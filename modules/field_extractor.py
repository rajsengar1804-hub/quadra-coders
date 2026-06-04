"""
FakeDoc Detector — modules/field_extractor.py
Module 3: Field Extraction (v3 — dual-format support)

Supports two certificate formats:
  1. Field-label format:  'Applicant Name: Raj Kumar'
  2. Paragraph format:    'This is to certify that Mr./Ms. Raj Kumar, S/o Mohan Kumar'

Key improvements over v2:
  • Labeled-field extractors for applicant_name and father_name (tried first)
  • Certificate number: handles IINC/... (double-I) → INC/...
  • All fields: labeled format tried before paragraph/regex fallback
  • OCR fixes: R_ → R., underscore-as-period, semicolon/comma separators
"""

import re


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _clean(value):
    """
    Remove trailing punctuation (semicolons, commas, colons, underscores)
    and strip whitespace from an extracted value.
    Note: trailing dots on name initials (e.g. 'R.') are preserved.
    """
    value = value.strip()
    # Strip trailing semicolons, commas, colons, underscores
    value = re.sub(r"[;:,_]+$", "", value).strip()
    # Strip a trailing dot ONLY if it is NOT a name initial (single capital + dot)
    if value.endswith(".") and not re.search(r"\b[A-Z]\.$", value):
        value = value[:-1].strip()
    return value


def _fix_underscores(value):
    """
    OCR sometimes reads a period as an underscore.
    Convert patterns like 'R_' or 'R_ Sharma' so the dot is restored.
    Examples:
        'R_'        → 'R.'
        'R_ Sharma' → 'R. Sharma'
    """
    return re.sub(r"\b([A-Z])_", r"\1.", value)


def _normalize_cert_number(value):
    """
    Fix common OCR misreads of the certificate number:
      INCIDEMO/...  -> INC/DEMO/...   slash misread as letter I
      INCDEMO/...   -> INC/DEMO/...   slash omitted entirely
      IINC/...      -> INC/...        stray leading double-I
      INC/DEMO/...  -> unchanged      already correct
    """
    # Slash misread as 'I': INCIDEMO → INC/DEMO
    value = re.sub(r"INCIDEMO", "INC/DEMO", value, flags=re.IGNORECASE)
    # Slash omitted: INCDEMO → INC/DEMO
    value = re.sub(r"INCDEMO", "INC/DEMO", value, flags=re.IGNORECASE)
    # Stray leading double-I: IINC/ → INC/
    value = re.sub(r"^II(?=NC/)", "I", value)
    return value.strip()


def _extract_labeled_field(full_text, *label_patterns):
    """
    Generic helper: try each label pattern against the full text.
    Each pattern should capture the field value in group 1.
    Returns the cleaned value of the first match, or None.

    Label patterns should match from the label through the colon/separator
    to the value, stopping at end-of-line.

    Example patterns:
        r"Applicant\s+Name\s*[:\-]\s*(.+)"
    """
    for pattern in label_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = _clean(match.group(1).strip())
            if value:
                return value
    return None


# ─── Individual Field Extractors ─────────────────────────────────────────────

def _get_certificate_number(lines, full_text):
    """
    Labeled:   'Certificate No: INC/DEMO/2025/1023'
    Also handles OCR variants: INCIDEMO, IINC/DEMO.
    Captures alphanumeric + slash characters (the full cert number token).
    """
    pattern = (
        r"(?:Certificate\s*(?:No|Number|Num)|Cert\.?\s*No)"
        r"[:\.\s]+([A-Z0-9/Il\-]+)"
    )
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        raw = match.group(1).strip()
        return _normalize_cert_number(raw)
    return "Not Found"


def _get_applicant_name(lines, full_text):
    """
    Priority 1 — Labeled format:
        'Applicant Name: Raj Kumar'
        'Applicant's Name: Raj Kumar'
        'Name of Applicant: Raj Kumar'

    Priority 2 — Paragraph format:
        'certify that Mr./Ms. Raj Kumar,'
        honorific immediately followed by a name
    """
    # --- Priority 1: labeled field ---
    labeled = _extract_labeled_field(
        full_text,
        r"Applicant['\u2019s]*\s+Name\s*[:\-]\s*(.+)",
        r"Name\s+of\s+Applicant\s*[:\-]\s*(.+)",
        r"^Name\s*[:\-]\s*(.+)",          # bare 'Name:' label at line start
    )
    if labeled and len(labeled) > 2:
        return labeled

    # --- Priority 2: paragraph format ---
    honorific = r"(?:Mr\.?/?Ms\.?|Mrs\.?|MrIMs\.?|Mr\s+Ms\.?|Shri\.?|Smt\.?|Mr|Ms)"

    # After 'certify that', skip honorific, capture full name (greedy up to comma/newline)
    # Use greedy {1,40} (no ?) so the full multi-word name is captured, not just the last word.
    pattern = (
        r"certify\s+that\s+" + honorific +
        r"[\s,./]*([A-Za-z][A-Za-z ]{1,40})(?=\s*[,\n]|$)"
    )
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        name = _clean(match.group(1).strip())
        if len(name) > 2:
            return name

    # Fallback: honorific followed directly by a full name (greedy)
    pattern2 = honorific + r"[\s,./]+([A-Za-z][A-Za-z ]{1,40})(?=\s*[,\n]|$)"
    match2 = re.search(pattern2, full_text, re.IGNORECASE)
    if match2:
        return _clean(match2.group(1).strip())

    return "Not Found"


