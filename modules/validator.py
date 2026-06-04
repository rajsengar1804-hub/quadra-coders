# modules/validator.py
# This module validates extracted fields from an income certificate
# using rule-based checks and generates a fraud risk score.

import re
from datetime import datetime


def validate_certificate(extracted_fields, ocr_text):
    """
    Validates the extracted fields and OCR text from an income certificate.

    Args:
        extracted_fields (dict): Fields extracted by field_extractor.py
        ocr_text (str): Full OCR text extracted from the document

    Returns:
        dict: Validation results including checks, issues, fraud types, score, and status
    """

    # ── Safe defaults ──────────────────────────────────────────────────────────
    # If any key is missing from extracted_fields, default to "Not Found"
    cert_number     = extracted_fields.get("certificate_number", "Not Found")
    applicant_name  = extracted_fields.get("applicant_name",     "Not Found")
    father_name     = extracted_fields.get("father_name",        "Not Found")
    annual_income   = extracted_fields.get("annual_income",      "Not Found")
    issue_date      = extracted_fields.get("issue_date",         "Not Found")
    place           = extracted_fields.get("place",              "Not Found")
    authority       = extracted_fields.get("issuing_authority",  "Not Found")
    designation     = extracted_fields.get("designation",        "Not Found")
    financial_year  = extracted_fields.get("financial_year",     "Not Found")

    # ── Result containers ──────────────────────────────────────────────────────
    checks = {}
    issues = []
    fraud_types = []
    score = 100  # Start with perfect score and deduct

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 1: Certificate Number Format
    # Expected: INC/DEMO/YYYY/NNN (at least 3 digits at end)
    # ══════════════════════════════════════════════════════════════════════════
    cert_pattern = r'^INC/DEMO/\d{4}/\d{3,}$'

    if cert_number != "Not Found" and re.match(cert_pattern, cert_number.strip()):
        checks["certificate_number_valid"] = True
    else:
        checks["certificate_number_valid"] = False
        issues.append("Certificate number format is invalid.")
        fraud_types.append("Invalid Certificate Number")
        score -= 20

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 2: Required Fields Present
    # All important fields must be found and not empty
    # ══════════════════════════════════════════════════════════════════════════
    required_fields = {
        "certificate_number": cert_number,
        "applicant_name":     applicant_name,
        "father_name":        father_name,
        "annual_income":      annual_income,
        "issue_date":         issue_date,
        "place":              place,
        "issuing_authority":  authority,
        "designation":        designation,
    }

    all_fields_present = True
    for field_name, field_value in required_fields.items():
        if not field_value or field_value.strip() in ("Not Found", ""):
            all_fields_present = False
            issues.append(f"Required field missing: {field_name}")
            fraud_types.append("Missing Required Fields")
            score -= 10  # Deduct 10 per missing field

    checks["required_fields_present"] = all_fields_present

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 3: Income Valid
    # Extract numeric value from income string and validate
    # ══════════════════════════════════════════════════════════════════════════
    # Remove commas and extract digits from income string like "Rs. 80,000"
    income_digits = re.sub(r'[,\s]', '', annual_income)
    income_numbers = re.findall(r'\d+', income_digits)

    if not income_numbers:
        checks["income_valid"] = False
        issues.append("Annual income value is missing or invalid.")
        fraud_types.append("Income Field Issue")
        score -= 15
    else:
        income_value = int(income_numbers[0])
        if income_value <= 0:
            checks["income_valid"] = False
            issues.append("Annual income value is not valid.")
            fraud_types.append("Income Field Issue")
            score -= 15
        else:
            checks["income_valid"] = True

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 4: Issue Date Valid
    # Expected format: DD-MM-YYYY  (e.g. 12-02-2025)
    # ══════════════════════════════════════════════════════════════════════════
    try:
        # strptime will raise ValueError if format doesn't match or date is unreal
        parsed_date = datetime.strptime(issue_date.strip(), "%d-%m-%Y")
        checks["issue_date_valid"] = True
    except (ValueError, AttributeError):
        checks["issue_date_valid"] = False
        issues.append("Issue date format is invalid.")
        fraud_types.append("Date Tampering")
        score -= 15

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 5: Financial Year Valid
    # Expected format: YYYY-YYYY  where second year = first year + 1
    # ══════════════════════════════════════════════════════════════════════════
    fy_pattern = r'(\d{4})-(\d{4})'
    fy_match = re.search(fy_pattern, financial_year)

    if fy_match:
        fy_start = int(fy_match.group(1))
        fy_end   = int(fy_match.group(2))
        if fy_end == fy_start + 1:
            checks["financial_year_valid"] = True
        else:
            checks["financial_year_valid"] = False
            issues.append("Financial year format is invalid.")
            fraud_types.append("Financial Year Issue")
            score -= 10
    else:
        checks["financial_year_valid"] = False
        issues.append("Financial year format is invalid.")
        fraud_types.append("Financial Year Issue")
        score -= 10

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 6: Demo / Sample Text Present
    # OCR text must contain at least one demo marker
    # ══════════════════════════════════════════════════════════════════════════
    ocr_upper = ocr_text.upper()
    demo_keywords = ["HACKATHON DEMO PURPOSE", "DEMO PURPOSE", "SAMPLE"]
    demo_found = any(kw in ocr_upper for kw in demo_keywords)

    if demo_found:
        checks["demo_text_present"] = True
    else:
        checks["demo_text_present"] = False
        issues.append("Demo/sample text is missing.")
        fraud_types.append("Demo Marking Missing")
        score -= 10

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 7: Authority Present
    # Issuing authority and designation must not be missing
    # ══════════════════════════════════════════════════════════════════════════
    authority_ok = (
        authority   not in ("Not Found", "", None) and
        designation not in ("Not Found", "", None)
    )

    if authority_ok:
        checks["authority_present"] = True
    else:
        checks["authority_present"] = False
        issues.append("Issuing authority or designation is missing.")
        fraud_types.append("Missing Authority Details")
        score -= 10

    # ══════════════════════════════════════════════════════════════════════════
    # CHECK 8: Seal Text Present
    # OCR text must contain a seal keyword
    # ══════════════════════════════════════════════════════════════════════════
    seal_keywords = ["SEAL", "OFFICIAL SEAL", "SAMPLE SEAL"]
    seal_found = any(kw in ocr_upper for kw in seal_keywords)

    if seal_found:
        checks["seal_text_present"] = True
    else:
        checks["seal_text_present"] = False
        issues.append("Seal text is missing.")
        fraud_types.append("Missing Seal")
        score -= 10

    # ── Final Score & Status ───────────────────────────────────────────────────
    # Clamp score so it never goes below 0
    score = max(0, score)

    if score >= 80:
        status = "Likely Genuine"
    elif score >= 50:
        status = "Suspicious"
    else:
        status = "Likely Fake"

    # Clean up duplicate fraud types
    fraud_types = list(dict.fromkeys(fraud_types))

    # If no issues, set friendly defaults
    if not issues:
        issues = ["No issues detected."]
    if not fraud_types:
        fraud_types = ["No major fraud detected."]

    return {
        "checks":     checks,
        "issues":     issues,
        "fraud_type": fraud_types,
        "score":      score,
        "status":     status,
    }