"""Scheme eligibility engine.

Rules live in each scheme's `criteria` dictionary, so adding a scheme is an
insert rather than a code change. The original frontend hardcoded rules per
scheme id in a chain of `if` statements, which meant an unrecognised scheme
silently fell through to a bare income test.

The supported rule vocabulary was widened after researching real central and
Maharashtra schemes, because almost none of them decide eligibility on age and
income alone:

    Sanjay Gandhi Niradhar   income under Rs 21,000 OR on the BPL list
    Ramai Awas               Scheduled Caste / Neo-Buddhist only
    MJPJAY                   Yellow, Orange, AAY or Annapurna ration card
    Saur Krushi Pump         land holding bands
    Ladki Bahin              married, widowed, divorced or abandoned
    PMAY-G, Ayushman Bharat  SECC-2011 deprivation listing, no income test

Supported keys
    min_age, max_age                int
    min_income, max_income          annual rupees
    gender                          "Male" | "Female"
    marital_status_any              list
    ward_in                         list of ward numbers
    occupation_any                  list of substrings, English or Marathi
    occupation_none                 list of substrings (exclusions)
    is_head                         bool
    category_any                    list, e.g. ["SC", "ST"]
    requires_bpl                    bool
    requires_secc_listed            bool
    ration_card_any                 list, e.g. ["Yellow", "Orange", "AAY"]
    min_land_hectares               float
    max_land_hectares               float
    min_disability_percent          int
    any_of                          list of criteria dicts — passes if ANY passes
    manual_review                   bool — engine cannot decide; officer must

An empty criteria dict means everyone passes. That is deliberate: a scheme with
no stated rules is open to all, and it is visible in the data rather than
hidden in a fallback branch.

`manual_review` exists because some real schemes cannot be evaluated from a
resident record at all. The National Family Benefit Scheme's age rule describes
the deceased breadwinner, not the applicant. PMMVY applies only to a first
living child. Rather than quietly misapplying those, the engine says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Citizen, CitizenDocument, Scheme

STATUS_MR = {
    "Eligible": "पात्र",
    "Missing Documents": "कागदपत्रे अपूर्ण",
    "Needs Review": "अधिकारी तपासणी आवश्यक",
    "Ineligible": "अपात्र",
}

# Ranked worst-to-best for any_of reporting, and used for list ordering.
STATUS_ORDER = ["Eligible", "Missing Documents", "Needs Review", "Ineligible"]


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
    needs_review: bool = False
    failed_criteria: list[str] = field(default_factory=list)
    failed_criteria_mr: list[str] = field(default_factory=list)
    missing_documents: list[DocGap] = field(default_factory=list)
    unverified_documents: list[DocGap] = field(default_factory=list)
    # Attributes the resident record does not hold, so the rule could not run.
    unknown_attributes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if not self.criteria_passed:
            return "Ineligible"
        if self.needs_review or self.unknown_attributes:
            return "Needs Review"
        if self.missing_documents or self.unverified_documents:
            return "Missing Documents"
        return "Eligible"


# ─────────────────────────────────────────────────────────────────────────────
# Criteria evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _matches_any(needles: list[str], *haystacks: str | None) -> bool:
    lowered = [h.lower() for h in haystacks if h]
    return any(n.lower() in hay for n in needles for hay in lowered)


@dataclass
class RuleOutcome:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    reasons_mr: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    manual_review: bool = False


def evaluate(citizen: Citizen, criteria: dict) -> RuleOutcome:
    """Evaluate one criteria dictionary against one resident."""
    out = RuleOutcome(passed=True)
    if not criteria:
        return out

    income = float(citizen.income or 0)

    def fail(en: str, mr: str) -> None:
        out.passed = False
        out.reasons.append(en)
        out.reasons_mr.append(mr)

    def unknown(attr_en: str, attr_mr: str) -> None:
        # A rule we cannot evaluate does not fail the resident — it flags them
        # for an officer. Silently passing or failing would both be wrong.
        out.unknown.append(attr_en)
        out.reasons_mr.append(f"{attr_mr} नोंद नाही")

    # ── Age ──────────────────────────────────────────────────────────────────
    if (v := criteria.get("min_age")) is not None and citizen.age < v:
        fail(f"Age {citizen.age} is below the minimum of {v}",
             f"वय {citizen.age} हे किमान {v} पेक्षा कमी आहे")

    if (v := criteria.get("max_age")) is not None and citizen.age > v:
        fail(f"Age {citizen.age} is above the maximum of {v}",
             f"वय {citizen.age} हे कमाल {v} पेक्षा जास्त आहे")

    # ── Income ───────────────────────────────────────────────────────────────
    if (v := criteria.get("max_income")) is not None and income > v:
        fail(f"Annual income Rs {income:,.0f} exceeds the ceiling of Rs {v:,.0f}",
             f"वार्षिक उत्पन्न ₹{income:,.0f} हे ₹{v:,.0f} च्या मर्यादेपेक्षा जास्त आहे")

    if (v := criteria.get("min_income")) is not None and income < v:
        fail(f"Annual income Rs {income:,.0f} is below the floor of Rs {v:,.0f}",
             f"वार्षिक उत्पन्न ₹{income:,.0f} हे ₹{v:,.0f} पेक्षा कमी आहे")

    # ── Gender and marital status ────────────────────────────────────────────
    if (v := criteria.get("gender")) is not None and citizen.gender != v:
        fail(f"Scheme is restricted to {v} applicants",
             f"ही योजना फक्त {'महिलांसाठी' if v == 'Female' else 'पुरुषांसाठी'} आहे")

    if v := criteria.get("marital_status_any"):
        if not citizen.marital_status:
            unknown("marital status", "वैवाहिक स्थिती")
        elif citizen.marital_status not in v:
            fail(f"Scheme requires marital status among {', '.join(v)}",
                 f"ही योजना {', '.join(v)} अशा वैवाहिक स्थितीसाठी आहे")

    # ── Social category, BPL, SECC ───────────────────────────────────────────
    if v := criteria.get("category_any"):
        if not citizen.social_category:
            unknown("social category", "सामाजिक प्रवर्ग")
        elif citizen.social_category not in v:
            fail(f"Scheme is reserved for {', '.join(v)} category applicants",
                 f"ही योजना {', '.join(v)} प्रवर्गासाठी राखीव आहे")

    if criteria.get("requires_bpl") and not citizen.is_bpl:
        fail("Applicant is not on the Below Poverty Line list",
             "अर्जदार दारिद्र्यरेषेखालील यादीत नाही")

    if criteria.get("requires_secc_listed") and not citizen.secc_listed:
        fail("Household is not listed in the SECC-2011 deprivation data",
             "कुटुंब एसईसीसी-२०११ वंचितता यादीत नाही")

    if v := criteria.get("ration_card_any"):
        if not citizen.ration_card_type:
            unknown("ration card type", "शिधापत्रिका प्रकार")
        elif citizen.ration_card_type not in v:
            fail(f"Requires a {' / '.join(v)} ration card; this household holds "
                 f"{citizen.ration_card_type}",
                 f"{' / '.join(v)} शिधापत्रिका आवश्यक; या कुटुंबाकडे "
                 f"{citizen.ration_card_type} आहे")

    # ── Land holding ─────────────────────────────────────────────────────────
    has_land_rule = (
        criteria.get("min_land_hectares") is not None
        or criteria.get("max_land_hectares") is not None
    )
    if has_land_rule and citizen.land_holding_hectares is None:
        unknown("land holding", "जमीनधारणा")
    else:
        land = citizen.land_holding_hectares
        if (v := criteria.get("min_land_hectares")) is not None and land is not None and land < v:
            fail(f"Land holding of {land} ha is below the minimum of {v} ha",
                 f"{land} हेक्टर जमीन ही किमान {v} हेक्टरपेक्षा कमी आहे")
        if (v := criteria.get("max_land_hectares")) is not None and land is not None and land > v:
            fail(f"Land holding of {land} ha exceeds the maximum of {v} ha",
                 f"{land} हेक्टर जमीन ही कमाल {v} हेक्टरपेक्षा जास्त आहे")

    # ── Disability ───────────────────────────────────────────────────────────
    if (v := criteria.get("min_disability_percent")) is not None:
        if citizen.disability_percent is None:
            unknown("disability assessment", "दिव्यांगत्व नोंद")
        elif citizen.disability_percent < v:
            fail(f"Requires a disability assessment of at least {v}%",
                 f"किमान {v}% दिव्यांगत्व आवश्यक आहे")

    # ── Occupation, ward, household head ─────────────────────────────────────
    if (v := criteria.get("occupation_any")) and not _matches_any(
        v, citizen.occupation, citizen.occupation_mr
    ):
        fail(f"Occupation '{citizen.occupation}' is not among the qualifying occupations",
             f"'{citizen.occupation_mr}' हा पात्र व्यवसाय नाही")

    if (v := criteria.get("occupation_none")) and _matches_any(
        v, citizen.occupation, citizen.occupation_mr
    ):
        fail(f"Occupation '{citizen.occupation}' is excluded from this scheme",
             f"'{citizen.occupation_mr}' हा व्यवसाय या योजनेतून वगळला आहे")

    if (v := criteria.get("ward_in")) and citizen.ward not in v:
        fail(f"Ward {citizen.ward} is outside the covered wards",
             f"वॉर्ड {citizen.ward} हा समाविष्ट वॉर्डांमध्ये नाही")

    if (v := criteria.get("is_head")) is not None and bool(citizen.is_head) != bool(v):
        fail("Scheme applies to household heads only",
             "ही योजना फक्त कुटुंब प्रमुखांसाठी लागू आहे")

    # ── any_of: an OR group ──────────────────────────────────────────────────
    # Real schemes routinely say "BPL OR income under X OR SC/ST". Each branch
    # is evaluated independently and the group passes if any branch does.
    if branches := criteria.get("any_of"):
        results = [evaluate(citizen, branch) for branch in branches]
        if any(r.passed and not r.unknown for r in results):
            pass  # one branch cleanly satisfied — nothing to report
        elif any(r.unknown for r in results):
            out.unknown.extend(sorted({a for r in results for a in r.unknown}))
        else:
            reasons = [" and ".join(r.reasons) for r in results if r.reasons]
            fail(
                "None of the alternative conditions are met (" + "; or ".join(reasons) + ")",
                "पर्यायी अटींपैकी एकही पूर्ण होत नाही",
            )

    if criteria.get("manual_review"):
        out.manual_review = True

    return out


def check_documents(
    scheme: Scheme, documents: list[CitizenDocument]
) -> tuple[list[DocGap], list[DocGap]]:
    """Match a resident's uploaded files against the scheme's requirements.

    Matching is forgiving — an officer typing "Income Cert." should satisfy a
    requirement named "Income Certificate" — but it compares whole normalised
    names rather than the old code's first-eight-characters trick, which
    matched "Land ownership 7/12" against anything starting "Land own".
    """
    missing: list[DocGap] = []
    unverified: list[DocGap] = []

    for req in scheme.required_documents or []:
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
        hit = (target and (target in have or have in target)) or (
            target_mr and (target_mr in have_mr or have_mr in target_mr)
        )
        if hit:
            if doc.status == "Verified":
                return doc  # prefer a verified copy if uploaded twice
            best = best or doc
    return best


def assess(
    citizen: Citizen, scheme: Scheme, documents: list[CitizenDocument]
) -> Assessment:
    outcome = evaluate(citizen, scheme.criteria or {})

    missing: list[DocGap] = []
    unverified: list[DocGap] = []
    if outcome.passed:
        missing, unverified = check_documents(scheme, documents)

    return Assessment(
        citizen=citizen,
        scheme=scheme,
        criteria_passed=outcome.passed,
        needs_review=outcome.manual_review,
        failed_criteria=outcome.reasons,
        failed_criteria_mr=outcome.reasons_mr,
        missing_documents=missing,
        unverified_documents=unverified,
        unknown_attributes=outcome.unknown,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Explanations
# ─────────────────────────────────────────────────────────────────────────────

def explain(a: Assessment, language: str = "en") -> str:
    """A plain-language reason for the decision, built from the same facts the
    engine used. No LLM in this path — a welfare decision has to be
    reproducible and auditable, and a generated sentence is neither."""
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

    if a.unknown_attributes:
        joined = ", ".join(a.unknown_attributes)
        return (
            f"{name} यांच्या नोंदीत आवश्यक माहिती नाही ({joined}), त्यामुळे "
            f"{scheme} साठी पात्रता ठरवता आली नाही. कृपया नोंद पूर्ण करा."
            if mr
            else f"{name}'s record is missing {joined}, so eligibility for {scheme} "
            f"could not be determined. Complete the record to get an answer."
        )

    if a.needs_review:
        return (
            f"{name} हे {scheme} च्या मूलभूत अटी पूर्ण करतात, परंतु या योजनेच्या "
            f"काही अटी नोंदीवरून तपासता येत नाहीत. अधिकाऱ्याने पडताळणी करावी."
            if mr
            else f"{name} meets the basic criteria for {scheme}, but this scheme has "
            f"conditions that cannot be checked from a resident record. An officer "
            f"must verify before approving."
        )

    if a.missing_documents or a.unverified_documents:
        missing = [d.name_mr if mr else d.name for d in a.missing_documents]
        pending = [
            f"{(d.name_mr if mr else d.name)} ({d.file_status})"
            for d in a.unverified_documents
        ]
        parts = []
        if missing:
            parts.append(("अपलोड बाकी: " if mr else "not uploaded: ") + ", ".join(missing))
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
        else f"{name} (age {a.citizen.age}, ward {a.citizen.ward}, annual income Rs {income:,.0f}) "
        f"qualifies for {scheme} and every required document is verified."
    )
