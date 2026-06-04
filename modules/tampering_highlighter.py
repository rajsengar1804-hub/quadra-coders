"""
FakeDoc Detector — modules/tampering_highlighter.py
Tampered Area Highlighting Module

Reads the processed certificate image, identifies suspicious fields from
validation_result and reference_result, draws red bounding boxes around
those fields, labels each box, and saves the annotated image.

Requires: opencv-python (cv2)
No YOLO or ML detection — pure coordinate-based highlighting.
"""

import os
import cv2


# ─── Relative Field Regions ───────────────────────────────────────────────────
# Each entry maps a field name to a function that accepts (w, h) and returns
# (x1, y1, x2, y2) in pixel coordinates.
# Coordinates are expressed as fractions of the image width/height so the
# boxes scale correctly to any image resolution.

def _get_field_regions(w, h):
    """
    Return a dict of field_name → (x1, y1, x2, y2) pixel tuples.
    All values are derived from the image width (w) and height (h).
    """
    return {
        "certificate_number": (
            int(0.08 * w), int(0.22 * h),
            int(0.70 * w), int(0.29 * h),
        ),
        "applicant_name": (
            int(0.08 * w), int(0.31 * h),
            int(0.75 * w), int(0.37 * h),
        ),
        "father_name": (
            int(0.08 * w), int(0.36 * h),
            int(0.75 * w), int(0.42 * h),
        ),
        "address": (
            int(0.08 * w), int(0.41 * h),
            int(0.85 * w), int(0.47 * h),
        ),
        "district": (
            int(0.08 * w), int(0.46 * h),
            int(0.50 * w), int(0.52 * h),
        ),
        "state": (
            int(0.35 * w), int(0.46 * h),
            int(0.90 * w), int(0.52 * h),
        ),
        "annual_income": (
            int(0.08 * w), int(0.51 * h),
            int(0.80 * w), int(0.57 * h),
        ),
        "financial_year": (
            int(0.08 * w), int(0.56 * h),
            int(0.90 * w), int(0.62 * h),
        ),
        "issue_date": (
            int(0.08 * w), int(0.75 * h),
            int(0.40 * w), int(0.81 * h),
        ),
        "place": (
            int(0.08 * w), int(0.79 * h),
            int(0.35 * w), int(0.85 * h),
        ),
        "issuing_authority": (
            int(0.45 * w), int(0.75 * h),
            int(0.92 * w), int(0.81 * h),
        ),
        "designation": (
            int(0.45 * w), int(0.79 * h),
            int(0.95 * w), int(0.85 * h),
        ),
        "seal": (
            int(0.68 * w), int(0.82 * h),
            int(0.95 * w), int(0.96 * h),
        ),
        "signature": (
            int(0.45 * w), int(0.83 * h),
            int(0.90 * w), int(0.89 * h),
        ),
    }


# ─── Issue → Field Mapping ────────────────────────────────────────────────────
# Maps substrings found in validation_result["issues"] to the field(s) they
# should trigger highlighting for.

ISSUE_TO_FIELDS = {
    "Certificate number format is invalid":          ["certificate_number"],
    "Issue date format is invalid":                  ["issue_date"],
    "Seal text is missing":                          ["seal"],
    "Issuing authority or designation is missing":   ["issuing_authority", "designation"],
    "Required field missing: applicant_name":        ["applicant_name"],
    "Required field missing: father_name":           ["father_name"],
    "Required field missing: annual_income":         ["annual_income"],
    "Required field missing: issue_date":            ["issue_date"],
    "Required field missing: issuing_authority":     ["issuing_authority"],
    "Required field missing: designation":           ["designation"],
    "Required field missing: certificate_number":    ["certificate_number"],
    "Required field missing: address":               ["address"],
    "Required field missing: district":              ["district"],
    "Required field missing: state":                 ["state"],
    "Required field missing: financial_year":        ["financial_year"],
    "Required field missing: place":                 ["place"],
    "Annual income value is missing or invalid":     ["annual_income"],
    "Annual income value is not valid":              ["annual_income"],
    "Financial year format is invalid":              ["financial_year"],
}

