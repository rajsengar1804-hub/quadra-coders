# app.py
# FakeDoc Detector
# Flow:
# Home Page → Select Certificate Type → Upload Certificate
# → OCR → Field Extraction → Validation → Reference Matching
# → Metadata → Template Matching → Final Report

import os
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

from modules.pdf_converter import convert_pdf_to_image
from modules.ocr_extractor import extract_text_from_image
from modules.field_extractor import extract_fields_from_text as extract_fields
from modules.validator import validate_certificate
from modules.metadata_checker import check_metadata
from modules.template_matcher import compare_with_template
from modules.reference_matcher import match_with_reference
from modules.report_generator import generate_final_report


# ── App Configuration ──────────────────────────────────────────────────────────
app = Flask(__name__)

UPLOAD_FOLDER = os.path.join("static", "uploads")
PROCESSED_FOLDER = os.path.join("static", "processed")
TEMPLATE_FOLDER = os.path.join("static", "templates_docs")
DATA_FOLDER = "data"

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["PROCESSED_FOLDER"] = PROCESSED_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(TEMPLATE_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)


# ── Helper Functions ───────────────────────────────────────────────────────────

def allowed_file(filename):
    """
    Check whether uploaded file extension is allowed.
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_certificate_type(certificate_type):
    """
    Only allow supported certificate types.
    """
    certificate_type = str(certificate_type).strip().lower()

    allowed_types = ["income", "caste", "degree"]

    if certificate_type not in allowed_types:
        return "income"

    return certificate_type


def get_certificate_display_name(certificate_type):
    """
    Convert certificate type into display name.
    """
    names = {
        "income": "Income Certificate",
        "caste": "Caste Certificate",
        "degree": "Degree Certificate"
    }

    return names.get(certificate_type, "Income Certificate")


def find_template_path(certificate_type="income"):
    """
    Find template based on selected certificate type.

    income → static/templates_docs/income_template.jpeg
    caste  → static/templates_docs/caste_template.jpeg
    degree → static/templates_docs/degree_template.jpeg
    """

    certificate_type = normalize_certificate_type(certificate_type)

    candidates = [
        os.path.join(TEMPLATE_FOLDER, f"{certificate_type}_template.png"),
        os.path.join(TEMPLATE_FOLDER, f"{certificate_type}_template.jpeg"),
        os.path.join(TEMPLATE_FOLDER, f"{certificate_type}_template.jpg"),
    ]

    for path in candidates:
        if os.path.exists(path):
            print(f"[App] Template found: {path}")
            return path

    print(f"[App] WARNING: No template found for {certificate_type}")
    return None


def update_status_from_score(score):
    """
    Convert score into status.
    """
    if score >= 80:
        return "Likely Genuine"
    elif score >= 50:
        return "Suspicious"
    else:
        return "Likely Fake"


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    """
    Home page.
    User selects certificate type here.
    """
    return render_template("index.html", selected_type=None)


@app.route("/check/<certificate_type>", methods=["GET"])
def check_certificate(certificate_type):
    """
    Upload page for selected certificate type.
    Example:
    /check/income
    /check/caste
    /check/degree
    """

    certificate_type = normalize_certificate_type(certificate_type)
    certificate_name = get_certificate_display_name(certificate_type)

    return render_template(
        "index.html",
        selected_type=certificate_type,
        certificate_name=certificate_name
    )


@app.route("/upload", methods=["POST"])
def upload_file():

    # ── Step 0: Get selected certificate type ──────────────────────────────────
    certificate_type = request.form.get("certificate_type", "income")
    certificate_type = normalize_certificate_type(certificate_type)
    certificate_name = get_certificate_display_name(certificate_type)

    # ── Step 1: Validate uploaded file ─────────────────────────────────────────
    if "file" not in request.files:
        return render_template(
            "index.html",
            selected_type=certificate_type,
            certificate_name=certificate_name,
            error="No file part in the request."
        )

    file = request.files["file"]

    if file.filename == "":
        return render_template(
            "index.html",
            selected_type=certificate_type,
            certificate_name=certificate_name,
            error="No file selected."
        )

    if not allowed_file(file.filename):
        return render_template(
            "index.html",
            selected_type=certificate_type,
            certificate_name=certificate_name,
            error="Invalid file type. Please upload PDF, PNG, JPG, or JPEG."
        )

    # ── Step 2: Save uploaded file ─────────────────────────────────────────────
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)

    print(f"[Upload] Saved: {file_path}")
    print(f"[Upload] Certificate Type: {certificate_type}")

    file_extension = filename.rsplit(".", 1)[1].lower()

    # ── Step 3: Convert PDF to image if needed ─────────────────────────────────
    if file_extension == "pdf":
        processed_image_path = convert_pdf_to_image(
            file_path,
            app.config["PROCESSED_FOLDER"]
        )

        if processed_image_path is None:
            return render_template(
                "index.html",
                selected_type=certificate_type,
                certificate_name=certificate_name,
                error="PDF conversion failed."
            )
    else:
        processed_image_path = file_path

    # ── Step 4: OCR ────────────────────────────────────────────────────────────
    print("[App] Running OCR...")

    ocr_result = extract_text_from_image(processed_image_path)
    extracted_text = ocr_result.get("text", "")

    ocr_confidence_raw = ocr_result.get("confidence", 0.0)
    ocr_confidence = round(ocr_confidence_raw * 100, 2)

    ocr_status = "Text extracted successfully." if extracted_text else "No text detected."

    # ── Step 5: Field Extraction ───────────────────────────────────────────────
    print("[App] Extracting fields...")

    extracted_fields = extract_fields(extracted_text)

    # ── Step 6: Validation ─────────────────────────────────────────────────────
    print("[App] Validating certificate...")

    validation_result = validate_certificate(extracted_fields, extracted_text)

    final_score = validation_result.get("score", 0)
    final_issues = list(validation_result.get("issues", []))
    final_frauds = list(validation_result.get("fraud_type", []))

    # ── Step 7: Reference Field Matching ───────────────────────────────────────
    print("[App] Running reference field matching...")

    reference_result = match_with_reference(
        extracted_fields,
        certificate_type=certificate_type
    )

    if reference_result:
        reference_status = reference_result.get("reference_status", "")

        if not reference_result.get("reference_found"):
            final_score -= 20

        elif reference_status == "Partial Match":
            final_score -= 15

        elif reference_status == "Mismatch":
            final_score -= 30

        reference_issues = reference_result.get("reference_issues", [])

        if reference_issues:
            if "No issues detected." in final_issues:
                final_issues.remove("No issues detected.")
            final_issues.extend(reference_issues)

        if reference_result.get("mismatched_fields"):
            if "Reference Data Mismatch" not in final_frauds:
                final_frauds.append("Reference Data Mismatch")
            if "Text Tampering" not in final_frauds:
                final_frauds.append("Text Tampering")

    # ── Step 8: Metadata Checking ──────────────────────────────────────────────
    print("[App] Checking metadata...")

    metadata_result = check_metadata(file_path, extracted_fields)

    meta_deduction = metadata_result.get("metadata_score_deduction", 0)
    final_score -= meta_deduction

    metadata_issues = metadata_result.get("metadata_issues", [])

    if metadata_issues:
        if "No issues detected." in final_issues:
            final_issues.remove("No issues detected.")
        final_issues.extend(metadata_issues)

    metadata_checks = metadata_result.get("metadata_checks", {})

    if metadata_checks.get("editing_software_detected"):
        if "Metadata Manipulation" not in final_frauds:
            final_frauds.append("Metadata Manipulation")

    # ── Step 9: Template Matching ──────────────────────────────────────────────
    print("[App] Running template matching...")

    template_path = find_template_path(certificate_type)
    template_result = compare_with_template(processed_image_path, template_path)

    template_status = template_result.get("template_status", "")

    if template_status == "Partial Match":
        final_score -= 10
    elif template_status == "Layout Mismatch":
        final_score -= 20
    elif template_status in ("Template Missing", "Image Error"):
        final_score -= 10

    if template_status != "Good Match":
        if "No issues detected." in final_issues:
            final_issues.remove("No issues detected.")
        final_issues.append(
            f"Template: {template_result.get('template_issue', 'Template issue detected.')}"
        )

    # ── Step 10: Final Score and Status ────────────────────────────────────────
    final_score = max(0, min(100, final_score))
    final_status = update_status_from_score(final_score)

    final_issues = list(dict.fromkeys(final_issues))
    final_frauds = list(dict.fromkeys(final_frauds))

    if not final_issues:
        final_issues = ["No issues detected."]

    if not final_frauds:
        final_frauds = ["No major fraud detected."]

    if "No major fraud detected." in final_frauds and len(final_frauds) > 1:
        final_frauds.remove("No major fraud detected.")

    final_result = {
        "score": final_score,
        "status": final_status,
        "checks": validation_result.get("checks", {}),
        "issues": final_issues,
        "fraud_type": final_frauds,
    }

    print(f"[App] Final Score: {final_score} | Status: {final_status}")

    # ── Step 11: Generate Final Explainable Report ─────────────────────────────
    print("[App] Generating final report...")

    final_report = generate_final_report(
        validation_result=final_result,
        template_result=template_result,
        metadata_result=metadata_result,
        extracted_fields=extracted_fields,
        ocr_confidence=ocr_confidence,
        reference_result=reference_result
    )

    # ── Step 12: Render Result ─────────────────────────────────────────────────
    return render_template(
        "result.html",
        filename=filename,
        file_path=file_path.replace("\\", "/"),
        file_extension=file_extension.upper(),
        processed_image_path=processed_image_path.replace("\\", "/"),
        extracted_text=extracted_text,
        ocr_confidence=ocr_confidence,
        ocr_status=ocr_status,
        extracted_fields=extracted_fields,
        validation_result=final_result,
        metadata_result=metadata_result,
        template_result=template_result,
        reference_result=reference_result,
        final_report=final_report,
        certificate_type=certificate_type,
        certificate_name=certificate_name,
        success_message=f"{certificate_name} uploaded and processed successfully!",
    )


if __name__ == "__main__":
    app.run(debug=True)