def _get_father_name(lines, full_text):
    """
    Priority 1 — Labeled format:
        'Father Name: Mohan Kumar'
        'Father's Name: Mohan Kumar'
        'Name of Father: Mohan Kumar'

    Priority 2 — Paragraph format (S/o, D/o, W/o and OCR variants):
        'Wlo Mohan Kumar;'
        OCR may split the marker onto its own line; next non-empty line is the name.
    """
    # --- Priority 1: labeled field ---
    labeled = _extract_labeled_field(
        full_text,
        r"Father['\u2019s]*\s+Name\s*[:\-]\s*(.+)",
        r"Name\s+of\s+Father\s*[:\-]\s*(.+)",
        r"Parent['\u2019s]*\s+Name\s*[:\-]\s*(.+)",   # some certs say 'Parent Name'
    )
    if labeled and len(labeled) > 2:
        return labeled

    # --- Priority 2: relation-marker format ---
    marker_re = re.compile(
        r"\b(W/o|S/o|D/o|Wlo|Slo|Dlo)\b",
        re.IGNORECASE
    )

    for i, line in enumerate(lines):
        if not marker_re.search(line):
            continue

        # Remove the marker (and anything before it) to isolate the name part
        name_part = marker_re.sub("", line).strip().strip("/,; ")

        # If a real name follows the marker on the same line, use it
        if len(name_part) > 2 and re.search(r"[A-Za-z]{2,}", name_part):
            return _clean(name_part)

        # Marker is alone on this line → check the next non-empty line
        for j in range(i + 1, min(i + 4, len(lines))):
            candidate = lines[j].strip()
            if marker_re.search(candidate):        # skip another bare marker
                continue
            if len(candidate) < 2 or not re.search(r"[A-Za-z]{2,}", candidate):
                continue
            return _clean(candidate)

    return "Not Found"


def _get_address(lines, full_text):
    """
    Labeled:   'Address: Gole Ka Mandir, Gwalior'
    Paragraph: 'resident of Gole Ka Mandir, Gwalior,'
    """
    labeled = _extract_labeled_field(
        full_text,
        r"Address\s*[:\-]\s*(.+)",
        r"Residence\s*[:\-]\s*(.+)",
    )
    if labeled:
        return labeled

    pattern = r"resident\s+of\s+(.+)"
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        return _clean(match.group(1))

    return "Not Found"


def _get_district(lines, full_text):
    """
    Labeled:   'District: Gwalior'
    Inline:    'District Gwalior; State Madhya Pradesh;'
    Separator between District value and next field can be comma, semicolon, or 'State'.
    """
    labeled = _extract_labeled_field(
        full_text,
        r"District\s*[:\-]\s*([A-Za-z ]+?)(?:\s*[;,\n]|$)",
    )
    if labeled:
        return labeled

    # Inline format (no colon): 'District Gwalior;'
    pattern = r"District\s+([A-Za-z ]+?)\s*(?:[;,]|State|$)"
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        return _clean(match.group(1))

    return "Not Found"


def _get_state(lines, full_text):
    """
    Labeled:   'State: Madhya Pradesh'
    Inline:    'State Madhya Pradesh;'
    """
    labeled = _extract_labeled_field(
        full_text,
        r"State\s*[:\-]\s*([A-Za-z ]+?)(?:\s*[;,\n]|$)",
    )
    if labeled:
        return labeled

    # Inline format (no colon)
    pattern = r"\bState\s+([A-Za-z ]+?)(?:\s*[;,\n]|$)"
    match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
    if match:
        return _clean(match.group(1))

    return "Not Found"


def _get_annual_income(lines, full_text):
    """
    Labeled:   'Annual Income: Rs. 80,000'
    Paragraph: 'annual family income of Rs. 80,000'
    Fallback:  any 'Rs.' amount in the text
    """
    labeled = _extract_labeled_field(
        full_text,
        r"Annual\s+(?:Family\s+)?Income\s*[:\-]\s*(Rs\.?\s*[\d,]+)",
        r"Income\s*[:\-]\s*(Rs\.?\s*[\d,]+)",
    )
    if labeled:
        return labeled

    pattern = r"income\s+of\s+(Rs\.?\s*[\d,]+)"
    match = re.search(pattern, full_text, re.IGNORECASE)
    if match:
        return _clean(match.group(1))

    # Last-resort fallback
    pattern2 = r"(Rs\.?\s*[\d,]+)"
    match2 = re.search(pattern2, full_text, re.IGNORECASE)
    if match2:
        return _clean(match2.group(1))

    return "Not Found"