# Fields that can be mismatched in reference_result["mismatched_fields"]
# and their corresponding highlight target (usually the same field name).
REFERENCE_FIELD_MAP = {
    "annual_income":    "annual_income",
    "applicant_name":   "applicant_name",
    "father_name":      "father_name",
    "issue_date":       "issue_date",
    "issuing_authority":"issuing_authority",
    "designation":      "designation",
    "address":          "address",
    "district":         "district",
    "state":            "state",
    "financial_year":   "financial_year",
    "place":            "place",
    "certificate_number": "certificate_number",
}


# ─── Drawing Helpers ──────────────────────────────────────────────────────────

# Red colour in BGR (OpenCV uses BGR, not RGB)
RED   = (0, 0, 255)
# Semi-transparent fill colour — drawn by blending a filled rectangle
RED_FILL = (0, 0, 200)

BOX_THICKNESS = 3
FONT          = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE    = 0.55
FONT_THICKNESS = 2
LABEL_OFFSET  = 10   # pixels above the rectangle top edge


def _draw_box_with_label(image, x1, y1, x2, y2, label):
    """
    Draw a red rectangle and a small label above it on the image (in-place).

    Args:
        image: OpenCV image (numpy array, modified in-place).
        x1, y1: Top-left corner of the bounding box.
        x2, y2: Bottom-right corner of the bounding box.
        label:  Short text string to display above the box.
    """
    # ── Draw the filled semi-transparent overlay ───────────────────────────
    # Create a copy, fill the rectangle on the copy, then blend.
    overlay = image.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), RED_FILL, thickness=-1)
    # Alpha 0.12 → very subtle red tint inside the box
    cv2.addWeighted(overlay, 0.12, image, 0.88, 0, image)

    # ── Draw the solid red border ──────────────────────────────────────────
    cv2.rectangle(image, (x1, y1), (x2, y2), RED, thickness=BOX_THICKNESS)

    # ── Draw the label ─────────────────────────────────────────────────────
    # Calculate text size so we can draw a background pill behind it.
    text = f"Suspicious: {label}"
    (text_w, text_h), baseline = cv2.getTextSize(
        text, FONT, FONT_SCALE, FONT_THICKNESS
    )

    # Position: just above the top-left corner of the box.
    # Clamp so the label never goes off the top of the image.
    label_y = max(y1 - LABEL_OFFSET, text_h + 4)
    label_x = x1

    # Dark background rectangle for readability
    cv2.rectangle(
        image,
        (label_x, label_y - text_h - baseline - 2),
        (label_x + text_w + 6, label_y + baseline),
        (20, 20, 20),
        thickness=-1,
    )

    # Red text
    cv2.putText(
        image,
        text,
        (label_x + 3, label_y - 2),
        FONT,
        FONT_SCALE,
        RED,
        FONT_THICKNESS,
        lineType=cv2.LINE_AA,
    )


# ─── Main Public Function ─────────────────────────────────────────────────────

