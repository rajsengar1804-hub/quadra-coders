# modules/template_matcher.py
# This module compares an uploaded certificate image with a reference
# template image using SSIM (Structural Similarity Index).

import cv2
import os
from skimage.metrics import structural_similarity as ssim


def compare_with_template(uploaded_image_path, template_image_path):
    """
    Compares the uploaded certificate image with the reference template image.

    Args:
        uploaded_image_path (str): Path to the uploaded/processed certificate image.
        template_image_path (str): Path to the genuine reference template image.

    Returns:
        dict: {
            "similarity_score" : float — SSIM score as percentage (0–100),
            "template_status"  : str   — "Good Match" / "Partial Match" / "Layout Mismatch",
            "template_issue"   : str   — human-readable description
        }
    """

    # ── Check if template image exists ────────────────────────────────────────
    if not template_image_path or not os.path.exists(template_image_path):
        print("[template_matcher] ERROR: Template image not found.")
        return {
            "similarity_score": 0,
            "template_status":  "Template Missing",
            "template_issue":   "Reference template image not found."
        }

    # ── Read uploaded image ────────────────────────────────────────────────────
    uploaded_img = cv2.imread(uploaded_image_path)

    if uploaded_img is None:
        print(f"[template_matcher] ERROR: Could not read uploaded image: {uploaded_image_path}")
        return {
            "similarity_score": 0,
            "template_status":  "Image Error",
            "template_issue":   "Uploaded image could not be processed for template matching."
        }

    # ── Read template image ────────────────────────────────────────────────────
    template_img = cv2.imread(template_image_path)

    if template_img is None:
        print(f"[template_matcher] ERROR: Could not read template image: {template_image_path}")
        return {
            "similarity_score": 0,
            "template_status":  "Template Missing",
            "template_issue":   "Reference template image not found."
        }

    # ── Convert both images to grayscale ──────────────────────────────────────
    # SSIM works on grayscale images
    uploaded_gray = cv2.cvtColor(uploaded_img,  cv2.COLOR_BGR2GRAY)
    template_gray = cv2.cvtColor(template_img,  cv2.COLOR_BGR2GRAY)

    # ── Resize both images to the same fixed size ──────────────────────────────
    # We use template size so the uploaded image matches the reference dimensions.
    # Fixed size: 800 x 1100 pixels (standard A4-like certificate size)
    target_width  = 800
    target_height = 1100

    uploaded_resized = cv2.resize(uploaded_gray, (target_width, target_height))
    template_resized = cv2.resize(template_gray, (target_width, target_height))

    # ── Calculate SSIM score ───────────────────────────────────────────────────
    # SSIM returns a value between -1 and 1.
    # 1.0 = identical images, 0.0 = no similarity, -1.0 = completely opposite.
    score, _ = ssim(template_resized, uploaded_resized, full=True)

    # Convert to percentage and round to 2 decimal places
    similarity_percent = round(score * 100, 2)

    # Clamp to 0–100 range just in case of floating point edge cases
    similarity_percent = max(0.0, min(100.0, similarity_percent))

    print(f"[template_matcher] SSIM similarity score: {similarity_percent}%")

    # ── Determine template status based on score ───────────────────────────────
    if similarity_percent >= 85:
        template_status = "Good Match"
        template_issue  = "No major layout mismatch detected."

    elif similarity_percent >= 65:
        template_status = "Partial Match"
        template_issue  = "Some layout differences detected."

    else:
        template_status = "Layout Mismatch"
        template_issue  = "Uploaded document does not match the reference template."

    return {
        "similarity_score": similarity_percent,
        "template_status":  template_status,
        "template_issue":   template_issue
    }