def _get_financial_year(lines, full_text):
    """
    Match: '2024-2025' or '2023-24'
    Labeled:  'Financial Year: 2024-2025'
    """
    labeled = _extract_labeled_field(
        full_text,
        r"Financial\s+Year\s*[:\-]\s*(20\d{2}[-\u2013]\d{2,4})",
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
    Labeled:   'Issue Date: 12-02-2025'
    Fallback:  any 'Date:' label followed by a date
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
    Labeled:   'Place: Gwalior'
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
    Labeled:   'Issuing Authority: R. Sharma'

    OCR problems:
      - Name may be split across two lines: 'Issuing Authority: R_'  /  'Sharma'
      - Underscore may stand in for period: 'R_' → 'R.'

    Logic:
      1. Find the line containing 'Issuing Authority'.
      2. Extract value after the colon; fix underscores.
      3. If result is short (≤4 chars), join next non-empty / non-noise line.
    """
    for i, line in enumerate(lines):
        if not re.search(r"Issuing\s*Authority", line, re.IGNORECASE):
            continue

        colon_match = re.search(r"Issuing\s*Authority[:\s]+(.+)", line, re.IGNORECASE)
        value = colon_match.group(1).strip() if colon_match else ""

        value = _fix_underscores(value)
        value = _clean(value)

        # Name looks incomplete — try to grab the continuation on the next line
        if len(value) <= 4:
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                if re.search(
                    r"Designation|Signature|Seal|Date|Place", next_line, re.IGNORECASE
                ):
                    break
                next_line = _fix_underscores(next_line)
                value = _clean(f"{value} {next_line}")
                break

        if value:
            return value

    return "Not Found"


def _get_designation(lines, full_text):
    """
    Labeled:   'Designation: Demo Revenue Officer'
    """
    labeled = _extract_labeled_field(
        full_text,
        r"Designation\s*[:\-]\s*([A-Za-z ]+?)(?:\s*\n|$)",
    )
    if labeled:
        return labeled

    return "Not Found"


# ─── Preprocessing ───────────────────────────────────────────────────────────

def _preprocess(text):
    """
    Minimal OCR cleanup:
      - Strip extra whitespace within each line.
      - Preserve line breaks (required for multi-line logic).
      - Drop lines that are clearly watermark / noise.
    """
    noise_patterns = re.compile(
        r"^(SAMPLE SEAL|DEMO ONLY|SAMPLE INCOME CERTIFICATE|"
        r"For Hackathon Demo Purpose Only|Signature\s*:?\s*_*|"
        r"Official Seal.*)$",
        re.IGNORECASE
    )
    cleaned = []
    for line in text.splitlines():
        line = re.sub(r" {2,}", " ", line.strip())
        if noise_patterns.match(line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


# ─── Main Public Function ─────────────────────────────────────────────────────

def extract_fields_from_text(ocr_text):
    """
    Extract all 12 certificate fields from raw OCR text.

    Supports two certificate formats:
      1. Field-label format  — 'Applicant Name: Raj Kumar'
      2. Paragraph format    — 'certify that Mr. Raj Kumar, S/o Mohan Kumar'

    Args:
        ocr_text (str): Raw string from EasyOCR.

    Returns:
        dict: 12-key dictionary; missing fields are 'Not Found'.
    """
    all_keys = [
        "certificate_number", "applicant_name", "father_name",
        "address", "district", "state", "annual_income",
        "financial_year", "issue_date", "place",
        "issuing_authority", "designation",
    ]

    if not ocr_text or not ocr_text.strip():
        return {key: "Not Found" for key in all_keys}

    # Step 1: Clean the text
    text  = _preprocess(ocr_text)
    lines = text.splitlines()   # line list used by multi-line extractors
    full  = text                # full string used by single-pattern extractors

    print("[field_extractor] Starting field extraction...")

    # Step 2: Extract each field
    fields = {
        "certificate_number": _get_certificate_number(lines, full),
        "applicant_name":     _get_applicant_name(lines, full),
        "father_name":        _get_father_name(lines, full),
        "address":            _get_address(lines, full),
        "district":           _get_district(lines, full),
        "state":              _get_state(lines, full),
        "annual_income":      _get_annual_income(lines, full),
        "financial_year":     _get_financial_year(lines, full),
        "issue_date":         _get_issue_date(lines, full),
        "place":              _get_place(lines, full),
        "issuing_authority":  _get_issuing_authority(lines, full),
        "designation":        _get_designation(lines, full),
    }

    found = sum(1 for v in fields.values() if v != "Not Found")
    print(f"[field_extractor] Extracted {found}/{len(fields)} fields.")

    return fields