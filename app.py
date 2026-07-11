import re
import io
import os
from fastapi import FastAPI, UploadFile, File
import uvicorn
import pdfplumber

app = FastAPI(
    title="Insurance PDF Extraction API",
    description="Extracts 26 specific policy fields locally without cloud dependencies.",
    version="1.0.0"
)

def extract_target_text(file_bytes):
    """Parses text from the first 3 pages and the last page in-memory."""
    full_text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            total_pages = len(pdf.pages)
            pages_to_scan = set()
            for i in range(min(3, total_pages)):
                pages_to_scan.add(i)
            if total_pages > 3:
                pages_to_scan.add(total_pages - 1)
                
            for page_num in sorted(pages_to_scan):
                page_text = pdf.pages[page_num].extract_text()
                if page_text:
                    full_text += f"\n{page_text}\n"
        return full_text
    except Exception:
        return ""

def find_by_regex(pattern, text, group_num=1, default=None):
    """Helper to cleanly extract text matching a regex pattern."""
    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    if match:
        try:
            return match.group(group_num).strip().strip(":,#- ")
        except IndexError:
            return match.group(0).strip()
    return default

def find_by_proximity(keywords, pattern, text, window=100, default=None):
    """Finds a keyword, looks at a small text window ahead of it, and extracts data."""
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text.lower()):
            start_idx = match.start()
            text_window = text[start_idx : start_idx + window]
            found = find_by_regex(pattern, text_window, group_num=0)
            if found:
                return found.strip(":,#- ")
    return default

@app.post("/extract-policy", summary="Upload an insurance PDF to extract data structures")
async def process_policy_pdf(file: UploadFile = File(...)):
    # Read uploaded file bytes directly from memory
    file_bytes = await file.read()
    text = extract_target_text(file_bytes)
    
    if not text.strip():
        return {"error": "Failed to extract selectable text from this PDF file structure."}

    # Universal Patterns
    date_reg = r'(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b|\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b)'
    currency_reg = r'(\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b|\b\d+\.\d{2}\b|\b\d{3,8}\b)'
    email_reg = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    phone_reg = r'(\b\+?\d{1,4}[-.\s]?\d{10,12}\b|\b\d{10}\b)'

    # --- Data Extraction Logic Block ---
    
    # 1. Identity & Structural Fields
    policy_num = find_by_proximity(
        ["policy number", "policy #", "contract no", "policy no", "certificate no", "policy id"],
        r'([A-Za-z0-9-]{6,25})', text, window=60
    )
    if not policy_num: # Fallback global search
        policy_num = find_by_regex(r'\b[A-Za-z0-9]{2,4}-\d{5,10}\b|\b\d{8,12}\b', text, group_num=0, default="Not Found")

    cust_name = find_by_proximity(
        ["insured name", "customer name", "name of insured", "proposer name", "policyholder"],
        r'(?:name\s*:?)\s*([A-Za-z\s.]{3,35})', text, window=60
    )

    # 2. Categorization Metrics
    insurance_type = "Other"
    text_lower = text.lower()
    if any(k in text_lower for k in ["motor", "vehicle", "car ", "bike", "auto", "registration no", "engine no"]):
        insurance_type = "Motor"
    elif any(k in text_lower for k in ["life", "term insurance", "death benefit", "maturity"]):
        insurance_type = "Life"
    elif any(k in text_lower for k in ["property", "home", "building", "fire", "burglary"]):
        insurance_type = "Property"
    elif any(k in text_lower for k in ["health", "medical", "hospital", "mediclaim"]):
        insurance_type = "Health"

    # --- Construct Output Response Object (26 Fields Mapping) ---
    response_data = {
        "customerName": cust_name if cust_name else find_by_regex(r'(?:Mr\.|Ms\.|Mrs\.|M/s\.)\s+([A-Za-z\s]{3,30})', text, default="Not Found"),
        "policyType": find_by_proximity(["policy type", "plan type", "cover type"], r'([A-Za-z\s]{3,20})', text, default="Not Found"),
        "policyNumber": policy_num,
        "insuranceBranch": find_by_proximity(["branch code", "issuing office", "branch name", "operating office"], r'([A-Za-z0-9\s]{3,30})', text, default="Not Found"),
        "companyName": find_by_regex(r'\b([A-Za-z\s]{4,30}\s+(?:Insurance|Assurance|General|Life))\b', text, default="Not Found"),
        "insuranceType": insurance_type,
        "productName": find_by_proximity(["product name", "plan name", "scheme name"], r'([A-Za-z0-9\s-]{4,40})', text, default="Not Found"),
        
        # Timeline Dates
        "policyStartDate": find_by_proximity(["start date", "period of insurance from", "risk commencement", "effective date"], date_reg, text, window=80, default="Not Found"),
        "policyEndDate": find_by_proximity(["end date", "period of insurance to", "expiry date", "valid until"], date_reg, text, window=80, default="Not Found"),
        
        # Financial Premiums Breakdown
        "basicODPremium": find_by_proximity(["basic od", "own damage premium", "od premium"], currency_reg, text, default="0.00"),
        "tpPremium": find_by_proximity(["third party premium", "tp premium", "liability premium"], currency_reg, text, default="0.00"),
        "ncb": find_by_proximity(["no claim bonus", "ncb", "ncb %"], r'(\b\d{1,2}\s*%\b|\b\d{2,4}\b)', text, default="0"),
        "netPremium": find_by_proximity(["net premium", "premium before tax", "total premium due"], currency_reg, text, default="0.00"),
        "premiumDiscount": find_by_proximity(["total discount", "discount amount", "discount given"], currency_reg, text, default="0.00"),
        "gstPercent": find_by_proximity(["gst %", "cgst/sgst %", "tax rate"], r'(\b\d{1,2}\s*%\b|\b\d{1,2}\b)', text, default="18%"),
        "gstAmount": find_by_proximity(["gst amount", "total tax", "cgst", "sgst", "igst"], currency_reg, text, default="0.00"),
        "finalPremium": find_by_proximity(["final premium", "total premium", "amount payable", "premium collected"], currency_reg, text, default="0.00"),
        
        # Vehicle Parameters (Populated dynamically for Motor types)
        "vehicleIDV": find_by_proximity(["idv", "insured declared value", "total idv"], currency_reg, text, default="N/A"),
        "vehicleMake": find_by_proximity(["make", "manufacturer", "make/model"], r'([A-Za-z]{3,15})', text, default="N/A"),
        "vehicleModel": find_by_proximity(["model", "variant"], r'([A-Za-z0-9\s-]{3,20})', text, default="N/A"),
        "vehicleRegistrationNumber": find_by_regex(r'\b([A-Z]{2}\s*[-–]?\s*\d{1,2}\s*[-–]?\s*[A-Z]{1,3}\s*[-–]?\s*\d{4})\b', text, default="N/A"),
        
        # Demographics & Contacts
        "customerDOB": find_by_proximity(["dob", "date of birth", "birth date"], date_reg, text, default="Not Found"),
        "customerAge": find_by_proximity(["age", "insured age"], r'(\b\d{2}\b)', text, window=30, default="Not Found"),
        "customerAddress": find_by_proximity(["address", "communication address", "postal address"], r'([A-Za-z0-9\s,.-]{15,100})', text, window=150, default="Not Found"),
        "customerMobileNumber": find_by_regex(phone_reg, text, default="Not Found"),
        "customerEmailId": find_by_regex(email_reg, text, default="Not Found")
    }

    return response_data

if __name__ == "__main__":
    # Start web server locally on port 8000
    uvicorn.run("app:app", host="127.0.0.1", port=8080, reload=True)
