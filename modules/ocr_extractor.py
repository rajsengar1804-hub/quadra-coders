"""
FakeDoc Detector — modules/ocr_extractor.py
Module 2: OCR Text Extractor

Uses EasyOCR to extract text from an image file.
The EasyOCR reader is initialized once at module load time
so it is not reloaded on every function call.
"""

import easyocr

# ── Initialize EasyOCR reader once (global) ───────────────────────────────────
# 'en' = English language model.
# gpu=False → use CPU (safe default; set True if CUDA GPU is available).
# This takes a few seconds the first time — only happens once per server start.
print("[ocr_extractor] Initializing EasyOCR reader (this may take a moment)...")
reader = easyocr.Reader(['en'], gpu=False)
print("[ocr_extractor] EasyOCR reader ready.")


def extract_text_from_image(image_path):
    """
    Extract all text from the given image using EasyOCR.

    Args:
        image_path (str): Full path to the image (PNG / JPG / JPEG).

    Returns:
        dict: {
            "text"       : str   — all extracted text joined into one string,
            "confidence" : float — average confidence across all detections (0–1),
            "raw"        : list  — raw EasyOCR output (bbox, text, conf) per line
        }
        On failure returns {"text": "", "confidence": 0.0, "raw": []}
    """

    try:
        # Run OCR on the image.
        # detail=1  → returns (bounding_box, text, confidence) per detection
        # paragraph=False → treat each text region individually
        results = reader.readtext(image_path, detail=1, paragraph=False)

        if not results:
            print(f"[ocr_extractor] No text found in: {image_path}")
            return {"text": "", "confidence": 0.0, "raw": []}

        # Collect text lines and confidence scores
        lines = []
        confidences = []

        for (bbox, text, confidence) in results:
            lines.append(text)
            confidences.append(confidence)

        # Join all detected lines into one readable string
        full_text = "\n".join(lines)

        # Compute average confidence across all detections
        avg_confidence = round(sum(confidences) / len(confidences), 4)

        print(f"[ocr_extractor] Extracted {len(lines)} lines | avg confidence: {avg_confidence}")

        return {
            "text": full_text,
            "confidence": avg_confidence,
            "raw": results
        }

    except Exception as e:
        print(f"[ocr_extractor] ERROR during OCR: {e}")
        return {"text": "", "confidence": 0.0, "raw": []}