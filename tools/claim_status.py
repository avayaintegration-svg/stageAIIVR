# tools/claim_status.py
import re 
from datetime import datetime
 

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from decimal import Decimal, InvalidOperation
from typing import Optional, Union


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

class ClaimStatusOutput(BaseModel):
    status: str = Field(
        description=(
            "Tool execution status: success, failed, "
            "not_found, or invalid_request."
        )
    )

    claim_id: str = Field(
        description="Normalized claim identifier."
    )

    member_id: Optional[str] = Field(
        default=None,
        description="Member ID associated with the claim."
    )

    claim_status: Optional[str] = Field(
        default=None,
        description=(
            "Business claim status such as Paid, Denied, "
            "Pending, or Not on File."
        )
    )

    service_start_date: Optional[str] = Field(
        default=None,
        description=(
            "Beginning date of service in YYYY-MM-DD format."
        )
    )

    service_end_date: Optional[str] = Field(
        default=None,
        description=(
            "Ending date of service in YYYY-MM-DD format."
        )
    )

    received_date: Optional[str] = Field(
        default=None,
        description=(
            "Date the claim was received in YYYY-MM-DD format."
        )
    )

    processed_date: Optional[str] = Field(
        default=None,
        description=(
            "Date the claim was processed in YYYY-MM-DD format."
        )
    )

    paid_date: Optional[str] = Field(
        default=None,
        description=(
            "Claim payment date in YYYY-MM-DD format."
        )
    )

    pay_to_provider: Optional[str] = Field(
        default=None,
        description="Provider or entity to which payment was issued."
    )

    billed_amount: Optional[float] = Field(
        default=None,
        description="Total amount billed on the claim."
    )

    allowed_amount: Optional[float] = Field(
        default=None,
        description="Total allowed amount on the claim."
    )

    paid_amount: Optional[float] = Field(
        default=None,
        description="Total amount paid on the claim."
    )

    member_responsibility: Optional[float] = Field(
        default=None,
        description=(
            "Total member responsibility, when available."
        )
    )

    check_number: Optional[str] = Field(
        default=None,
        description=(
            "Payment check or electronic payment reference."
        )
    )

    denial_reason: Optional[str] = Field(
        default=None,
        description="Reason the claim was denied."
    )

    pending_reason: Optional[str] = Field(
        default=None,
        description="Reason the claim is pending."
    )

    message: str = Field(
        description="Short result suitable for application handling."
    )

    response_prompt: str = Field(
        description=(
            "Natural-language response that Nova Sonic can "
            "speak to the caller."
        )
    )


# ---------------------------------------------------------------------------
# Mock claim data
#
# Replace this list later with your database or external REST API.
# ---------------------------------------------------------------------------

CLAIM_DATA = [
    {
        "claim_id": "CLM100001",
        "member_id": "1001",
        "claim_status": "Paid",
        "service_start_date": "2026-08-01",
        "service_end_date": "2026-08-01",
        "received_date": "2026-08-05",
        "processed_date": "2026-08-12",
        "paid_date": "2026-08-15",
        "pay_to_provider": "BayCare Medical Group",
        "billed_amount": 450.00,
        "allowed_amount": 325.00,
        "paid_amount": 260.00,
        "member_responsibility": 65.00,
        "check_number": "EFT900001",
        "denial_reason": None,
        "pending_reason": None,
    },
    {
        "claim_id": "12345E005192",
        "member_id": "1001",
        "claim_status": "Denied",
        "service_start_date": "2025-10-08",
        "service_end_date": "2025-10-08",
        "received_date": "2025-12-30",
        "processed_date": "2026-01-05",
        "paid_date": None,
        "pay_to_provider": None,
        "billed_amount": 275.00,
        "allowed_amount": 0.00,
        "paid_amount": 0.00,
        "member_responsibility": 0.00,
        "check_number": None,
        "denial_reason": (
            "The submitted procedure code was not valid for "
            "the established patient service."
        ),
        "pending_reason": None,
    },
    {
        "claim_id": "12345E000917",
        "member_id": "1008",
        "claim_status": "Denied",
        "service_start_date": "2025-12-31",
        "service_end_date": "2025-12-31",
        "received_date": "2026-01-01",
        "processed_date": "2026-01-04",
        "paid_date": None,
        "pay_to_provider": None,
        "billed_amount": 180.00,
        "allowed_amount": 0.00,
        "paid_amount": 0.00,
        "member_responsibility": 0.00,
        "check_number": None,
        "denial_reason": (
            "The submitted procedure or units of service "
            "were not covered under the applicable claim rules."
        ),
        "pending_reason": None,
    },
    {
        "claim_id": "12345E003627",
        "member_id": "1008",
        "claim_status": "Pending",
        "service_start_date": "2025-09-15",
        "service_end_date": "2025-09-15",
        "received_date": "2025-10-03",
        "processed_date": None,
        "paid_date": None,
        "pay_to_provider": None,
        "billed_amount": 780.00,
        "allowed_amount": None,
        "paid_amount": None,
        "member_responsibility": None,
        "check_number": None,
        "denial_reason": None,
        "pending_reason": (
            "The claim is under review and additional "
            "information may be required."
        ),
    },
    {
        "claim_id": "12345E004854",
        "member_id": "1008",
        "claim_status": "Paid",
        "service_start_date": "2025-07-22",
        "service_end_date": "2025-07-22",
        "received_date": "2025-08-01",
        "processed_date": "2025-08-08",
        "paid_date": "2025-08-12",
        "pay_to_provider": "Sample Pay-To Provider",
        "billed_amount": 625.00,
        "allowed_amount": 500.00,
        "paid_amount": 400.00,
        "member_responsibility": 100.00,
        "check_number": "EFT2517004854",
        "denial_reason": None,
        "pending_reason": None,
    },
]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def normalize_identifier(value: Optional[str]) -> str:
    """
    Normalize a member or claim identifier.

    Examples:
        CLM-100-001    -> CLM100001
        25364 E005192  -> 25364E005192
        000 410 939    -> 000410939
    """

    if value is None:
        return ""

    return re.sub(
        r"[^A-Za-z0-9]",
        "",
        str(value),
    ).upper()


