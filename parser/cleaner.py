"""
Universal Cleaning Utilities

Used by all extractors.

Converts raw PDF values into clean API-ready values.
"""

import re
from datetime import datetime


def clean_text(value):
    """
    Generic text cleaner
    """

    if value is None:
        return "Not Found"

    value = str(value).strip()

    if not value:
        return "Not Found"

    value = value.replace("\n", " ")
    value = value.replace("\t", " ")

    while "  " in value:
        value = value.replace("  ", " ")

    return value.strip()


def clean_currency(value):
    """
    Convert

    ₹ 12,345
    12,345.00
    Rs. 12,345

    to

    12345.00
    """

    if not value:
        return "0.00"

    value = str(value)

    allowed = []

    for ch in value:

        if ch.isdigit():
            allowed.append(ch)

        elif ch == ".":
            allowed.append(ch)

    cleaned = "".join(allowed)

    if not cleaned:
        return "0.00"

    try:
        return f"{float(cleaned):.2f}"

    except Exception:
        return "0.00"


def clean_percentage(value):
    """
    Convert

    20
    20%
    NCB 20%

    into

    20%
    """

    if not value:
        return "0%"

    value = str(value)

    match = re.search(r"\b(\d{1,3})\s*%", value)
    if not match:
        match = re.search(r"\b(\d{1,3})\b", value)
    if not match:
        return "0%"
    return f"{match.group(1)}%"


def clean_mobile(value):
    """
    Extract valid mobile number
    """

    if not value:
        return "Not Found"

    digits = []

    for ch in str(value):

        if ch.isdigit():
            digits.append(ch)

    digits = "".join(digits)

    if len(digits) >= 10:
        return digits[-10:]

    return "Not Found"


def clean_email(value):
    """
    Validate email
    """

    if not value:
        return "Not Found"

    value = clean_text(value)
    if "*" in value:
        return "Not Found"

    match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", value, re.I)
    if not match:
        return "Not Found"
    return match.group(0)


def clean_policy_number(value):
    """Policy number cleanup and boundary trimming."""

    if not value:
        return "Not Found"

    value = clean_text(value)
    if not value:
        return "Not Found"

    value = value.replace(":", "")
    value = value.replace("#", "")

    tokens = value.split()
    stops = ["through", "preferred", "insurance", "partner", "proposal", "proposal no", "via", "on", "by"]
    trimmed = []
    for token in tokens:
        if token.lower() in stops:
            break
        trimmed.append(token)

    value = " ".join(trimmed).strip()
    if not any(ch.isdigit() for ch in value):
        return "Not Found"

    return value


def clean_vehicle_number(value):
    """Normalize vehicle registration numbers and reject IRDA labels."""

    if not value:
        return "Not Found"

    value = clean_text(value)
    if not value:
        return "Not Found"

    if any(token in value.upper() for token in ["IRDA", "REGISTRATION NO", "REGISTRATION NUMBER"]):
        return "Not Found"

    cleaned = "".join(ch for ch in value if ch.isalnum())
    cleaned = cleaned.upper()

    if len(cleaned) < 6:
        return "Not Found"

    if cleaned[:2].isalpha() and cleaned[2:].isdigit():
        return cleaned

    if cleaned.startswith(("DL", "KA", "MH", "TN", "UP", "PY", "OD", "WB", "AP", "CH", "GJ", "RJ", "PB", "HR")):
        return cleaned

    return "Not Found"


def clean_date(value):
    """
    Normalize common date formats

    02/07/2026
    02-Jul-2026
    02 Jul 2026

    =>
    2026-07-02
    """

    if not value:
        return "Not Found"

    value = clean_text(value)
    match = re.search(r"\b\d{1,2}[/-][A-Za-z]{3,9}[/-]\d{2,4}\b|\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", value)
    if match:
        value = match.group(0)

    formats = [

        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d"

    ]

    for fmt in formats:

        try:

            dt = datetime.strptime(value, fmt)

            return dt.strftime("%Y-%m-%d")

        except Exception:
            pass

    return value


def clean_address(value):
    """Address cleanup with stop-word trimming."""

    if not value:
        return "Not Found"

    value = clean_text(value)
    if not value:
        return "Not Found"

    lower = value.lower()
    stops = ["phone", "mobile", "email", "gstin", "vehicle", "policy", "registration", "previous policy", "nominee", "premium", "helpline", "help line", "website", "fax"]
    earliest = len(value)
    for stop in stops:
        idx = lower.find(stop)
        if idx != -1 and idx < earliest:
            earliest = idx
    if earliest < len(value):
        value = value[:earliest].strip()

    return value if value else "Not Found"


def clean_name(value):
    """Customer / Nominee name cleanup."""

    if not value:
        return "Not Found"

    value = clean_text(value)
    if not value:
        return "Not Found"

    prefixes = [
        "MR.",
        "MRS.",
        "MS.",
        "MISS",
        "SHRI",
        "SMT"
    ]

    upper = value.upper()
    for prefix in prefixes:
        if upper.startswith(prefix):
            value = value[len(prefix):].strip()
            break

    stops = ["period of insurance", "policy period", "cover", "validity", "premium", "gstin", "proposal", "previous" ]
    lower = value.lower()
    earliest = len(value)
    for stop in stops:
        idx = lower.find(stop)
        if idx != -1 and idx < earliest:
            earliest = idx
    if earliest < len(value):
        value = value[:earliest].strip()

    return value if value else "Not Found"


def clean_age(value):
    """
    Age cleanup
    """

    if not value:
        return "Not Found"

    digits = []

    for ch in str(value):

        if ch.isdigit():
            digits.append(ch)

    if not digits:
        return "Not Found"

    return "".join(digits)


def clean_value(value):
    """
    Universal fallback cleaner
    """

    return clean_text(value)
