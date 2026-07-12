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

    digits = []

    for ch in value:

        if ch.isdigit():
            digits.append(ch)

    if not digits:
        return "0%"

    return f'{"".join(digits)}%'


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

    if "@" not in value:
        return "Not Found"

    return value


def clean_policy_number(value):
    """
    Policy number cleanup
    """

    if not value:
        return "Not Found"

    value = clean_text(value)

    value = value.replace(":", "")
    value = value.replace("#", "")

    return value.strip()


def clean_vehicle_number(value):
    """Normalize vehicle registration numbers."""

    if not value:
        return "Not Found"

    value = clean_text(value)
    if not value:
        return "Not Found"

    if any(token in value.upper() for token in ["IRDA", "REGISTRATION NO", "REGISTRATION NUMBER"]):
        return "Not Found"

    cleaned = "".join(ch for ch in value if ch.isalnum())
    cleaned = cleaned.upper()

    if len(cleaned) < 4:
        return "Not Found"

    if cleaned.startswith("DL") or cleaned.startswith("KA") or cleaned.startswith("MH") or cleaned.startswith("TN"):
        return cleaned

    return cleaned if cleaned.isalnum() else "Not Found"


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
    """
    Address cleanup
    """

    if not value:
        return "Not Found"

    value = clean_text(value)

    return value


def clean_name(value):
    """
    Customer / Nominee name cleanup
    """

    if not value:
        return "Not Found"

    value = clean_text(value)

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

    return value


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