def normalize_date_for_speech(
    date_value: Optional[str],
) -> Optional[str]:
    """
    Convert YYYY-MM-DD to a natural spoken date.

    Example:
        2026-08-15 -> August 15, 2026
    """

    if not date_value:
        return None

    try:
        parsed_date = datetime.strptime(
            date_value,
            "%Y-%m-%d",
        )

        return parsed_date.strftime("%B %d, %Y")

    except ValueError:
        return date_value


def format_currency(
    amount: Optional[Union[int, float, Decimal, str]],
) -> Optional[str]:
    if amount is None:
        return None

    if isinstance(amount, str):
        amount = amount.strip()

        if not amount:
            return None

        # Accept values such as "$1,234.50".
        amount = amount.replace("$", "").replace(",", "")

    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return None

    if not decimal_amount.is_finite():
        return None

    return f"${decimal_amount:,.2f}"

# ---------------------------------------------------------------------------
# Response prompt builders
# ---------------------------------------------------------------------------

def build_paid_response(record: dict) -> str:
    service_start = normalize_date_for_speech(
        record.get("service_start_date")
    )

    service_end = normalize_date_for_speech(
        record.get("service_end_date")
    )

    paid_date = normalize_date_for_speech(
        record.get("paid_date")
    )

    paid_amount = format_currency(
        record.get("paid_amount")
    )

    prompt_parts = [
        f"Your claim number is {record['claim_id']}.",
        "The claim status is paid.",
    ]

    if service_start and service_end:
        if service_start == service_end:
            prompt_parts.append(
                f"The date of service was {service_start}."
            )
        else:
            prompt_parts.append(
                "The dates of service were from "
                f"{service_start} through {service_end}."
            )

    if record.get("pay_to_provider"):
        prompt_parts.append(
            "The claim was paid to "
            f"{record['pay_to_provider']}."
        )

    if paid_amount:
        prompt_parts.append(
            f"The paid amount was {paid_amount}."
        )

    if paid_date:
        prompt_parts.append(
            f"The payment date was {paid_date}."
        )

    return " ".join(prompt_parts)


def build_denied_response(record: dict) -> str:
    service_start = normalize_date_for_speech(
        record.get("service_start_date")
    )

    service_end = normalize_date_for_speech(
        record.get("service_end_date")
    )

    prompt_parts = [
        f"Your claim number is {record['claim_id']}.",
        "The claim status is denied.",
    ]

    if service_start and service_end:
        if service_start == service_end:
            prompt_parts.append(
                f"The date of service was {service_start}."
            )
        else:
            prompt_parts.append(
                "The dates of service were from "
                f"{service_start} through {service_end}."
            )

    if record.get("denial_reason"):
        prompt_parts.append(
            f"The denial reason is "
            f"{record['denial_reason']}"
        )

    return " ".join(prompt_parts)


def build_pending_response(record: dict) -> str:
    service_start = normalize_date_for_speech(
        record.get("service_start_date")
    )

    service_end = normalize_date_for_speech(
        record.get("service_end_date")
    )

    prompt_parts = [
        f"Your claim number is {record['claim_id']}.",
        "The claim status is pending.",
    ]

    if service_start and service_end:
        if service_start == service_end:
            prompt_parts.append(
                f"The date of service was {service_start}."
            )
        else:
            prompt_parts.append(
                "The dates of service were from "
                f"{service_start} through {service_end}."
            )

    if record.get("pending_reason"):
        prompt_parts.append(
            f"{record['pending_reason']}"
        )

    return " ".join(prompt_parts)


