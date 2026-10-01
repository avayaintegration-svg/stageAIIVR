from mcp.server.fastmcp import FastMCP
from tools import member,  provider , verify_eligibility , transfer ,claim_status
 

mcp = FastMCP("HealthCare-Assistant")

member.register(mcp)
provider.register(mcp)
verify_eligibility.register(mcp)
transfer.register(mcp)

claim_status.register(mcp)


if __name__ == "__main__":
    print("MCP RUN")
    mcp.run()