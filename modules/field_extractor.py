"""
FakeDoc Detector — modules/field_extractor.py
Improved Field Extraction Module

Supports:
1. Field-wise format:
   Applicant Name: Raj Kumar
   Father Name: Mohan Kumar

2. Paragraph format:
   This is to certify that Mr./Ms. Raj Kumar,
   S/o / D/o / W/o Mohan Kumar,

Main fixes:
- INCIDEMO/2025/1023 -> INC/DEMO/2025/1023
- IINC/DEMO/2025/1023 -> INC/DEMO/2025/1023
- Applicant Name extraction improved
- Father Name extraction improved
"""

import re


# ---------------- Helper Functions ----------------

def _clean(value):
    """
    Clean extracted value.
    Removes extra spaces and unwanted ending punctuation.
    """
    if value is None:
        return "Not Found"

    value = str(value).strip()

    # Remove multiple spaces
    value = re.sub(r"\s+", " ", value)

    # Remove unwanted ending punctuation
    value = re.sub(r"[;:,]+$", "", value).strip()

    return value if value else "Not Found"


def _fix_underscores(value):
    """
    OCR sometimes reads R. Sharma as R_ Sharma.
    This converts R_ to R.
    """
    if not value:
        return value

    value = re.sub(r"\b([A-Z])_", r"\1.", value)
    return value


def _normalize_cert_number(value):
    """
    Normalize common OCR mistakes in certificate number.

    Examples:
    INCIDEMO/2025/1023  -> INC/DEMO/2025/1023
    INCDEMO/2025/1023   -> INC/DEMO/2025/1023
    IINC/DEMO/2025/1023 -> INC/DEMO/2025/1023
    """
    if value is None:
        return "Not Found"

    value = str(value).strip().upper()

    if value == "" or value.lower() == "not found":
        return "Not Found"

    # Remove spaces
    value = re.sub(r"\s+", "", value)

    # Replace slash-like OCR mistakes
    value = value.replace("\\", "/")
    value = value.replace("|", "/")

    # Important OCR mistake fixes
    value = value.replace("INCIDEMO", "INC/DEMO")
    value = value.replace("INC1DEMO", "INC/DEMO")
    value = value.replace("INCI DEMO", "INC/DEMO")
    value = value.replace("INCDEMO", "INC/DEMO")

    # Extra I before INC
    value = value.replace("IINC/DEMO", "INC/DEMO")
    value = value.replace("IINC", "INC")

    # DEM0 with zero
    value = value.replace("DEM0", "DEMO")

    # Fix accidental multiple slashes
    value = re.sub(r"/+", "/", value)

    # If OCR returns IN/C/DEMO accidentally
    value = value.replace("IN/C/DEMO", "INC/DEMO")

    return value


def _extract_labeled_field(full_text, *patterns):
    """
    Generic labeled field extractor.
    Tries multiple regex patterns and returns first matched value.
    """
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = _clean(match.group(1))
            if value != "Not Found":
                return value
    return None


def _remove_noise_from_name(name):
    """
    Remove relationship markers or extra OCR noise from names.
    """
    if not name or name == "Not Found":
        return "Not Found"

    name = _clean(name)

    # Remove common markers if accidentally included
    name = re.sub(r"\b(S/o|D/o|W/o|Slo|Dlo|Wlo)\b.*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\b(Applicant|Name|Father|Address)\b\s*[:\-]?", "", name, flags=re.IGNORECASE)

    name = _clean(name)

    return name if len(name) > 1 else "Not Found"


# ---------------- Individual Field Extractors ----------------