def build_response_prompt(record: dict) -> str:
    claim_status = str(
        record.get("claim_status", "")
    ).strip().lower()

    if claim_status == "paid":
        return build_paid_response(record)

    if claim_status == "denied":
        return build_denied_response(record)

    if claim_status in {"pending", "pend", "pended"}:
        return build_pending_response(record)

    return (
        f"Your claim number is {record['claim_id']}. "
        f"The claim status is "
        f"{record.get('claim_status', 'unavailable')}."
    )


# ---------------------------------------------------------------------------
# Claim lookup
# ---------------------------------------------------------------------------
 

def find_claim(
    claim_id: str,
    member_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:

    """
    Find a claim by claim ID.

    When member_id is supplied, the claim must also belong
    to that member.
    """

    normalized_claim_id = normalize_identifier(claim_id)
    normalized_member_id = normalize_identifier(member_id)

    if not normalized_claim_id:
        return None

    for record in CLAIM_DATA:
        if not isinstance(record, dict):
            continue

        record_claim_id = normalize_identifier(
            record.get("claim_id")
        )

        if record_claim_id != normalized_claim_id:
            continue

        # When member_id is supplied, enforce ownership matching.
        if normalized_member_id:
            record_member_id = normalize_identifier(
                record.get("member_id")
            )

            if record_member_id != normalized_member_id:
                continue

        return record

    return None


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------
def register(mcp: FastMCP) -> None:

    @mcp.tool(
        description=(
            "Retrieve a healthcare claim status using the "
            "claim ID and authenticated member ID. "
            "Returns paid, denied, pending, or not-found status, "
            "dates of service, payment information, denial reason, "
            "pending reason, and a caller-friendly response. "
            "Only call this tool after member authentication. "
            "Do not invent claim information."
        )
    )
    def get_claim_status(
        claim_id: str,
        member_id: Optional[str] = None,
    ) -> ClaimStatusOutput:
        normalized_claim_id = normalize_identifier(
            claim_id
        )

        normalized_member_id = normalize_identifier(
            member_id
        )

        if not normalized_claim_id:
            return ClaimStatusOutput(
                status="invalid_request",
                claim_id="",
                member_id=(
                    normalized_member_id or None
                ),
                claim_status=None,
                message="Claim ID is required.",
                response_prompt=(
                    "Please provide the claim number."
                ),
            )

        if not normalized_member_id:
            return ClaimStatusOutput(
                status="invalid_request",
                claim_id=normalized_claim_id,
                member_id=None,
                claim_status=None,
                message=(
                    "Authenticated member ID is required."
                ),
                response_prompt=(
                    "I need to authenticate the member "
                    "before checking the claim status."
                ),
            )

        print(
            "[get_claim_status] Lookup request: "
            f"claim_id={normalized_claim_id}, "
            f"member_id={normalized_member_id}"
        )

        record = find_claim(
            claim_id=normalized_claim_id,
            member_id=normalized_member_id,
        )

        if record is None:
            return ClaimStatusOutput(
                status="not_found",
                claim_id=normalized_claim_id,
                member_id=normalized_member_id,
                claim_status="Not on File",
                message=(
                    "No matching claim was found for the "
                    "authenticated member."
                ),
                response_prompt=(
                    "I could not find that claim under the "
                    "authenticated member's account. "
                    "Please verify the claim number and try again."
                ),
            )

        response_prompt = build_response_prompt(
            record
        )

        return ClaimStatusOutput(
            status="success",
            claim_id=record["claim_id"],
            member_id=record["member_id"],
            claim_status=record["claim_status"],
            service_start_date=record.get(
                "service_start_date"
            ),
            service_end_date=record.get(
                "service_end_date"
            ),
            received_date=record.get(
                "received_date"
            ),
            processed_date=record.get(
                "processed_date"
            ),
            paid_date=record.get(
                "paid_date"
            ),
            pay_to_provider=record.get(
                "pay_to_provider"
            ),
            billed_amount=record.get(
                "billed_amount"
            ),
            allowed_amount=record.get(
                "allowed_amount"
            ),
            paid_amount=record.get(
                "paid_amount"
            ),
            member_responsibility=record.get(
                "member_responsibility"
            ),
            check_number=record.get(
                "check_number"
            ),
            denial_reason=record.get(
                "denial_reason"
            ),
            pending_reason=record.get(
                "pending_reason"
            ),
            message="Claim status retrieved successfully.",
            response_prompt=response_prompt,
        )