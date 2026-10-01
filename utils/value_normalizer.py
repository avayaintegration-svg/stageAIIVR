import re
import unicodedata
from datetime import datetime
from typing import Any


DIGIT_WORDS: dict[str, str] = {
    # English
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "to": "2",
    "too": "2",
    "three": "3",
    "four": "4",
    "for": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "ate": "8",
    "nine": "9",

    # Spanish
    "cero": "0",
    "uno": "1",
    "dos": "2",
    "tres": "3",
    "cuatro": "4",
    "cinco": "5",
    "seis": "6",
    "siete": "7",
    "ocho": "8",
    "nueve": "9",

    # French
    "zéro": "0",
    "un": "1",
    "une": "1",
    "deux": "2",
    "trois": "3",
    "quatre": "4",
    "cinq": "5",
    "sept": "7",
    "huit": "8",
    "neuf": "9",
}


PHONETIC_WORDS: dict[str, str] = {
    # NATO
    "alpha": "A",
    "bravo": "B",
    "charlie": "C",
    "delta": "D",
    "echo": "E",
    "foxtrot": "F",
    "golf": "G",
    "hotel": "H",
    "india": "I",
    "juliett": "J",
    "juliet": "J",
    "kilo": "K",
    "lima": "L",
    "mike": "M",
    "november": "N",
    "oscar": "O",
    "papa": "P",
    "quebec": "Q",
    "romeo": "R",
    "sierra": "S",
    "tango": "T",
    "uniform": "U",
    "victor": "V",
    "whiskey": "W",
    "xray": "X",
    "yankee": "Y",
    "zulu": "Z",

    # Common spoken variants
    "apple": "A",
    "boy": "B",
    "cat": "C",
    "dog": "D",
    "elephant": "E",
    "fish": "F",
    "goat": "G",
    "house": "H",
    "ice": "I",
    "john": "J",
    "king": "K",
    "lion": "L",
    "mother": "M",
    "nancy": "N",
    "orange": "O",
    "queen": "Q",
    "robert": "R",
    "sam": "S",
    "tom": "T",
    "umbrella": "U",
    "van": "V",
    "william": "W",
    "yellow": "Y",
    "zebra": "Z",
}


IDENTIFIER_FIELDS = {
    "memberid",
    "member_id",
    "memberId",
    "claimid",
    "claim_id",
    "claimId",
    "authorizationid",
    "authorization_id",
    "authorization_number",
    "authorizationNumber",
    "auth_id",
    "auth_number",
    "providerid",
    "provider_id",
    "providerId",
    "referenceid",
    "reference_id",
    "reference_number",
    "caseid",
    "case_id",
    "interactionid",
    "interaction_id",
}


DOB_FIELDS = {
    "dob",
    "dateofbirth",
    "date_of_birth",
    "dateOfBirth",
    "birthdate",
    "birth_date",
}


def remove_accents(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    return "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )


def normalize_identifier(
    value: Any,
) -> str:
    if value is None:
        return ""

    text = remove_accents(
        str(value).strip().lower()
    )

    if not text:
        return ""

    tokens = re.findall(
        r"[a-z]+|\d+",
        text,
    )

    normalized_parts: list[str] = []

    for token in tokens:
        if token in DIGIT_WORDS:
            normalized_parts.append(
                DIGIT_WORDS[token]
            )

        elif token in PHONETIC_WORDS:
            normalized_parts.append(
                PHONETIC_WORDS[token]
            )

        elif token.isdigit():
            normalized_parts.append(token)

        else:
            normalized_parts.append(
                token.upper()
            )

    return re.sub(
        r"[^A-Z0-9]",
        "",
        "".join(normalized_parts).upper(),
    )


def normalize_dob(
    value: Any,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    text = re.sub(
        r"(?i)(\d{1,2})(st|nd|rd|th)",
        r"\1",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # Convert spoken digits first.
    tokens = re.findall(
        r"[A-Za-zÀ-ÿ]+|\d+|[/.-]",
        text.lower(),
    )

    converted_parts: list[str] = []

    for token in tokens:
        accent_free_token = remove_accents(token)

        if token in DIGIT_WORDS:
            converted_parts.append(
                DIGIT_WORDS[token]
            )

        elif accent_free_token in DIGIT_WORDS:
            converted_parts.append(
                DIGIT_WORDS[accent_free_token]
            )

        else:
            converted_parts.append(token)

    converted_text = "".join(converted_parts)

    formats = [
        "%d%m%Y",
        "%Y%m%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%d %b, %Y",
        "%d %B, %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    candidates = [
        text,
        converted_text,
    ]

    for candidate in candidates:
        for date_format in formats:
            try:
                parsed_date = datetime.strptime(
                    candidate,
                    date_format,
                )

                return parsed_date.strftime(
                    "%Y-%m-%d"
                )

            except (ValueError, TypeError):
                continue

    return None


def normalize_parameter(
    parameter_name: str,
    value: Any,
) -> Any:
    if value is None:
        return None

    if parameter_name in DOB_FIELDS:
        normalized_dob = normalize_dob(value)

        # Preserve the original input when parsing fails so that the
        # actual tool can return the appropriate validation message.
        return (
            normalized_dob
            if normalized_dob is not None
            else value
        )

    if parameter_name in IDENTIFIER_FIELDS:
        return normalize_identifier(value)

    return value


def normalize_tool_arguments(
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    if not arguments:
        return {}

    normalized_arguments: dict[str, Any] = {}

    for parameter_name, value in arguments.items():
        if isinstance(value, dict):
            normalized_arguments[parameter_name] = (
                normalize_tool_arguments(value)
            )

        elif isinstance(value, list):
            normalized_arguments[parameter_name] = [
                (
                    normalize_tool_arguments(item)
                    if isinstance(item, dict)
                    else item
                )
                for item in value
            ]

        else:
            normalized_arguments[parameter_name] = (
                normalize_parameter(
                    parameter_name,
                    value,
                )
            )

    return normalized_arguments