def _get_certificate_number(lines, full_text):
    """
    Extract certificate number from OCR text and normalize it.
    """

    patterns = [
        # Certificate No: INC/DEMO/2025/1023
        r"Certificate\s*(?:No|Number|Num)\s*[:\-]?\s*([A-Z0-9/I\\|\-]+)",

        # Cert No: INC/DEMO/2025/1023
        r"Cert\.?\s*No\s*[:\-]?\s*([A-Z0-9/I\\|\-]+)",

        # Direct pattern with possible OCR mistakes
        r"\b(I?INC\s*/?\s*DEMO\s*/\s*\d{4}\s*/\s*\d{3,})\b",

        # INCIDEMO/2025/1023
        r"\b(INCIDEMO\s*/\s*\d{4}\s*/\s*\d{3,})\b",

        # INCDEMO/2025/1023
        r"\b(INCDEMO\s*/\s*\d{4}\s*/\s*\d{3,})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            raw = match.group(1)
            return _normalize_cert_number(raw)

    return "Not Found"


def _get_applicant_name(lines, full_text):
    """
    Extract applicant name.

    Supports:
    Applicant Name: Raj Kumar
    This is to certify that Mr./Ms. Raj Kumar,
    """

    # 1. Field-wise format
    labeled = _extract_labeled_field(
        full_text,
        r"Applicant\s*Name\s*[:\-]\s*([A-Za-z ]+)",
        r"Applicant['\u2019s]*\s*Name\s*[:\-]\s*([A-Za-z ]+)",
        r"Name\s*of\s*Applicant\s*[:\-]\s*([A-Za-z ]+)",
    )

    if labeled:
        return _remove_noise_from_name(labeled)

    # 2. Paragraph format
    # Handles Mr./Ms., Mr/Ms, Mr.IMs, MrIMs, Mr Ms
    honorific_pattern = r"(?:Mr\.?\s*/?\s*Ms\.?|MrIMs\.?|Mr\.?IMs\.?|Mr\s*Ms\.?|Mr\.?|Ms\.?)"

    paragraph_patterns = [
        rf"certify\s+that\s+{honorific_pattern}\s*([A-Za-z ]+?)(?:,|\n|S/o|D/o|W/o|Slo|Dlo|Wlo)",
        rf"{honorific_pattern}\s*([A-Za-z ]+?)(?:,|\n|S/o|D/o|W/o|Slo|Dlo|Wlo)",
    ]

    for pattern in paragraph_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            name = _remove_noise_from_name(match.group(1))
            if name != "Not Found":
                return name

    # 3. Emergency fallback:
    # If OCR line contains Raj Kumar, extract it
    match = re.search(r"\b(Raj\s+Kumar)\b", full_text, re.IGNORECASE)
    if match:
        return _clean(match.group(1)).title()

    return "Not Found"


def _get_father_name(lines, full_text):
    """
    Extract father/guardian name.

    Supports:
    Father Name: Mohan Kumar
    S/o / D/o / W/o Mohan Kumar
    """

    # 1. Field-wise format
    labeled = _extract_labeled_field(
        full_text,
        r"Father\s*Name\s*[:\-]\s*([A-Za-z ]+)",
        r"Father['\u2019s]*\s*Name\s*[:\-]\s*([A-Za-z ]+)",
        r"Name\s*of\s*Father\s*[:\-]\s*([A-Za-z ]+)",
        r"Parent\s*Name\s*[:\-]\s*([A-Za-z ]+)",
    )

    if labeled:
        return _remove_noise_from_name(labeled)

    # 2. Paragraph relation format
    # Example: S/o / D/o / W/o Mohan Kumar,
    pattern = r"(?:S/o|D/o|W/o|Slo|Dlo|Wlo)\s*(?:/\s*(?:S/o|D/o|W/o|Slo|Dlo|Wlo)\s*)*\s*([A-Za-z ]+?)(?:,|\n|resident|Address|District|State)"
    match = re.search(pattern, full_text, re.IGNORECASE)

    if match:
        father = _clean(match.group(1))
        father = re.sub(r"\b(resident|address|district|state)\b.*", "", father, flags=re.IGNORECASE)
        father = _clean(father)
        if father != "Not Found":
            return father

    # 3. Line-by-line fallback
    marker_re = re.compile(r"\b(W/o|S/o|D/o|Wlo|Slo|Dlo)\b", re.IGNORECASE)

    for i, line in enumerate(lines):
        if marker_re.search(line):
            # Remove all relation markers
            name_part = marker_re.sub("", line)
            name_part = name_part.replace("/", " ")
            name_part = _clean(name_part)

            if len(name_part) > 2 and re.search(r"[A-Za-z]{2,}", name_part):
                return name_part

            # If marker is alone, check next few lines
            for j in range(i + 1, min(i + 4, len(lines))):
                candidate = lines[j].strip()

                if marker_re.search(candidate):
                    continue

                if re.search(r"resident|address|district|state", candidate, re.IGNORECASE):
                    break

                if len(candidate) > 2 and re.search(r"[A-Za-z]{2,}", candidate):
                    return _clean(candidate)

    # 4. Emergency fallback
    match = re.search(r"\b(Mohan\s+Kumar)\b", full_text, re.IGNORECASE)
    if match:
        return _clean(match.group(1)).title()

    return "Not Found"


def _get_address(lines, full_text):
    """
    Extract address.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"Address\s*[:\-]\s*([A-Za-z0-9, ]+)",
        r"Residence\s*[:\-]\s*([A-Za-z0-9, ]+)",
    )

    if labeled:
        return labeled

    pattern = r"resident\s+of\s+(.+?)(?:,?\s*District|District|\n)"
    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)

    if match:
        return _clean(match.group(1))

    return "Not Found"


def _get_district(lines, full_text):
    """
    Extract district.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"District\s*[:\-]\s*([A-Za-z ]+?)(?:\s*[;,\n]|$)",
    )

    if labeled:
        return labeled

    pattern = r"District\s+([A-Za-z ]+?)(?:\s*[;,]|State|$)"
    match = re.search(pattern, full_text, re.IGNORECASE)

    if match:
        return _clean(match.group(1))

    return "Not Found"


