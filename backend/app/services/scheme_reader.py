"""Read a Government Resolution and propose a scheme from it.

An officer uploads the GR (शासन निर्णय) announcing a welfare scheme; the model
reads it and proposes a scheme record with machine-readable eligibility rules.
The proposal is saved as `status='pending'` and nothing acts on it until an
officer approves it through the existing decision endpoint.

That gate is not bureaucracy. These rules decide who a Gram Panchayat tells to
apply for a pension. A model that misreads "60 वर्षे" as a maximum rather than a
minimum would have the system advising every resident under sixty to apply and
every eligible pensioner that they do not qualify. So the extraction is treated
as a *draft prepared by a clerk*, not as fact.

Two safeguards beyond the human check:

**A closed vocabulary.** The eligibility engine understands a fixed set of
criteria keys. A key it does not recognise is silently ignored at evaluation
time — which would make a scheme look stricter on paper than it behaves in
practice, the most dangerous failure available here. So anything the model
emits outside the known vocabulary is stripped out and reported to the officer
rather than stored as a rule that does nothing.

**Confidence is never 'high'.** Extraction confidence is capped at 'medium',
because nothing read by a model without a human comparing it to the GR deserves
the same standing as the hand-verified schemes already seeded.
"""

from __future__ import annotations

from datetime import date, datetime

from app.services.llm import LLMUnavailable, generate_json
from app.services.transcript import UnsupportedTranscript, extract_text  # noqa: F401

MAX_CHARS = 30_000

# Exactly the keys app/services/eligibility.py evaluates. Adding a rule there
# means adding it here, or the engine will support something the reader can
# never propose.
KNOWN_CRITERIA = {
    "min_age",
    "max_age",
    "min_income",
    "max_income",
    "gender",
    "marital_status_any",
    "category_any",
    "requires_bpl",
    "requires_secc_listed",
    "ration_card_any",
    "min_land_hectares",
    "max_land_hectares",
    "min_disability_percent",
    "occupation_any",
    "occupation_none",
    "ward_in",
    "is_head",
    "any_of",
    "manual_review",
}

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "nameMr": {"type": "string"},
        "description": {"type": "string"},
        "descriptionMr": {"type": "string"},
        "benefit": {"type": "string"},
        "benefitMr": {"type": "string"},
        "level": {"type": "string", "enum": ["central", "state", "district", "panchayat"]},
        "category": {"type": "string"},
        "announcedOn": {"type": "string"},
        "requiredDocuments": {"type": "array", "items": {"type": "string"}},
        "criteria": {
            "type": "object",
            "properties": {
                "min_age": {"type": "integer"},
                "max_age": {"type": "integer"},
                "max_income": {"type": "number"},
                "gender": {"type": "string", "enum": ["Male", "Female", "Other"]},
                "marital_status_any": {"type": "array", "items": {"type": "string"}},
                "category_any": {"type": "array", "items": {"type": "string"}},
                "requires_bpl": {"type": "boolean"},
                "requires_secc_listed": {"type": "boolean"},
                "min_income": {"type": "number"},
                "ration_card_any": {"type": "array", "items": {"type": "string"}},
                "min_land_hectares": {"type": "number"},
                "max_land_hectares": {"type": "number"},
                "min_disability_percent": {"type": "integer"},
                "occupation_any": {"type": "array", "items": {"type": "string"}},
                "occupation_none": {"type": "array", "items": {"type": "string"}},
                "manual_review": {"type": "boolean"},
            },
        },
        "unmappableConditions": {"type": "array", "items": {"type": "string"}},
        "confidenceNote": {"type": "string"},
    },
    "required": ["name", "nameMr", "description", "descriptionMr", "benefit", "benefitMr"],
}

SYSTEM = (
    "You are a records clerk for a Gram Panchayat in Maharashtra, India. You read "
    "Government Resolutions (शासन निर्णय) announcing welfare schemes and record "
    "what they say.\n\n"
    "Rules you must follow:\n"
    "- Record only what the document states. Never supply an age limit, income "
    "ceiling, benefit amount or document requirement that is not written in it.\n"
    "- If the document does not state an eligibility condition, leave that field "
    "out entirely rather than guessing a common value.\n"
    "- Age and income limits are the most dangerous fields to get wrong. Read "
    "them twice, and note whether each is a minimum or a maximum.\n"
    "- Put every eligibility condition you could NOT express in the given "
    "criteria fields into 'unmappableConditions', word for word. An officer "
    "reads those; a condition you silently drop is one nobody will check.\n"
    "- Produce every text field in both English and Marathi. When the source is "
    "Marathi, translate faithfully rather than paraphrasing.\n"
    "- In 'confidenceNote', say plainly what was unclear or ambiguous in the "
    "document. Do not reassure."
)