def highlight_tampered_areas(
    image_path,
    reference_result=None,
    validation_result=None,
    output_folder="static/result_images",
):
    """
    Generate an annotated image with red bounding boxes around suspicious fields.

    Args:
        image_path (str):
            Path to the processed certificate image (PNG / JPG).
        reference_result (dict, optional):
            Output of reference_matcher.match_with_reference().
            Expected key: "mismatched_fields" — list of dicts with a "field" key.
        validation_result (dict, optional):
            Output of validator.validate_certificate() (or the merged final result).
            Expected key: "issues" — list of issue strings.
        output_folder (str):
            Folder where the highlighted image will be saved.
            Defaults to "static/result_images".

    Returns:
        dict: {
            "highlighted_image_path": str | None,
            "highlighted_fields":     list[str],
            "highlight_status":       "Highlighted" | "No Highlight Needed" | "Image Error"
        }
    """

    print("[tampering_highlighter] Starting tampered area highlighting...")

    # ── Step 1: Read the image ─────────────────────────────────────────────────
    image = cv2.imread(image_path)

    if image is None:
        print(f"[tampering_highlighter] ERROR: Cannot read image at {image_path}")
        return {
            "highlighted_image_path": None,
            "highlighted_fields":     [],
            "highlight_status":       "Image Error",
        }

    h, w = image.shape[:2]
    print(f"[tampering_highlighter] Image size: {w}×{h}")

    # ── Step 2: Collect suspicious fields ─────────────────────────────────────
    # Use a set so each field is highlighted only once even if flagged by
    # multiple sources.
    suspicious_fields = set()

    # — From reference_result mismatched fields —
    if reference_result and isinstance(reference_result, dict):
        mismatched = reference_result.get("mismatched_fields", [])
        for item in mismatched:
            # item can be a dict {"field": "annual_income", ...} or a plain string
            if isinstance(item, dict):
                field_name = item.get("field", "")
            else:
                field_name = str(item)

            field_name = field_name.strip()
            if field_name in REFERENCE_FIELD_MAP:
                suspicious_fields.add(REFERENCE_FIELD_MAP[field_name])
                print(f"[tampering_highlighter]   Reference mismatch → {field_name}")

    # — From validation_result issues —
    if validation_result and isinstance(validation_result, dict):
        issues = validation_result.get("issues", [])
        for issue in issues:
            if not issue:
                continue
            issue_str = str(issue).strip()

            # Try each known issue substring
            for substring, fields in ISSUE_TO_FIELDS.items():
                if substring.lower() in issue_str.lower():
                    for f in fields:
                        suspicious_fields.add(f)
                    print(f"[tampering_highlighter]   Validation issue '{issue_str}' → {fields}")
                    break  # One match per issue is enough

    # ── Step 3: Return early if nothing to highlight ───────────────────────────
    if not suspicious_fields:
        print("[tampering_highlighter] No suspicious fields found — no highlighting needed.")
        return {
            "highlighted_image_path": None,
            "highlighted_fields":     [],
            "highlight_status":       "No Highlight Needed",
        }

    # ── Step 4: Build field regions for this image size ───────────────────────
    field_regions = _get_field_regions(w, h)

    # ── Step 5: Draw boxes ─────────────────────────────────────────────────────
    highlighted_fields = []

    for field in sorted(suspicious_fields):   # sorted for deterministic order
        region = field_regions.get(field)

        if region is None:
            print(f"[tampering_highlighter]   No region defined for field: {field} — skipping.")
            continue

        x1, y1, x2, y2 = region

        # Sanity-check: make sure coordinates are inside the image
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))
        x2 = max(0, min(x2, w - 1))
        y2 = max(0, min(y2, h - 1))

        if x2 <= x1 or y2 <= y1:
            print(f"[tampering_highlighter]   Degenerate region for {field} — skipping.")
            continue

        # Convert field name to a readable label: "annual_income" → "annual income"
        label = field.replace("_", " ")
        _draw_box_with_label(image, x1, y1, x2, y2, label)
        highlighted_fields.append(field)
        print(f"[tampering_highlighter]   Drew box for: {field}")

    # ── Step 6: Save the highlighted image ────────────────────────────────────
    os.makedirs(output_folder, exist_ok=True)

    original_filename = os.path.basename(image_path)
    # Remove existing extension and rebuild as .jpg
    base_name = os.path.splitext(original_filename)[0]
    output_filename = f"highlighted_{base_name}.jpg"

    # Build the save path using the OS separator (works on Windows too)
    save_path = os.path.join(output_folder, output_filename)

    success = cv2.imwrite(save_path, image)

    if not success:
        print(f"[tampering_highlighter] ERROR: Could not save image to {save_path}")
        return {
            "highlighted_image_path": None,
            "highlighted_fields":     highlighted_fields,
            "highlight_status":       "Image Error",
        }

    # Return path with forward slashes so Flask url_for / <img src> works correctly
    flask_path = save_path.replace("\\", "/")
    print(f"[tampering_highlighter] Saved highlighted image → {flask_path}")
    print(f"[tampering_highlighter] Highlighted fields: {highlighted_fields}")

    return {
        "highlighted_image_path": flask_path,
        "highlighted_fields":     highlighted_fields,
        "highlight_status":       "Highlighted",
    }