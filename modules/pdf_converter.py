"""
FakeDoc Detector — modules/pdf_converter.py
Module 2: PDF to Image Converter

Converts the first page of a PDF file into a PNG image
using PyMuPDF (fitz), and saves it to static/processed/.
"""

import os
import fitz  # PyMuPDF


def convert_pdf_to_image(pdf_path, output_folder):
    """
    Convert the first page of a PDF to a PNG image.

    Args:
        pdf_path    (str): Full path to the uploaded PDF file.
        output_folder (str): Folder where the output image will be saved.

    Returns:
        str: Path to the saved PNG image, or None if conversion failed.
    """

    # Make sure the output folder exists
    os.makedirs(output_folder, exist_ok=True)

    try:
        # Open the PDF file using PyMuPDF
        pdf_document = fitz.open(pdf_path)

        # Access only the first page (index 0)
        first_page = pdf_document[0]

        # Render the page to a pixel map at 2x zoom for better OCR quality
        # Matrix(2, 2) means 2x scale in both x and y directions
        zoom_matrix = fitz.Matrix(2, 2)
        pixel_map = first_page.get_pixmap(matrix=zoom_matrix)

        # Build the output image filename from the PDF filename
        # e.g. "income_certificate.pdf" → "income_certificate_page1.png"
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_filename = f"{base_name}_page1.png"
        output_path = os.path.join(output_folder, output_filename)

        # Save the rendered image as PNG
        pixel_map.save(output_path)

        # Close the PDF document to free memory
        pdf_document.close()

        print(f"[pdf_converter] PDF converted → {output_path}")
        return output_path

    except Exception as e:
        # Log the error and return None so the caller can handle it
        print(f"[pdf_converter] ERROR during PDF conversion: {e}")
        return None