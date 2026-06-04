#DeepDoc

## AI-Based Multi-Certificate Forgery Detection System

FakeDoc Detector is a web-based document verification system that detects suspicious or fake certificates using OCR, validation rules, reference matching, template matching, metadata checking, and risk scoring.

The system supports:

* Income Certificate
* Caste Certificate
* Degree Certificate

---

## Problem Statement

Fake certificates are often used for fraud in scholarships, admissions, jobs, and government schemes. Manual verification is slow and error-prone. FakeDoc Detector helps verify documents faster and explains why a document is genuine, suspicious, or fake.

---

## Key Features

* Multi-certificate selection
* OCR-based text extraction
* Field extraction
* Rule-based validation
* Reference data matching
* Template/layout matching
* Metadata checking
* Authenticity score
* Final explainable report

---

## System Workflow

```text
User opens website
↓
Select certificate type
↓
Upload certificate
↓
OCR extracts text
↓
Fields are extracted
↓
Validation checks are applied
↓
Reference data is matched
↓
Template layout is compared
↓
Metadata is checked
↓
Final score and report are generated
```

---

## Technology Stack

* Frontend: HTML, CSS, JavaScript
* Backend: Python Flask
* OCR: EasyOCR
* Image Processing: OpenCV, Pillow
* Template Matching: SSIM
* Metadata Checking: PyMuPDF, PyPDF2, Pillow EXIF
* Data Storage: JSON

---

## Project Structure

```text
FakeDoc_Detector/
│
├── app.py
├── requirements.txt
├── data/
│   └── reference_data.json
├── modules/
│   ├── ocr_extractor.py
│   ├── field_extractor.py
│   ├── validator.py
│   ├── reference_matcher.py
│   ├── metadata_checker.py
│   ├── template_matcher.py
│   └── report_generator.py
├── static/
│   ├── uploads/
│   ├── processed/
│   └── templates_docs/
│       ├── income_template.jpeg
│       ├── caste_template.jpeg
│       └── degree_template.jpeg
└── templates/
    ├── index.html
    └── result.html
```

---

## How to Run

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open in browser:

```text
http://127.0.0.1:5000
```

---

## Output

The system gives:

* Final status
* Authenticity score
* Risk level
* OCR confidence
* Detected issues
* Fraud indicators
* Recommendation

Example:

```text
Status: Suspicious
Score: 68/100
Fraud Type: Reference Data Mismatch
Recommendation: Manual verification required
```

---

## Ethical Note

This project uses only dummy/sample certificates for hackathon demonstration. No real government certificate or real personal data is used.

---

## Future Scope

* QR code verification
* Tampered area highlighting
* Database and report history
* Admin panel
* YOLO-based seal/signature detection
* Official API integration
