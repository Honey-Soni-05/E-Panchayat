"""One upload satisfies every scheme requirement that names the same paper."""

from types import SimpleNamespace

import pytest

from app.services.eligibility import _find_document


def _doc(name, status="Verified"):
    return SimpleNamespace(doc_type=name, doc_type_mr="", status=status)


@pytest.mark.parametrize("requirement, upload", [
    ("Bank account passbook", "Bank Passbook"),
    ("Bank or post office savings account", "Bank Passbook"),
    ("Address proof", "Passport"),
    ("Age proof", "10th Marksheet"),
    ("Government photo ID (interim, until health card issued)", "Voter ID"),
    ("Land records (7/12 and 8A)", "7/12 Land Extract"),
    ("Maharashtra domicile / residence certificate", "Domicile Certificate"),
    ("BPL certificate / Ration card", "Ration Card"),
    ("Income certificate", "Income Cert."),
])
def test_requirement_is_met_by_an_equivalent_upload(requirement, upload):
    assert _find_document(requirement, "", [_doc(upload)]) is not None


@pytest.mark.parametrize("requirement, upload", [
    ("Aadhaar-linked bank passbook", "Aadhaar Card"),
    ("Yellow or Orange Ration Card with Aadhaar number", "Aadhaar Card"),
    ("Income certificate", "Caste Certificate"),
    ("Disability certificate", "Passport"),
])
def test_unrelated_upload_does_not_count(requirement, upload):
    assert _find_document(requirement, "", [_doc(upload)]) is None
