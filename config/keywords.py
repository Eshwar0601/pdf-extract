"""
Universal Insurance PDF Parser

Field aliases are configured centrally so the parser logic remains generic.
"""

FIELDS = {
    "customerName": [
        "Customer Name",
        "Customer Name:",
        "Client Name",
        "Policy Holder Name",
        "Policyholder Name",
        "Policy Holder",
        "Insured Name",
        "Insured's Name",
        "Insured Name:",
        "Insured's Code/Name",
        "Name of Insured",
        "Proposer Name",
        "Applicant Name",
        "Life Assured",
        "Member Name",
        "Employee Name",
        "Name of the Insured",
        "Name of Life Assured"
    ],
    "customerAddress": [
        "Address",
        "Customer Address",
        "Insured Address",
        "Insured Address and Contact Details",
        "Communication Address",
        "Permanent Address",
        "Residential Address",
        "Postal Address"
    ],
    "customerMobileNumber": [
        "Mobile",
        "Mobile No",
        "Mobile Number",
        "Phone",
        "Phone No",
        "Phone Number",
        "Mob",
        "Contact",
        "Contact Number",
        "Contact No"
    ],
    "customerEmailId": [
        "Email",
        "Email Address",
        "Email ID",
        "Email Id",
        "E-Mail",
        "Customer Email"
    ],
    "customerDOB": [
        "DOB",
        "Date of Birth",
        "Birth Date",
        "Date of Birth of Insured"
    ],
    "customerAge": [
        "Age",
        "Customer Age",
        "Nominee Age",
        "Insured Age"
    ],
    "policyNumber": [
        "Policy Number",
        "Policy No",
        "Policy No.",
        "Policy #",
        "Certificate Number",
        "Certificate No",
        "Insurance Policy Number",
        "Quotation Number",
        "Quotation No",
        "Quote Number",
        "Quote No",
        "Proposal Number",
        "Proposal No",
        "Policy No. & Policy Issued On",
        "Vehicle Insurance Policy Number",
        "Certificate Cum Policy Schedule"
    ],
    "policyType": [
        "Policy Type",
        "Policy Plan",
        "Plan Type",
        "Policy Name",
        "Insurance Type",
        "Cover Type",
        "Product",
        "Product Name",
        "Plan"
    ],
    "productName": [
        "Product Name",
        "Plan Name",
        "Product",
        "Plan",
        "Policy Name"
    ],
    "policyStartDate": [
        "Period of Insurance From",
        "Coverage From",
        "Policy Start Date",
        "Start Date",
        "Risk Commencement",
        "Risk Commencement Date",
        "From"
    ],
    "policyEndDate": [
        "Period of Insurance To",
        "Coverage To",
        "Policy End Date",
        "Expiry Date",
        "End Date",
        "To"
    ],
    "insuranceBranch": [
        "Branch",
        "Branch Office",
        "Servicing Office",
        "Policy Issuing Office",
        "Issuing Office"
    ],
    "vehicleRegistrationNumber": [
        "Registration Number",
        "Vehicle Registration Number",
        "Vehicle Registration No",
        "Vehicle Number",
        "Registration Mark",
        "Registration Mark & No",
        "Registration No",
        "Vehicle No",
        "Regn. No"
    ],
    "vehicleMake": [
        "Make",
        "Vehicle Make",
        "Make of Vehicle",
        "Manufacturer"
    ],
    "vehicleModel": [
        "Model",
        "Vehicle Model",
        "Variant",
        "Model/Vehicle Variant",
        "Vehicle Variant",
        "Model Name"
    ],
    "vehicleEngineNumber": [
        "Engine Number",
        "Engine No",
        "Engine No."
    ],
    "vehicleChassisNumber": [
        "Chassis Number",
        "Chassis No",
        "VIN",
        "Chassis No."
    ],
    "vehicleIDV": [
        "IDV",
        "Vehicle IDV",
        "Total IDV",
        "Insured Declared Value",
        "IDV of Vehicle"
    ],
    "basicODPremium": [
        "Basic OD Premium",
        "Basic Premium",
        "Own Damage Premium",
        "OD Premium",
        "OD TOTAL",
        "Net Own Damage Premium"
    ],
    "tpPremium": [
        "Basic TP Premium",
        "Third Party Premium",
        "TP Premium",
        "TP TOTAL",
        "Liability Premium",
        "Basic Third Party Liability"
    ],
    "netPremium": [
        "Net Premium",
        "Gross Premium",
        "Premium Before Tax"
    ],
    "premiumDiscount": [
        "Discount",
        "Discount Amount",
        "Premium Discount",
        "Less",
        "No Claim Bonus Discount"
    ],
    "gstAmount": [
        "GST",
        "GST Amount",
        "CGST",
        "SGST",
        "IGST"
    ],
    "finalPremium": [
        "Final Premium",
        "Total Premium",
        "Premium Amount",
        "Gross Premium Payable",
        "Total Amount",
        "Amount Payable"
    ],
    "ncb": [
        "NCB",
        "No Claim Bonus",
        "No Claim Bonus Discount"
    ]
}