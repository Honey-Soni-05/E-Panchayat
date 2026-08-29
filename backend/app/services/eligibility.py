"""Scheme eligibility engine.

The old frontend version keyed its rules on scheme id in a chain of `if`
statements, so a sixth scheme silently fell through to a bare income test.
Here the rules are data: each scheme carries a `criteria` dict and this module
evaluates whatever it finds, so adding a scheme is an insert, not a code change.

Supported criteria keys
    min_age            int    citizen.age >= value
    max_age            int    citizen.age <= value
    max_income         float  citizen.income <= value
    min_income         float  citizen.income >= value
    gender             str    exact match on citizen.gender
    ward_in            list   citizen.ward in value
    occupation_any     list   any substring matches occupation or occupation_mr
    occupation_none    list   no substring matches (exclusions)
    is_head            bool   citizen.is_head == value

An empty criteria dict means every citizen passes, which is deliberate: a
scheme with no stated rules is open to all, and that is visible in the data
rather than hidden in a fallback branch.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Citizen, CitizenDocument, Scheme

STATUS_MR = {
    "Eligible": "पात्र",
    "Missing Documents": "कागदपत्रे अपूर्ण",
    "Ineligible": "अपात्र",
}


@dataclass
class DocGap:
    name: str
    name_mr: str
    file_status: str | None = None


@dataclass
class Assessment:
    citizen: Citizen
    scheme: Scheme
    criteria_passed: bool
    failed_criteria: list[str] = field(default_factory=list)
    failed_criteria_mr: list[str] = field(default_factory=list)
    missing_documents: list[DocGap] = field(default_factory=list)
    unverified_documents: list[DocGap] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.criteria_passed:
            return "Ineligible"
        if self.missing_documents or self.unverified_documents:
            return "Missing Documents"
        return "Eligible"


def _matches_any(needles: list[str], *haystacks: str | None) -> bool:
    lowered = [h.lower() for h in haystacks if h]
    return any(
        n.lower() in hay
        for n in needles
        for hay in lowered
    )


def check_criteria(citizen: Citizen, criteria: dict) -> tuple[bool, list[str], list[str]]:
    """Returns (passed, reasons_en, reasons_mr) — reasons list what failed."""
    failed: list[str] = []
    failed_mr: list[str] = []
    income = float(citizen.income or 0)

    if (v := criteria.get("min_age")) is not None and citizen.age < v:
        failed.append(f"Age {citizen.age} is below the minimum of {v}")
        failed_mr.append(f"वय {citizen.age} हे किमान {v} पेक्षा कमी आहे")

    if (v := criteria.get("max_age")) is not None and citizen.age > v:
        failed.append(f"Age {citizen.age} is above the maximum of {v}")
        failed_mr.append(f"वय {citizen.age} हे कमाल {v} पेक्षा जास्त आहे")

    if (v := criteria.get("max_income")) is not None and income > v:
        failed.append(f"Annual income ₹{income:,.0f} exceeds the ceiling of ₹{v:,.0f}")
        failed_mr.append(f"वार्षिक उत्पन्न ₹{income:,.0f} हे ₹{v:,.0f} च्या मर्यादेपेक्षा जास्त आहे")

    if (v := criteria.get("min_income")) is not None and income < v:
        failed.append(f"Annual income ₹{income:,.0f} is below the floor of ₹{v:,.0f}")
        failed_mr.append(f"वार्षिक उत्पन्न ₹{income:,.0f} हे ₹{v:,.0f} पेक्षा कमी आहे")

    if (v := criteria.get("gender")) is not None and citizen.gender != v:
        failed.append(f"Scheme is restricted to applicants of gender {v}")
        failed_mr.append(f"ही योजना फक्त {v} अर्जदारांसाठी आहे")

    if (v := criteria.get("ward_in")) and citizen.ward not in v:
        failed.append(f"Ward {citizen.ward} is outside the covered wards {v}")
        failed_mr.append(f"वॉर्ड {citizen.ward} हा समाविष्ट वॉर्डांमध्ये नाही")

    if (v := criteria.get("occupation_any")) and not _matches_any(
        v, citizen.occupation, citizen.occupation_mr
    ):
        failed.append(f"Occupation '{citizen.occupation}' is not among the qualifying occupations")
        failed_mr.append(f"'{citizen.occupation_mr}' हा पात्र व्यवसाय नाही")

    if (v := criteria.get("occupation_none")) and _matches_any(
        v, citizen.occupation, citizen.occupation_mr
    ):
        failed.append(f"Occupation '{citizen.occupation}' is excluded from this scheme")
        failed_mr.append(f"'{citizen.occupation_mr}' हा व्यवसाय या योजनेतून वगळला आहे")

    if (v := criteria.get("is_head")) is not None and bool(citizen.is_head) != bool(v):
        failed.append("Scheme applies to household heads only")
        failed_mr.append("ही योजना फक्त कुटुंब प्रमुखांसाठी लागू आहे")

    return (not failed), failed, failed_mr


def check_documents(
    scheme: Scheme, documents: list[CitizenDocument]
) -> tuple[list[DocGap], list[DocGap]]:
    """Match a citizen's uploaded files against the scheme's requirements.

    Matching is deliberately forgiving — an officer typing "Income Cert." should
    satisfy a requirement named "Income Certificate" — but it compares whole
    normalised names rather than the old code's first-eight-characters trick,
    which matched "Land ownership 7/12" against anything starting "Land own".
    """
    required = scheme.required_documents or []
    missing: list[DocGap] = []
    unverified: list[DocGap] = []

    for req in required:
        req_name = (req.get("name") or "").strip()
        req_name_mr = (req.get("name_mr") or req.get("nameMr") or "").strip()
        match = _find_document(req_name, req_name_mr, documents)

        if match is None:
            missing.append(DocGap(name=req_name, name_mr=req_name_mr))
        elif match.status != "Verified":
            unverified.append(
                DocGap(name=req_name, name_mr=req_name_mr, file_status=match.status)
            )

    return missing, unverified


def _find_document(
    req_name: str, req_name_mr: str, documents: list[CitizenDocument]
) -> CitizenDocument | None:
    def norm(s: str) -> str:
        return "".join(ch for ch in s.lower() if ch.isalnum())

    target, target_mr = norm(req_name), norm(req_name_mr)
    best: CitizenDocument | None = None

    for doc in documents:
        have, have_mr = norm(doc.doc_type), norm(doc.doc_type_mr or "")
        hit = (
            (target and (target in have or have in target))
            or (target_mr and (target_mr in have_mr or have_mr in target_mr))
        )
        if hit:
            # Prefer a verified copy if the citizen uploaded the file twice.
            if doc.status == "Verified":
                return doc
            best = best or doc
    return best


def assess(
    citizen: Citizen, scheme: Scheme, documents: list[CitizenDocument]
) -> Assessment:
    passed, failed, failed_mr = check_criteria(citizen, scheme.criteria or {})
    missing, unverified = ([], [])
    if passed:
        missing, unverified = check_documents(scheme, documents)

    return Assessment(
        citizen=citizen,
        scheme=scheme,
        criteria_passed=passed,
        failed_criteria=failed,
        failed_criteria_mr=failed_mr,
        missing_documents=missing,
        unverified_documents=unverified,
    )


def explain(a: Assessment, language: str = "en") -> str:
    """A plain-language reason for the decision, built from the same facts the
    engine used. No LLM call — this is deterministic and auditable, which is
    what a welfare decision needs."""
    mr = language == "mr"
    name = a.citizen.name_mr if mr else a.citizen.name
    scheme = a.scheme.name_mr if mr else a.scheme.name

    if not a.criteria_passed:
        reasons = a.failed_criteria_mr if mr else a.failed_criteria
        joined = "; ".join(reasons)
        return (
            f"{name} या योजनेसाठी ({scheme}) पात्र नाहीत: {joined}."
            if mr
            else f"{name} does not meet the criteria for {scheme}: {joined}."
        )

    if a.missing_documents or a.unverified_documents:
        missing = [d.name_mr if mr else d.name for d in a.missing_documents]
        pending = [
            f"{(d.name_mr if mr else d.name)} ({d.file_status})"
            for d in a.unverified_documents
        ]
        parts = []
        if missing:
            parts.append(
                ("अपलोड बाकी: " if mr else "not uploaded: ") + ", ".join(missing)
            )
        if pending:
            parts.append(
                ("पडताळणी बाकी: " if mr else "awaiting verification: ") + ", ".join(pending)
            )
        joined = "; ".join(parts)
        return (
            f"{name} हे {scheme} साठी निकषांनुसार पात्र आहेत, परंतु कागदपत्रे अपूर्ण आहेत — {joined}."
            if mr
            else f"{name} meets every criterion for {scheme}, but the file is incomplete — {joined}."
        )

    income = float(a.citizen.income or 0)
    return (
        f"{name} (वय {a.citizen.age}, वॉर्ड {a.citizen.ward}, वार्षिक उत्पन्न ₹{income:,.0f}) "
        f"हे {scheme} साठी पूर्णपणे पात्र आहेत आणि सर्व आवश्यक कागदपत्रे पडताळली आहेत."
        if mr
        else f"{name} (age {a.citizen.age}, ward {a.citizen.ward}, annual income ₹{income:,.0f}) "
        f"qualifies for {scheme} and every required document is verified."
    )
