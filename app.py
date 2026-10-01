# ── MUST be the first lines in the file, before any other imports ──────────
import sys
from concurrent.futures import InvalidStateError

def _suppress_awscrt_teardown_race(args):
    if args.exc_type is InvalidStateError:
        return  # known aws-crt-python race: _resolve_pending_chunk_futures vs cancelled future
    sys.__unraisablehook__(args)

sys.unraisablehook = _suppress_awscrt_teardown_race
# ─────────────────────────────────────────────────────────────────────────
import asyncio
import base64
import json
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.responses import Response
import uvicorn
from dotenv import load_dotenv

from nova_sonic import NovaSonic
from mcp_client import MCPClient
from utils.audio import twilio_to_nova, nova_to_twilio
import numpy as np
import audioop
load_dotenv()

mcp = MCPClient(server_script="mcp_server.py") 
SILENCE_THRESHOLD = 200  # amplitude level

def _loop_exception_handler(loop, context):
    exc = context.get("exception")
    if isinstance(exc, RuntimeError) and "AWS_ERROR_HTTP_STREAM_HAS_COMPLETED" in str(exc):
        return  # known awscrt teardown race — safe to ignore
    loop.default_exception_handler(context)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.get_event_loop().set_exception_handler(_loop_exception_handler)
    print("lifespan")
    await mcp.start()
    yield
    await mcp.stop()

# @asynccontextmanager
# async def lifespan(app:FastAPI):
#     try:
#         await mcp.start()
#     except Exception as e:
#         print(f"MCP startup failed: {e}")
#         raise
#     yield

app =FastAPI(lifespan=lifespan)

@app.get("/ping")
@app.get("/")
async def health_check():
   return {"status": "ok", "message": "Service is running"}


@app.post("/invocations")
async def invoke_agent(request: Request):
    """
    This endpoint is called by AgentCore when you use 'invoke_agent_runtime'
    """
    body = await request.json()
    return {"status": "ok","message":body} 

# ── WebSocket media stream ────────────────────────────────────────────────────

@app.websocket("/media-stream")
# @app.websocket("/ws")
async def media_stream(ws: WebSocket):
    await ws.accept()
    print("[ws] Twilio connected")
    # ── Nova Sonic Integrate with MCP Tools ────────
    nova = NovaSonic(mcp=mcp) 
    send_task = asyncio.create_task(_noop())
    send_task.add_done_callback(_silence_known_awscrt_race)
    stream_sid: str | None = None 
    await nova.start_session() 
    # ── Background task: watches for barge-in and sends Twilio 'clear' ────────
    async def _watch_barge_in():
        while nova.is_active:
            await nova.barge_in_event.wait()   # blocks until barge-in fires
            nova.barge_in_event.clear()
            if stream_sid:
                try:
                    await ws.send_text(json.dumps({
                        "event": "clear",
                        "streamSid": stream_sid,
                    }))
                    print("[ws] Sent Twilio 'clear' to flush playback buffer")
                except Exception as e:
                    print(f"[ws] clear send error: {e}")

    barge_in_watcher = asyncio.create_task(_watch_barge_in())
    barge_in_watcher.add_done_callback(_silence_known_awscrt_race)
    try:
        async for raw in ws.iter_text():
            msg = json.loads(raw)
            event = msg.get("event")

            if event == "start":
                stream_sid = msg["start"]["streamSid"]
                call_sid   = msg["start"]["callSid"]
                print(f"[ws] Stream started: {stream_sid}")
                await nova.start_audio_input(call_sid=call_sid)

                send_task.cancel()
                send_task = asyncio.create_task(
                    _relay_nova_to_twilio(ws, nova, stream_sid)
                )
                send_task.add_done_callback(_silence_known_awscrt_race)
            elif event == "media":
                mulaw = base64.b64decode(msg["media"]["payload"]) 
               # rms = audioop.rms(mulaw, 2)  # 2 bytes per sample (16-bit)
                pcm, nova.twilio_resample_state = twilio_to_nova(
                    mulaw, nova.twilio_resample_state
                ) 
               # if rms > SILENCE_THRESHOLD:
                await nova.send_audio_chunk(pcm)
                #print("Audio contains sound")
                    

            elif event == "stop":
                print("[ws] Stream stopped") 
                send_task.cancel()
                barge_in_watcher.cancel()
                await asyncio.sleep(0) # let in-flight writes/callbacks settle
                await nova.end_session()                
                break
    except asyncio.CancelledError:
        print("Task was cancelled")
    except Exception as e:
        print(f"[ws error] {e}")
    finally:
        if nova.is_active:
            send_task.cancel()
            barge_in_watcher.cancel()
            try:
                await asyncio.sleep(0)
                await nova.end_session()
            except Exception as e:
                print(f"[ws] end_session cleanup error: {e}")
     
        print("[ws] Session cleaned up")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _relay_nova_to_twilio(ws: WebSocket, nova: NovaSonic, stream_sid: str):
    resample_state = None
    try:
        while nova.is_active:
            item = await nova.audio_queue.get()
            gen_id, pcm_24k = item 
            # Drop stale chunks from before the barge-in
            if gen_id != nova._generation_id:
                continue

            mulaw, resample_state = nova_to_twilio(pcm_24k, resample_state)
            await ws.send_text(json.dumps({
                "event": "media",
                "streamSid": stream_sid,
                "media": {"track": "outbound", "payload": base64.b64encode(mulaw).decode("utf-8")},
            }))
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[relay error] {e}")

async def _noop():
    await asyncio.sleep(0)
    return "done"

def _silence_known_awscrt_race(task: asyncio.Task):
    if task.cancelled():
        return
    exc = task.exception()
    if exc is None:
        return
    if isinstance(exc, RuntimeError) and "AWS_ERROR_HTTP_STREAM_HAS_COMPLETED" in str(exc):
        return  # known awscrt close-race, safe to ignore
    print(f"[task error] {exc}")

 
if __name__ == "__main__":
    # Set your AWS credentials here or use environment variables 
    uvicorn.run(app, host="0.0.0.0", port=8080)