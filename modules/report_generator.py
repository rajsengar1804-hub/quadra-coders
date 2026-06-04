"""
FakeDoc Detector — modules/report_generator.py
Module 8: Final Explainable Report + Recommendation Generator

Aggregates results from all previous modules and produces a
clean, human-readable final report dictionary for the result page.
"""


def generate_final_report(
    validation_result,
    template_result,
    metadata_result,
    extracted_fields,
    ocr_confidence=None
):
    """
    Generate a final explainable report from all module outputs.

    Args:
        validation_result (dict): Output from validator.py (score, status, checks, issues, fraud_type).
        template_result   (dict): Output from template_matcher.py (similarity_score, template_status, template_issue).
        metadata_result   (dict): Output from metadata_checker.py (metadata, metadata_checks, metadata_issues, metadata_score_deduction).
        extracted_fields  (dict): Output from field_extractor.py (12 certificate fields).
        ocr_confidence    (float|None): Average OCR confidence as a 0–100 float (optional).

    Returns:
        dict: Complete report with score, status, risk, findings, issues,
              indicators, recommendation, and verification breakdown.
    """

    # ── 1. Final Score ─────────────────────────────────────────────────────────
    # Use .get() with a fallback of 0 to avoid KeyError if key is missing
    final_score = validation_result.get("score", 0)

    # Clamp just in case
    final_score = max(0, min(100, final_score))

    # ── 2. Final Status ────────────────────────────────────────────────────────
    if final_score >= 80:
        final_status = "Likely Genuine"
    elif final_score >= 50:
        final_status = "Suspicious"
    else:
        final_status = "Likely Fake"

    # ── 3. Risk Level ──────────────────────────────────────────────────────────
    if final_score >= 80:
        risk_level = "Low Risk"
    elif final_score >= 50:
        risk_level = "Medium Risk"
    else:
        risk_level = "High Risk"

    # ── 4. Confidence Level ────────────────────────────────────────────────────
    # ocr_confidence is expected as a 0–100 float (already multiplied in app.py)
    if ocr_confidence is None:
        confidence_level = "Unknown"
    elif ocr_confidence >= 80:
        confidence_level = "High"
    elif ocr_confidence >= 60:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # ── 5. Summary Text ────────────────────────────────────────────────────────
    if final_status == "Likely Genuine":
        summary = (
            "The uploaded income certificate appears mostly genuine based on "
            "OCR extraction, field validation, template matching, and metadata checks."
        )
    elif final_status == "Suspicious":
        summary = (
            "The uploaded income certificate has some suspicious indicators. "
            "Manual verification is recommended before accepting the document."
        )
    else:
        summary = (
            "The uploaded income certificate has multiple strong fraud indicators "
            "and should not be accepted without strict manual verification."
        )

    # ── 6. Key Findings (positive results) ────────────────────────────────────
    key_findings = []

    # Pull the per-check booleans safely
    checks = validation_result.get("checks", {})
    meta_checks = metadata_result.get("metadata_checks", {})
    template_status = template_result.get("template_status", "")

    if checks.get("certificate_number_valid"):
        key_findings.append("Certificate number format is valid.")

    if checks.get("required_fields_present"):
        key_findings.append("Required certificate fields are present.")

    if checks.get("income_valid"):
        key_findings.append("Annual income value is valid.")

    if checks.get("issue_date_valid"):
        key_findings.append("Issue date format is valid.")

    if checks.get("financial_year_valid"):
        key_findings.append("Financial year format is valid.")

    if checks.get("authority_present"):
        key_findings.append("Issuing authority name is present.")

    if checks.get("seal_text_present"):
        key_findings.append("Official seal text is present.")

    if template_status == "Good Match":
        key_findings.append("Document layout matches the reference template.")

    if not meta_checks.get("editing_software_detected", False):
        key_findings.append("No editing software detected in metadata.")

    # Fallback if nothing positive was found
    if not key_findings:
        key_findings.append("No positive findings to report.")

    # ── 7. Major Issues ────────────────────────────────────────────────────────
    # Collect from validation issues + metadata issues + template issues
    # Use a set to avoid duplicates, then convert back to list
    seen_issues = set()
    major_issues = []

    raw_issues = validation_result.get("issues", [])
    meta_issues = metadata_result.get("metadata_issues", [])
    template_issue_text = template_result.get("template_issue", "")

    all_issue_sources = raw_issues + meta_issues

    # Add template issue only if it signals a real problem
    if template_status not in ("Good Match", "Template Missing", "Image Error"):
        if template_issue_text:
            all_issue_sources.append(template_issue_text)

    for issue in all_issue_sources:
        # Skip the "no issues" placeholder
        if issue.lower() in ("no issues detected.", "no major issues detected."):
            continue
        normalized = issue.strip()
        if normalized and normalized not in seen_issues:
            seen_issues.add(normalized)
            major_issues.append(normalized)

    if not major_issues:
        major_issues = ["No major issues detected."]

    # ── 8. Fraud Indicators ────────────────────────────────────────────────────
    raw_frauds = validation_result.get("fraud_type", [])
    fraud_indicators = list(dict.fromkeys(raw_frauds))  # remove duplicates, preserve order

    # Remove the generic "no fraud" placeholder if real fraud types exist
    if len(fraud_indicators) > 1 and "No major fraud detected." in fraud_indicators:
        fraud_indicators.remove("No major fraud detected.")

    if not fraud_indicators:
        fraud_indicators = ["No major fraud detected."]

    # ── 9. Verification Breakdown ──────────────────────────────────────────────
    # Field Validation
    if checks.get("required_fields_present"):
        field_validation_status = "Passed"
    else:
        # Count how many of the 12 fields were actually found
        found_count = sum(
            1 for v in extracted_fields.values()
            if v and v != "Not Found"
        )
        total = len(extracted_fields) or 1
        if found_count >= total * 0.7:
            field_validation_status = "Partial — some fields missing"
        else:
            field_validation_status = "Failed — many fields missing"

    # Template Matching — use the status string directly
    template_match_status = template_status if template_status else "Not Available"

    # Metadata Check
    editing_detected = meta_checks.get("editing_software_detected", False)
    creation_missing = not meta_checks.get("creation_date_found", True)
    score_deduction = metadata_result.get("metadata_score_deduction", 0)

    if editing_detected:
        metadata_check_status = "Suspicious — editing software found"
    elif score_deduction > 10:
        metadata_check_status = "Warning — multiple metadata issues"
    elif creation_missing or score_deduction > 0:
        metadata_check_status = "Minor Warning — creation date missing"
    else:
        metadata_check_status = "Passed"

    # OCR Quality
    if ocr_confidence is None:
        ocr_quality = "Not Available"
    elif ocr_confidence >= 80:
        ocr_quality = "Good"
    elif ocr_confidence >= 60:
        ocr_quality = "Average"
    else:
        ocr_quality = "Poor"

    verification_breakdown = {
        "ocr_quality":        ocr_quality,
        "field_validation":   field_validation_status,
        "template_matching":  template_match_status,
        "metadata_check":     metadata_check_status,
    }

    # ── 10. Recommendation ────────────────────────────────────────────────────
    if final_score >= 80:
        recommendation = (
            "Document can be considered valid for demo verification. "
            "Manual verification is still recommended for real-world use."
        )
    elif final_score >= 50:
        recommendation = (
            "Manual verification is required because some suspicious indicators were found. "
            "Do not accept the document without further review."
        )
    else:
        recommendation = (
            "Document should be rejected or sent for strict manual verification "
            "due to multiple fraud indicators."
        )

    # ── Assemble and return ────────────────────────────────────────────────────
    report = {
        "final_score":             final_score,
        "final_status":            final_status,
        "risk_level":              risk_level,
        "confidence_level":        confidence_level,
        "summary":                 summary,
        "key_findings":            key_findings,
        "major_issues":            major_issues,
        "fraud_indicators":        fraud_indicators,
        "verification_breakdown":  verification_breakdown,
        "recommendation":          recommendation,
    }

    print(f"[report_generator] Report generated | Score: {final_score} | Status: {final_status} | Risk: {risk_level}")
    return report