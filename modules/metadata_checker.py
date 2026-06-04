# modules/metadata_checker.py
# This module extracts and analyzes file metadata from uploaded
# PDF or image files to detect suspicious editing signs.

import os
import re
from datetime import datetime

# Pillow for image metadata and EXIF
from PIL import Image
from PIL.ExifTags import TAGS

# PyMuPDF for PDF metadata
import fitz


# ── Known editing software keywords ───────────────────────────────────────────
EDITING_SOFTWARE = [
    "photoshop", "canva", "gimp", "illustrator", "picsart",
    "snapseed", "photopea", "corel", "paint.net", "inkscape",
    "lightroom", "affinity"
]


# ── Date Parsing Helpers ───────────────────────────────────────────────────────

def _parse_pdf_date(date_str):
    """
    Parse a PDF metadata date string into a Python datetime object.

    PDF date format example: D:20260604072819+05'30'

    Args:
        date_str (str): Raw PDF date string.

    Returns:
        datetime or None
    """
    if not date_str:
        return None
    try:
        # Remove the "D:" prefix if present
        date_str = date_str.strip()
        if date_str.startswith("D:"):
            date_str = date_str[2:]

        # Extract the first 14 characters: YYYYMMDDHHMMSS
        date_str = date_str[:14]
        return datetime.strptime(date_str, "%Y%m%d%H%M%S")
    except Exception:
        return None


