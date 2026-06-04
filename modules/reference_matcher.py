# modules/reference_matcher.py
# Reference Field Matching Module
# Compares extracted fields with stored reference data based on certificate type.

import json
import os
import re


def normalize_certificate_number(value):
    """
    Normalize certificate number before lookup.
    """
    if value is None:
        return ""

    value = str(value).strip().upper()

    if value == "" or value.lower() == "not found":
        return ""

    value = re.sub(r"\s+", "", value)

    value = value.replace("\\", "/")
    value = value.replace("|", "/")

    value = value.replace("INCIDEMO", "INC/DEMO")
    value = value.replace("INCDEMO", "INC/DEMO")
    value = value.replace("IINC/DEMO", "INC/DEMO")
    value = value.replace("IINC", "INC")
    value = value.replace("DEM0", "DEMO")

    value = re.sub(r"/+", "/", value)

    return value


def normalize_general(value):
    """
    Normalize normal text fields.
    """
    if value is None:
        return ""

    value = str(value).strip().lower()

    if value == "" or value == "not found":
        return ""

    value = re.sub(r"[.,:;]", "", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


def normalize_income(value):
    """
    Normalize income.
    """
    if value is None:
        return ""

    value = str(value).strip().lower()

    if value == "" or value == "not found":
        return ""

    digits = re.findall(r"\d+", value)

    if not digits:
        return ""

    return "".join(digits)


def normalize_date(value):
    """
    Normalize date.
    """
    if value is None:
        return ""

    value = str(value).strip()

    if value == "" or value.lower() == "not found":
        return ""

    return value.replace("/", "-")


def normalize_value(field_name, value):
    """
    Choose normalization based on field type.
    """
    if field_name in ["annual_income", "income"]:
        return normalize_income(value)

    if field_name in ["issue_date", "date_of_issue"]:
        return normalize_date(value)

    return normalize_general(value)


def load_reference_data(reference_file_path):
    """
    Safely load reference data.
    """
    if not os.path.exists(reference_file_path):
        return None

    try:
        with open(reference_file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        print("[reference_matcher] Error loading reference file:", e)
        return None


def get_fields_to_compare(certificate_type):
    """
    Fields to compare based on certificate type.

    Income certificate has full field comparison.
    Caste and degree can be expanded later with custom extractors.
    """

    certificate_type = str(certificate_type).lower()

    if certificate_type == "income":
        return [
            "applicant_name",
            "father_name",
            "address",
            "district",
            "state",
            "annual_income",
            "financial_year",
            "issue_date",
            "place",
            "issuing_authority",
            "designation"
        ]

    if certificate_type == "caste":
        return [
            "applicant_name",
            "father_name",
            "address",
            "district",
            "state",
            "issue_date",
            "place",
            "issuing_authority",
            "designation"
        ]

    if certificate_type == "degree":
        return [
            "applicant_name",
            "father_name",
            "issue_date",
            "place",
            "issuing_authority",
            "designation"
        ]

    return [
        "applicant_name",
        "father_name",
        "issue_date",
        "place",
        "issuing_authority",
        "designation"
    ]


def match_with_reference(
    extracted_fields,
    certificate_type="income",
    reference_file_path="data/reference_data.json"
):
    """
    Compare extracted fields with reference database.
    """

    certificate_type = str(certificate_type).strip().lower()

    if not isinstance(extracted_fields, dict):
        return {
            "reference_found": False,
            "reference_score": 0,
            "reference_status": "Reference Not Found",
            "matched_fields": [],
            "mismatched_fields": [],
            "reference_issues": ["Extracted fields are not available."]
        }

    reference_data = load_reference_data(reference_file_path)

    if reference_data is None:
        return {
            "reference_found": False,
            "reference_score": 0,
            "reference_status": "Reference File Missing",
            "matched_fields": [],
            "mismatched_fields": [],
            "reference_issues": ["Reference data file not found."]
        }

    certificate_number = extracted_fields.get("certificate_number", "Not Found")
    certificate_number = normalize_certificate_number(certificate_number)

    if not certificate_number:
        return {
            "reference_found": False,
            "reference_score": 0,
            "reference_status": "Reference Not Found",
            "matched_fields": [],
            "mismatched_fields": [],
            "reference_issues": ["Certificate number not found in extracted fields."]
        }

    if certificate_number not in reference_data:
        return {
            "reference_found": False,
            "reference_score": 0,
            "reference_status": "Reference Not Found",
            "matched_fields": [],
            "mismatched_fields": [],
            "reference_issues": ["Certificate number not found in reference database."]
        }

    expected_data = reference_data[certificate_number]

    expected_type = str(expected_data.get("certificate_type", "income")).strip().lower()

    if expected_type != certificate_type:
        return {
            "reference_found": False,
            "reference_score": 0,
            "reference_status": "Certificate Type Mismatch",
            "matched_fields": [],
            "mismatched_fields": [],
            "reference_issues": [
                f"Selected certificate type is {certificate_type}, but reference record is {expected_type}."
            ]
        }

    fields_to_compare = get_fields_to_compare(certificate_type)

    matched_fields = []
    mismatched_fields = []
    reference_issues = []

    for field in fields_to_compare:
        expected_value = expected_data.get(field, "")
        found_value = extracted_fields.get(field, "Not Found")

        expected_normalized = normalize_value(field, expected_value)
        found_normalized = normalize_value(field, found_value)

        if expected_normalized and found_normalized and expected_normalized == found_normalized:
            matched_fields.append(field)
        else:
            mismatched_fields.append({
                "field": field,
                "expected": expected_value,
                "found": found_value
            })
            reference_issues.append(f"Mismatch found in {field}.")

    total_fields = len(fields_to_compare) or 1
    reference_score = round((len(matched_fields) / total_fields) * 100, 2)

    if reference_score >= 90:
        reference_status = "Matched"
    elif reference_score >= 60:
        reference_status = "Partial Match"
    else:
        reference_status = "Mismatch"

    return {
        "reference_found": True,
        "reference_score": reference_score,
        "reference_status": reference_status,
        "matched_fields": matched_fields,
        "mismatched_fields": mismatched_fields,
        "reference_issues": reference_issues
    }