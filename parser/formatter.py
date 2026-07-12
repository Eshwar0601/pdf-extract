"""
Response Formatter

Converts extracted raw values into
clean API response.

Keeps extractor.py clean and small.
"""

from parser.cleaner import (
    clean_name,
    clean_text,
    clean_currency,
    clean_percentage,
    clean_mobile,
    clean_email,
    clean_date,
    clean_policy_number,
    clean_vehicle_number,
    clean_address,
    clean_age
)


FIELD_CLEANERS = {

    "customerName": clean_name,

    "policyType": clean_text,

    "policyNumber": clean_policy_number,

    "insuranceBranch": clean_text,

    "companyName": clean_text,

    "insuranceType": clean_text,

    "productName": clean_text,

    "policyStartDate": clean_date,

    "policyEndDate": clean_date,

    "basicODPremium": clean_currency,

    "tpPremium": clean_currency,

    "ncb": clean_percentage,

    "netPremium": clean_currency,

    "premiumDiscount": clean_currency,

    "gstPercent": clean_percentage,

    "gstAmount": clean_currency,

    "finalPremium": clean_currency,

    "vehicleIDV": clean_currency,

    "vehicleMake": clean_text,

    "vehicleModel": clean_text,

    "vehicleRegistrationNumber": clean_vehicle_number,

    "vehicleEngineNumber": clean_text,

    "vehicleChassisNumber": clean_text,

    "customerDOB": clean_date,

    "customerAge": clean_age,

    "customerAddress": clean_address,

    "customerMobileNumber": clean_mobile,

    "customerEmailId": clean_email
}


DEFAULT_RESPONSE = {

    "customerName": "Not Found",

    "policyType": "Not Found",

    "policyNumber": "Not Found",

    "insuranceBranch": "Not Found",

    "companyName": "Unknown",

    "insuranceType": "Other",

    "productName": "Not Found",

    "policyStartDate": "Not Found",

    "policyEndDate": "Not Found",

    "basicODPremium": "0.00",

    "tpPremium": "0.00",

    "ncb": "0%",

    "netPremium": "0.00",

    "premiumDiscount": "0.00",

    "gstPercent": "18%",

    "gstAmount": "0.00",

    "finalPremium": "0.00",

    "vehicleIDV": "0.00",

    "vehicleMake": "Not Found",

    "vehicleModel": "Not Found",

    "vehicleRegistrationNumber": "Not Found",

    "vehicleEngineNumber": "Not Found",

    "vehicleChassisNumber": "Not Found",

    "customerDOB": "Not Found",

    "customerAge": "Not Found",

    "customerAddress": "Not Found",

    "customerMobileNumber": "Not Found",

    "customerEmailId": "Not Found"

}


def format_response(raw_data):
    """
    Apply field-specific cleaners
    and return final JSON response.
    """

    response = DEFAULT_RESPONSE.copy()

    for field in response:

        if field in raw_data:

            value = raw_data[field]

            cleaner = FIELD_CLEANERS.get(field, clean_text)

            try:
                response[field] = cleaner(value)

            except Exception:
                response[field] = value

    return response


def merge_data(*sources):
    """
    Merge multiple extraction results.

    Priority:
        First non-empty value wins.

    Example:

        merge_data(
            keyword_result,
            table_result,
            layout_result
        )
    """

    merged = {}

    for source in sources:

        if not source:
            continue

        for key, value in source.items():

            if key not in merged:

                merged[key] = value

                continue

            if merged[key] in [
                "",
                None,
                "Not Found",
                "Unknown",
                "0.00",
                "0%"
            ]:

                if value not in [
                    "",
                    None,
                    "Not Found",
                    "Unknown"
                ]:

                    merged[key] = value

    return merged


def update_response(response, field, value):
    """
    Update a single field using
    appropriate cleaner.
    """

    cleaner = FIELD_CLEANERS.get(field, clean_text)

    response[field] = cleaner(value)

    return response