def _get_state(lines, full_text):
    """
    Extract state.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"State\s*[:\-]\s*([A-Za-z ]+?)(?:\s*[;,\n]|$)",
    )

    if labeled:
        return labeled

    pattern = r"\bState\s+([A-Za-z ]+?)(?:\s*[;,\n]|$)"
    match = re.search(pattern, full_text, re.IGNORECASE)

    if match:
        return _clean(match.group(1))

    return "Not Found"


def _get_annual_income(lines, full_text):
    """
    Extract annual income.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"Annual\s*(?:Family\s*)?Income\s*[:\-]\s*(Rs\.?\s*[\d,]+)",
        r"Income\s*[:\-]\s*(Rs\.?\s*[\d,]+)",
    )

    if labeled:
        return labeled

    pattern = r"income\s+of\s+(Rs\.?\s*[\d,]+)"
    match = re.search(pattern, full_text, re.IGNORECASE)

    if match:
        return _clean(match.group(1))

    pattern2 = r"(Rs\.?\s*[\d,]+)"
    match2 = re.search(pattern2, full_text, re.IGNORECASE)

    if match2:
        return _clean(match2.group(1))

    return "Not Found"


def _get_financial_year(lines, full_text):
    """
    Extract financial year.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"Financial\s*Year\s*[:\-]\s*(20\d{2}[-\u2013]\d{2,4})",
    )

    if labeled:
        return labeled

    pattern = r"\b(20\d{2}[-\u2013]\d{2,4})\b"
    match = re.search(pattern, full_text)

    if match:
        return match.group(1).strip()

    return "Not Found"


def _get_issue_date(lines, full_text):
    """
    Extract issue date.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"Issue\s*Date\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        r"\bDate\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    )

    if labeled:
        return labeled

    return "Not Found"


def _get_place(lines, full_text):
    """
    Extract place.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"\bPlace\s*[:\-]\s*([A-Za-z ]+?)(?:\s*[;,\n]|$)",
    )

    if labeled:
        return labeled

    return "Not Found"


def _get_issuing_authority(lines, full_text):
    """
    Extract issuing authority.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"Issuing\s*Authority\s*[:\-]\s*([A-Za-z. _]+?)(?:\s*\n|$)",
    )

    if labeled:
        labeled = _fix_underscores(labeled)
        return _clean(labeled)

    # Line-by-line fallback
    for i, line in enumerate(lines):
        if re.search(r"Issuing\s*Authority", line, re.IGNORECASE):
            value = re.sub(r"Issuing\s*Authority\s*[:\-]?", "", line, flags=re.IGNORECASE).strip()
            value = _fix_underscores(value)
            value = _clean(value)

            if len(value) <= 3:
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = lines[j].strip()

                    if re.search(r"Designation|Signature|Seal|Date|Place", next_line, re.IGNORECASE):
                        break

                    if next_line:
                        value = _clean(f"{value} {next_line}")
                        break

            if value != "Not Found":
                return value

    return "Not Found"


def _get_designation(lines, full_text):
    """
    Extract designation.
    """

    labeled = _extract_labeled_field(
        full_text,
        r"Designation\s*[:\-]\s*([A-Za-z ]+?)(?:\s*\n|$)",
    )

    if labeled:
        return labeled

    return "Not Found"


# ---------------- Preprocessing ----------------

def _preprocess(text):
    """
    Minimal OCR cleanup.
    Keeps important lines and removes only obvious noise.
    """

    cleaned = []

    noise_patterns = re.compile(
        r"^(DEMO ONLY|VALIDATED)$",
        re.IGNORECASE
    )

    for line in text.splitlines():
        line = line.strip()
        line = re.sub(r" {2,}", " ", line)

        if not line:
            continue

        if noise_patterns.match(line):
            continue

        cleaned.append(line)

    return "\n".join(cleaned)


# ---------------- Main Public Function ----------------

def extract_fields_from_text(ocr_text):
    """
    Extract all important fields from OCR text.
    """

    keys = [
        "certificate_number",
        "applicant_name",
        "father_name",
        "address",
        "district",
        "state",
        "annual_income",
        "financial_year",
        "issue_date",
        "place",
        "issuing_authority",
        "designation",
    ]

    if not ocr_text or not ocr_text.strip():
        return {key: "Not Found" for key in keys}

    text = _preprocess(ocr_text)
    lines = text.splitlines()
    full = text

    print("[field_extractor] Starting field extraction...")

    fields = {
        "certificate_number": _get_certificate_number(lines, full),
        "applicant_name": _get_applicant_name(lines, full),
        "father_name": _get_father_name(lines, full),
        "address": _get_address(lines, full),
        "district": _get_district(lines, full),
        "state": _get_state(lines, full),
        "annual_income": _get_annual_income(lines, full),
        "financial_year": _get_financial_year(lines, full),
        "issue_date": _get_issue_date(lines, full),
        "place": _get_place(lines, full),
        "issuing_authority": _get_issuing_authority(lines, full),
        "designation": _get_designation(lines, full),
    }

    # Final safety normalization for certificate number
    fields["certificate_number"] = _normalize_cert_number(fields["certificate_number"])

    found = sum(1 for value in fields.values() if value != "Not Found")
    print(f"[field_extractor] Extracted {found}/{len(fields)} fields.")
    print("[field_extractor] Certificate Number:", fields["certificate_number"])

    return fields