def _parse_exif_date(date_str):
    """
    Parse an EXIF date string into a Python datetime object.

    EXIF date format example: 2026:06:04 07:28:19

    Args:
        date_str (str): Raw EXIF date string.

    Returns:
        datetime or None
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def _parse_issue_date(date_str):
    """
    Parse the certificate issue date extracted by field_extractor.

    Certificate date format: 12-02-2025

    Args:
        date_str (str): Issue date string from extracted fields.

    Returns:
        datetime or None
    """
    if not date_str or date_str == "Not Found":
        return None
    try:
        return datetime.strptime(date_str.strip(), "%d-%m-%Y")
    except Exception:
        return None


def _check_editing_software(software_str):
    """
    Check if the software name string contains any known editing software.

    Args:
        software_str (str): Software name from metadata.

    Returns:
        bool: True if editing software is detected.
    """
    if not software_str:
        return False
    software_lower = software_str.lower()
    return any(kw in software_lower for kw in EDITING_SOFTWARE)


# ── PDF Metadata Extractor ─────────────────────────────────────────────────────

def _extract_pdf_metadata(file_path):
    """
    Extract metadata from a PDF file using PyMuPDF.

    Args:
        file_path (str): Path to the PDF file.

    Returns:
        dict: Extracted metadata fields.
    """
    metadata = {
        "file_type":         "PDF",
        "title":             "Not Found",
        "author":            "Not Found",
        "subject":           "Not Found",
        "creator":           "Not Found",
        "producer":          "Not Found",
        "creation_date":     "Not Found",
        "modification_date": "Not Found",
        "pages":             "Not Found",
        "image_width":       "N/A",
        "image_height":      "N/A",
        "image_format":      "N/A",
        "software":          "Not Found",
    }

    try:
        doc = fitz.open(file_path)
        meta = doc.metadata  # Returns a dict
        doc.close()

        metadata["title"]    = meta.get("title",    "") or "Not Found"
        metadata["author"]   = meta.get("author",   "") or "Not Found"
        metadata["subject"]  = meta.get("subject",  "") or "Not Found"
        metadata["creator"]  = meta.get("creator",  "") or "Not Found"
        metadata["producer"] = meta.get("producer", "") or "Not Found"
        metadata["pages"]    = str(meta.get("page_count", "Not Found"))

        # Dates
        raw_creation = meta.get("creationDate", "")
        raw_modified = meta.get("modDate", "")
        metadata["creation_date"]     = raw_creation if raw_creation else "Not Found"
        metadata["modification_date"] = raw_modified if raw_modified else "Not Found"

        # Software is sometimes stored in creator or producer for PDFs
        combined = f"{metadata['creator']} {metadata['producer']}".lower()
        if _check_editing_software(combined):
            metadata["software"] = f"{metadata['creator']} / {metadata['producer']}"

        print(f"[metadata_checker] PDF metadata extracted.")

    except Exception as e:
        print(f"[metadata_checker] ERROR reading PDF metadata: {e}")

    return metadata


# ── Image Metadata Extractor ───────────────────────────────────────────────────

def _extract_image_metadata(file_path):
    """
    Extract metadata and EXIF data from an image file using Pillow.

    Args:
        file_path (str): Path to the image file.

    Returns:
        dict: Extracted metadata fields.
    """
    metadata = {
        "file_type":         "Image",
        "title":             "N/A",
        "author":            "N/A",
        "subject":           "N/A",
        "creator":           "N/A",
        "producer":          "N/A",
        "creation_date":     "Not Found",
        "modification_date": "Not Found",
        "pages":             "N/A",
        "image_width":       "Not Found",
        "image_height":      "Not Found",
        "image_format":      "Not Found",
        "software":          "Not Found",
    }

    try:
        img = Image.open(file_path)

        metadata["image_format"] = img.format  or "Not Found"
        metadata["image_width"]  = str(img.width)
        metadata["image_height"] = str(img.height)
        metadata["file_type"]    = img.format  or "Image"

        # Try to extract EXIF data
        exif_data = img._getexif() if hasattr(img, '_getexif') else None

        if exif_data:
            # Map numeric EXIF tag IDs to human-readable names
            decoded_exif = {TAGS.get(tag_id, tag_id): value
                            for tag_id, value in exif_data.items()}

            # Software
            software = decoded_exif.get("Software", "")
            metadata["software"] = software if software else "Not Found"

            # DateTime (modification time in EXIF)
            datetime_modified = decoded_exif.get("DateTime", "")
            metadata["modification_date"] = datetime_modified if datetime_modified else "Not Found"

            # DateTimeOriginal (when photo was originally taken / created)
            datetime_original = decoded_exif.get("DateTimeOriginal", "")
            metadata["creation_date"] = datetime_original if datetime_original else "Not Found"

            # If creation date still not found, try DateTimeDigitized
            if metadata["creation_date"] == "Not Found":
                datetime_digitized = decoded_exif.get("DateTimeDigitized", "")
                metadata["creation_date"] = datetime_digitized if datetime_digitized else "Not Found"

        img.close()
        print(f"[metadata_checker] Image metadata extracted.")

    except Exception as e:
        print(f"[metadata_checker] ERROR reading image metadata: {e}")

    return metadata


# ── Main Public Function ───────────────────────────────────────────────────────

def check_metadata(file_path, extracted_fields=None):
    """
    Extract metadata from a PDF or image file and analyze for suspicious signs.

    Args:
        file_path (str): Path to the original uploaded file.
        extracted_fields (dict): Fields extracted by field_extractor (optional).
                                 Used to compare issue date with file creation date.

    Returns:
        dict: {
            "metadata"              : dict  — raw extracted metadata fields,
            "metadata_checks"       : dict  — boolean check results,
            "metadata_issues"       : list  — list of issue strings,
            "metadata_score_deduction": int — total score to deduct
        }
    """

    # ── Determine file type and extract metadata ───────────────────────────────
    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        metadata = _extract_pdf_metadata(file_path)
        is_pdf   = True
    else:
        metadata = _extract_image_metadata(file_path)
        is_pdf   = False

    # ── Initialize result containers ──────────────────────────────────────────
    metadata_checks = {
        "metadata_found":              False,
        "editing_software_detected":   False,
        "creation_date_found":         False,
        "modification_date_found":     False,
        "creation_after_issue_date":   False,
    }
    metadata_issues   = []
    score_deduction   = 0

    # ── Check 1: Was any metadata found at all? ────────────────────────────────
    has_any = any(
        v not in ("Not Found", "N/A", None, "")
        for k, v in metadata.items()
        if k in ("title", "author", "creator", "software",
                 "creation_date", "modification_date",
                 "image_width", "image_height")
    )
    metadata_checks["metadata_found"] = has_any

    # ── Check 2: Editing software ──────────────────────────────────────────────
    software_str = metadata.get("software", "")
    if _check_editing_software(software_str):
        metadata_checks["editing_software_detected"] = True
        metadata_issues.append("Possible editing software detected in metadata.")
        score_deduction += 15
        print(f"[metadata_checker] Editing software detected: {software_str}")

    # ── Check 3: Creation date present ────────────────────────────────────────
    creation_str = metadata.get("creation_date", "Not Found")
    if creation_str and creation_str != "Not Found":
        metadata_checks["creation_date_found"] = True
    else:
        # Missing creation date is a minor flag — don't make document fake
        metadata_issues.append("Creation date metadata is missing.")
        score_deduction += 5
        print("[metadata_checker] Creation date not found.")

    # ── Check 4: Modification date present and different from creation ─────────
    mod_str = metadata.get("modification_date", "Not Found")
    if mod_str and mod_str != "Not Found":
        metadata_checks["modification_date_found"] = True

        # Compare modification and creation dates
        if is_pdf:
            creation_dt  = _parse_pdf_date(creation_str)
            mod_dt       = _parse_pdf_date(mod_str)
        else:
            creation_dt  = _parse_exif_date(creation_str)
            mod_dt       = _parse_exif_date(mod_str)

        if creation_dt and mod_dt and creation_dt != mod_dt:
            metadata_issues.append("File modification date is different from creation date.")
            score_deduction += 10
            print("[metadata_checker] Modification date differs from creation date.")

    # ── Check 5: File created AFTER the certificate issue date ────────────────
    if extracted_fields and metadata_checks["creation_date_found"]:
        issue_date_str = extracted_fields.get("issue_date", "Not Found")
        issue_dt       = _parse_issue_date(issue_date_str)

        if is_pdf:
            creation_dt = _parse_pdf_date(creation_str)
        else:
            creation_dt = _parse_exif_date(creation_str)

        if issue_dt and creation_dt and creation_dt > issue_dt:
            metadata_checks["creation_after_issue_date"] = True
            metadata_issues.append("File creation date is later than certificate issue date.")
            score_deduction += 15
            print("[metadata_checker] File created AFTER issue date — suspicious!")

    print(f"[metadata_checker] Total score deduction: {score_deduction}")

    return {
        "metadata":                 metadata,
        "metadata_checks":          metadata_checks,
        "metadata_issues":          metadata_issues,
        "metadata_score_deduction": score_deduction,
    }