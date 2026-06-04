"""
FakeDoc Detector — modules/report_generator.py
Final Explainable Report + Recommendation Generator

This module combines:
- Validation result
- Reference matching result
- Template matching result
- Metadata result
- OCR confidence
- Extracted fields

and produces one clean final report for the result page.
"""


def generate_final_report(
    validation_result,
    template_result,
    metadata_result,
    extracted_fields,
    ocr_confidence=None,
    reference_result=None
):
    """
    Generate final explainable report.

    Parameters:
        validation_result: final validation dictionary
        template_result: template matching result
        metadata_result: metadata checking result
        extracted_fields: extracted OCR fields
        ocr_confidence: OCR confidence in percentage
        reference_result: reference matching result

    Returns:
        report dictionary
    """

    # ── 1. Final Score ─────────────────────────────────────────────
    final_score = validation_result.get("score", 0)

    try:
        final_score = int(final_score)
    except (TypeError, ValueError):
        final_score = 0

    final_score = max(0, min(100, final_score))

    # ── 2. Final Status ────────────────────────────────────────────
    if final_score >= 80:
        final_status = "Likely Genuine"
    elif final_score >= 50:
        final_status = "Suspicious"
    else:
        final_status = "Likely Fake"

    # ── 3. Risk Level ──────────────────────────────────────────────
    if final_score >= 80:
        risk_level = "Low Risk"
    elif final_score >= 50:
        risk_level = "Medium Risk"
    else:
        risk_level = "High Risk"

    # ── 4. OCR Confidence Level ────────────────────────────────────
    if ocr_confidence is None:
        confidence_level = "Unknown"
    elif ocr_confidence >= 80:
        confidence_level = "High"
    elif ocr_confidence >= 60:
        confidence_level = "Medium"
    else:
        confidence_level = "Low"

    # ── 5. Summary ─────────────────────────────────────────────────
    if final_status == "Likely Genuine":
        summary = (
            "The uploaded income certificate appears mostly genuine based on "
            "OCR extraction, field validation, reference matching, template matching, "
            "and metadata checks."
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

    # ── 6. Key Findings ────────────────────────────────────────────
    key_findings = []

    checks = validation_result.get("checks", {})
    meta_checks = metadata_result.get("metadata_checks", {})
    template_status = template_result.get("template_status", "Not Available")

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

    # Reference matching positive finding
    if reference_result:
        reference_status = reference_result.get("reference_status", "Not Available")

        if reference_status == "Matched":
            key_findings.append("Extracted fields match the official reference record.")

    # Template matching positive finding
    if template_status == "Good Match":
        key_findings.append("Document layout matches the reference template.")

    # Metadata positive finding
    if not meta_checks.get("editing_software_detected", False):
        key_findings.append("No editing software detected in metadata.")

    if not key_findings:
        key_findings.append("No positive findings to report.")

    # ── 7. Major Issues ────────────────────────────────────────────
    major_issues = []
    seen_issues = set()

    raw_issues = validation_result.get("issues", [])
    meta_issues = metadata_result.get("metadata_issues", [])
    template_issue_text = template_result.get("template_issue", "")

    all_issues = []

    if isinstance(raw_issues, list):
        all_issues.extend(raw_issues)

    if isinstance(meta_issues, list):
        all_issues.extend(meta_issues)

    # Add reference matching issues
    if reference_result:
        reference_issues = reference_result.get("reference_issues", [])

        if isinstance(reference_issues, list):
            all_issues.extend(reference_issues)

    # Add template issue only if it is not a good match
    if template_status not in ("Good Match", "Template Missing", "Image Error"):
        if template_issue_text:
            all_issues.append(template_issue_text)

    for issue in all_issues:
        if not issue:
            continue

        issue = str(issue).strip()

        # Skip no-issue placeholders
        if issue.lower() in (
            "no issues detected.",
            "no major issues detected."
        ):
            continue

        if issue not in seen_issues:
            seen_issues.add(issue)
            major_issues.append(issue)

    if not major_issues:
        major_issues = ["No major issues detected."]

    # ── 8. Fraud Indicators ────────────────────────────────────────
    fraud_indicators = validation_result.get("fraud_type", [])

    if not isinstance(fraud_indicators, list):
        fraud_indicators = []

    # Add fraud indicators from reference matching
    if reference_result and reference_result.get("mismatched_fields"):
        fraud_indicators.append("Reference Data Mismatch")
        fraud_indicators.append("Text Tampering")

    # Remove duplicates
    fraud_indicators = list(dict.fromkeys(fraud_indicators))

    # Remove generic no-fraud if real fraud types are present
    if len(fraud_indicators) > 1 and "No major fraud detected." in fraud_indicators:
        fraud_indicators.remove("No major fraud detected.")

    if not fraud_indicators:
        fraud_indicators = ["No major fraud detected."]

    # ── 9. Verification Breakdown ─────────────────────────────────
    # Field validation breakdown
    if checks.get("required_fields_present"):
        field_validation_status = "Passed"
    else:
        found_count = sum(
            1 for value in extracted_fields.values()
            if value and value != "Not Found"
        )

        total_fields = len(extracted_fields) or 1

        if found_count >= total_fields * 0.7:
            field_validation_status = "Partial — some fields missing"
        else:
            field_validation_status = "Failed — many fields missing"

    # Reference matching breakdown
    if reference_result:
        reference_match_status = reference_result.get(
            "reference_status",
            "Not Available"
        )
    else:
        reference_match_status = "Not Available"

    # Template matching breakdown
    template_match_status = template_status if template_status else "Not Available"

    # Metadata check breakdown
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

    # OCR quality
    if ocr_confidence is None:
        ocr_quality = "Not Available"
    elif ocr_confidence >= 80:
        ocr_quality = "Good"
    elif ocr_confidence >= 60:
        ocr_quality = "Average"
    else:
        ocr_quality = "Poor"

    verification_breakdown = {
        "ocr_quality": ocr_quality,
        "field_validation": field_validation_status,
        "reference_matching": reference_match_status,
        "template_matching": template_match_status,
        "metadata_check": metadata_check_status,
    }

    # ── 10. Recommendation ────────────────────────────────────────
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

    # ── 11. Final Report Dictionary ───────────────────────────────
    report = {
        "final_score": final_score,
        "final_status": final_status,
        "risk_level": risk_level,
        "confidence_level": confidence_level,
        "summary": summary,
        "key_findings": key_findings,
        "major_issues": major_issues,
        "fraud_indicators": fraud_indicators,
        "verification_breakdown": verification_breakdown,
        "recommendation": recommendation,
    }

    print(
        f"[report_generator] Report generated | "
        f"Score: {final_score} | Status: {final_status} | Risk: {risk_level}"
    )

    return report