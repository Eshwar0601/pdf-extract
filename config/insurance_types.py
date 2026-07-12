"""Scoring-based insurance type detection."""

INSURANCE_TYPES = {
    "Motor": [
        "motor",
        "private car",
        "private vehicle",
        "commercial vehicle",
        "two wheeler",
        "bike",
        "motorcycle",
        "scooter",
        "car",
        "vehicle",
        "registration number",
        "registration mark",
        "engine no",
        "engine number",
        "chassis no",
        "chassis number",
        "vehicle idv",
        "idv",
        "rto",
        "fuel type",
        "make",
        "model",
        "variant",
        "own damage",
        "third party",
        "tp premium",
        "od premium",
        "certificate cum policy schedule",
        "certificate of insurance"
    ],
    "Health": [
        "health insurance",
        "health policy",
        "mediclaim",
        "cashless",
        "hospital",
        "hospitalization",
        "insured person",
        "insured member",
        "sum insured",
        "pre-existing disease",
        "room rent",
        "day care",
        "critical illness",
        "family floater",
        "health card",
        "claim settlement"
    ],
    "Life": [
        "life insurance",
        "life assured",
        "life cover",
        "death benefit",
        "nominee",
        "maturity benefit",
        "survival benefit",
        "policy anniversary",
        "premium paying term",
        "policy term",
        "sum assured",
        "annualized premium",
        "risk commencement",
        "life insured"
    ],
    "Travel": [
        "travel insurance",
        "trip",
        "journey",
        "passport",
        "visa",
        "flight",
        "baggage",
        "travel period",
        "overseas",
        "international travel",
        "domestic travel"
    ],
    "Personal Accident": [
        "personal accident",
        "accidental death",
        "permanent disability",
        "temporary disability",
        "accidental benefit",
        "owner driver",
        "pa cover"
    ],
    "Home": [
        "home insurance",
        "householder",
        "building",
        "contents",
        "property",
        "fire and allied perils",
        "burglary"
    ],
    "Marine": [
        "marine",
        "cargo",
        "shipment",
        "consignment",
        "bill of lading",
        "voyage"
    ],
    "Fire": [
        "fire policy",
        "fire insurance",
        "industrial all risk",
        "fire and allied perils"
    ],
    "Crop": [
        "crop insurance",
        "farmer",
        "crop",
        "agriculture",
        "pmfby"
    ]
}


def detect_insurance_type(raw_text: str) -> str:
    if not raw_text:
        return "Other"

    text = raw_text.lower()
    scores = {}

    for insurance_type, keywords in INSURANCE_TYPES.items():
        score = 0
        for keyword in keywords:
            if keyword.lower() in text:
                score += 1
        scores[insurance_type] = score

    best_match = max(scores, key=scores.get)
    return best_match if scores[best_match] > 0 else "Other"