class SchemeExtractionError(ValueError):
    """The document was read but did not describe a scheme."""


def _clean_criteria(raw: dict | None) -> tuple[dict, list[str]]:
    """Keep only the rules the eligibility engine actually evaluates.

    Returns the usable criteria and a list of what was discarded, so the officer
    is told rather than the rule quietly vanishing.
    """
    if not isinstance(raw, dict):
        return {}, []

    kept: dict = {}
    dropped: list[str] = []

    for key, value in raw.items():
        if key not in KNOWN_CRITERIA:
            dropped.append(f"{key}={value!r}")
            continue
        # A null or empty value is not a rule; storing it would add a criterion
        # that reads as configured but tests nothing.
        if value is None or value == [] or value == "":
            continue
        kept[key] = value

    return kept, dropped


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value.strip()[:10], fmt).date()
        except ValueError:
            continue
    return None


async def read_scheme(text: str, source_name: str | None = None) -> dict:
    """Ask the model to read a GR and propose a scheme.

    Returns a dict ready to build a `Scheme` from, plus `_review` carrying
    everything the officer needs to check before approving.
    """
    prompt = (
        "Read the Government Resolution below and record the welfare scheme it "
        "announces.\n\n"
        "Extract: the scheme's name, a description of its purpose, what the "
        "beneficiary receives, which government level runs it, its category "
        "(Pension, Housing, Agriculture, Health, Education, Women and Child, "
        "Employment, Sanitation, Insurance, Disability or similar), the date it "
        "was announced, the documents an applicant must submit, and its "
        "eligibility conditions as structured criteria.\n\n"
        f"DOCUMENT:\n{text}"
    )

    data = await generate_json(prompt, EXTRACTION_SCHEMA, SYSTEM)

    if not data.get("name") or not data.get("benefit"):
        raise SchemeExtractionError(
            "This document does not appear to announce a welfare scheme. "
            "Check that you uploaded the right file."
        )

    criteria, dropped = _clean_criteria(data.get("criteria"))
    unmappable = [str(c) for c in (data.get("unmappableConditions") or [])]

    # A scheme with conditions nobody could encode must not silently behave as
    # though it has none — anyone passing the encodable rules would be told they
    # qualify. Flagging it for review makes the engine say "Needs Review"
    # instead of "Eligible".
    if unmappable or dropped:
        criteria["manual_review"] = True

    notes = [f"Read from {source_name}." if source_name else "Read from an uploaded document."]
    if data.get("confidenceNote"):
        notes.append(f"Reader's note: {data['confidenceNote']}")
    if unmappable:
        notes.append(
            "Conditions in the GR that could not be expressed as automatic rules, "
            "and must be checked by hand: " + "; ".join(unmappable)
        )
    if dropped:
        notes.append(
            "The reader proposed criteria this system does not evaluate, so they "
            "were not stored as rules: " + "; ".join(dropped)
        )
    notes.append(
        "Extracted by a language model and not yet verified against the source "
        "document. Check every figure before approving."
    )

    return {
        "name": data["name"].strip(),
        "name_mr": (data.get("nameMr") or data["name"]).strip(),
        "description": data["description"].strip(),
        "description_mr": (data.get("descriptionMr") or data["description"]).strip(),
        "benefit": data["benefit"].strip(),
        "benefit_mr": (data.get("benefitMr") or data["benefit"]).strip(),
        "level": data.get("level") or "state",
        "category": data.get("category"),
        "announced_on": _parse_date(data.get("announcedOn")),
        "required_documents": [str(d) for d in (data.get("requiredDocuments") or [])],
        "criteria": criteria,
        # Never 'high': nothing a model read unverified is as trustworthy as the
        # hand-checked schemes already in the database.
        "confidence": "low" if (unmappable or dropped) else "medium",
        "notes": "\n\n".join(notes),
        "_review": {
            "unmappable_conditions": unmappable,
            "discarded_criteria": dropped,
            "confidence_note": data.get("confidenceNote"),
            "needs_manual_review": bool(criteria.get("manual_review")),
        },
    }
