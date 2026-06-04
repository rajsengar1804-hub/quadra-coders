# app.py
# Main Flask application for FakeDoc Detector.
# Pipeline: Upload → PDF Convert → OCR → Fields → Validation
#           → Metadata Check → Template Match → Final Score → Report → Result

import os
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

from modules.pdf_converter    import convert_pdf_to_image
from modules.ocr_extractor    import extract_text_from_image
from modules.field_extractor  import extract_fields_from_text as extract_fields
from modules.validator        import validate_certificate
from modules.metadata_checker import check_metadata
from modules.template_matcher import compare_with_template
from modules.report_generator import generate_final_report      # ← NEW

# ── App Configuration ──────────────────────────────────────────────────────────
app = Flask(__name__)

UPLOAD_FOLDER    = os.path.join('static', 'uploads')
PROCESSED_FOLDER = os.path.join('static', 'processed')
TEMPLATE_FOLDER  = os.path.join('static', 'templates_docs')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER']    = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

os.makedirs(UPLOAD_FOLDER,    exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(TEMPLATE_FOLDER,  exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def find_template_path():
    """Find the reference template image in templates_docs folder."""
    candidates = [
        os.path.join(TEMPLATE_FOLDER, 'income_template.png'),
        os.path.join(TEMPLATE_FOLDER, 'income_template.jpeg'),
        os.path.join(TEMPLATE_FOLDER, 'income_template.jpg'),
    ]
    for path in candidates:
        if os.path.exists(path):
            print(f"[App] Template found: {path}")
            return path
    print("[App] WARNING: No template image found.")
    return None


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():

    # ── Step 0: Validate request ───────────────────────────────────────────────
    if 'file' not in request.files:
        return render_template('index.html', error="No file part in the request.")

    file = request.files['file']

    if file.filename == '':
        return render_template('index.html', error="No file selected.")

    if not allowed_file(file.filename):
        return render_template('index.html', error="Invalid file type. Please upload PDF, PNG, JPG, or JPEG.")

    # ── Step 1: Save uploaded file ─────────────────────────────────────────────
    filename  = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    print(f"[Upload] Saved: {file_path}")

    file_extension = filename.rsplit('.', 1)[1].lower()

    # ── Step 2: Convert PDF to image if needed ─────────────────────────────────
    if file_extension == 'pdf':
        processed_image_path = convert_pdf_to_image(file_path, app.config['PROCESSED_FOLDER'])
        if processed_image_path is None:
            return render_template('index.html', error="PDF conversion failed.")
    else:
        processed_image_path = file_path

    # ── Step 3: OCR ────────────────────────────────────────────────────────────
    print("[App] Running OCR...")
    ocr_result     = extract_text_from_image(processed_image_path)
    extracted_text = ocr_result.get("text", "")
    # Keep raw 0–1 value for report_generator; multiply by 100 for display
    ocr_confidence_raw  = ocr_result.get("confidence", 0.0)
    ocr_confidence      = round(ocr_confidence_raw * 100, 2)   # e.g. 87.34
    ocr_status          = "Text extracted successfully." if extracted_text else "No text detected."

    # ── Step 4: Field Extraction ───────────────────────────────────────────────
    print("[App] Extracting fields...")
    extracted_fields = extract_fields(extracted_text)

    # ── Step 5: Validation ─────────────────────────────────────────────────────
    print("[App] Validating certificate...")
    validation_result = validate_certificate(extracted_fields, extracted_text)

    # Start building the final score from validation score
    final_score  = validation_result["score"]
    final_issues = list(validation_result["issues"])
    final_frauds = list(validation_result["fraud_type"])

    # ── Step 6: Metadata Checking ──────────────────────────────────────────────
    # Use original file_path (not processed image) for metadata
    print("[App] Checking metadata...")
    metadata_result = check_metadata(file_path, extracted_fields)

    # Deduct metadata score
    meta_deduction = metadata_result["metadata_score_deduction"]
    final_score   -= meta_deduction

    # Add metadata issues to final issues
    if metadata_result["metadata_issues"]:
        if "No issues detected." in final_issues:
            final_issues.remove("No issues detected.")
        final_issues.extend(metadata_result["metadata_issues"])

    # Add fraud type if editing software was found
    if metadata_result["metadata_checks"].get("editing_software_detected"):
        if "Metadata Manipulation" not in final_frauds:
            final_frauds.append("Metadata Manipulation")

    # ── Step 7: Template Matching ──────────────────────────────────────────────
    print("[App] Running template matching...")
    template_path   = find_template_path()
    template_result = compare_with_template(processed_image_path, template_path)

    template_status = template_result["template_status"]

    if template_status == "Partial Match":
        final_score -= 10
    elif template_status == "Layout Mismatch":
        final_score -= 20
    elif template_status in ("Template Missing", "Image Error"):
        final_score -= 10

    if template_status != "Good Match":
        if "No issues detected." in final_issues:
            final_issues.remove("No issues detected.")
        final_issues.append(f"Template: {template_result['template_issue']}")

    # ── Step 8: Final Score and Status ────────────────────────────────────────
    final_score = max(0, min(100, final_score))

    if final_score >= 80:
        final_status = "Likely Genuine"
    elif final_score >= 50:
        final_status = "Suspicious"
    else:
        final_status = "Likely Fake"

    # Clean up fraud types and issues
    final_frauds = list(dict.fromkeys(final_frauds))   # remove duplicates
    if not final_issues:
        final_issues = ["No issues detected."]
    if "No major fraud detected." in final_frauds and len(final_frauds) > 1:
        final_frauds.remove("No major fraud detected.")

    # Build final combined result
    final_result = {
        "score":      final_score,
        "status":     final_status,
        "checks":     validation_result["checks"],
        "issues":     final_issues,
        "fraud_type": final_frauds,
    }

    print(f"[App] Final Score: {final_score} | Status: {final_status}")

    # ── Step 9: Generate Final Explainable Report ──────────────────────────────
    print("[App] Generating final report...")
    final_report = generate_final_report(
        validation_result = final_result,       # pass the combined/updated result
        template_result   = template_result,
        metadata_result   = metadata_result,
        extracted_fields  = extracted_fields,
        ocr_confidence    = ocr_confidence,     # already 0–100 float
    )

    # ── Step 10: Render result ─────────────────────────────────────────────────
    return render_template(
        'result.html',
        filename             = filename,
        file_path            = file_path.replace("\\", "/"),
        file_extension       = file_extension.upper(),
        processed_image_path = processed_image_path.replace("\\", "/"),
        extracted_text       = extracted_text,
        ocr_confidence       = ocr_confidence,
        ocr_status           = ocr_status,
        extracted_fields     = extracted_fields,
        validation_result    = final_result,
        metadata_result      = metadata_result,
        template_result      = template_result,
        final_report         = final_report,        # ← NEW
        success_message      = "File uploaded and processed successfully!",
    )


if __name__ == '__main__':
    app.run(debug=True)