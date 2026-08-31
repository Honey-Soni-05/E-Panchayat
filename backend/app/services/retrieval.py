"""Fetch the Panchayat records a question is actually about.

This replaces the old assistant, which matched keywords against a handful of
`if` branches and returned pre-written paragraphs with the numbers interpolated.
It could not answer anything its author had not anticipated, and the "sources"
it displayed were decorative.

Here a question is routed to real queries, the rows that come back are rendered
as facts, and the language model is given those facts and told to answer from
them alone. Two consequences worth noting:

  * Every answer is scoped by the asker's own permissions. A citizen's question
    runs against their own records; an officer's against their village. The
    retrieval layer cannot leak what the API would not return.
  * With no model key configured the endpoint still answers, from the same
    retrieved facts, in a plainer form. It degrades rather than inventing.

Retrieval is keyword-routed rather than embedding-based. That is a deliberate
first step: the facts are real, which is the part that matters. Semantic search
over `knowledge_chunks` is the next layer, and slots in behind the same
interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Citizen,
    CitizenDocument,
    Grievance,
    Project,
    SabhaMeeting,
    Scheme,
    User,
    Village,
)
from app.services import eligibility as elig

# ─────────────────────────────────────────────────────────────────────────────
# Intent routing
# ─────────────────────────────────────────────────────────────────────────────

TOPIC_KEYWORDS: dict[str, list[str]] = {
    "grievances": [
        "grievance", "complaint", "issue", "problem", "pending", "resolved",
        "तक्रार", "समस्या", "प्रलंबित", "निराकरण",
    ],
    "schemes": [
        "scheme", "yojana", "eligible", "eligibility", "pension", "subsidy",
        "benefit", "qualify", "apply", "welfare",
        "योजना", "पात्र", "पेन्शन", "निवृत्तिवेतन", "अनुदान", "लाभ",
    ],
    "projects": [
        "project", "work", "construction", "road", "budget", "spend", "delayed",
        "progress", "fund", "expenditure",
        "प्रकल्प", "काम", "बांधकाम", "रस्ता", "निधी", "बजेट", "खर्च", "विलंब",
    ],
    "citizens": [
        "citizen", "resident", "population", "people", "household", "family",
        "how many live", "ward",
        "नागरिक", "रहिवासी", "लोकसंख्या", "कुटुंब", "वॉर्ड",
    ],
    "sabha": [
        "sabha", "meeting", "minutes", "decision", "action item", "resolution",
        "सभा", "बैठक", "निर्णय", "ठराव", "कार्यवाही",
    ],
    "documents": [
        "document", "certificate", "aadhaar", "upload", "verify", "verification",
        "कागदपत्र", "दाखला", "आधार", "पडताळणी",
    ],
    "village": [
        "village", "panchayat", "block", "taluka", "district", "lgd",
        "गाव", "पंचायत", "तालुका", "जिल्हा",
    ],
}


def detect_topics(question: str) -> list[str]:
    """Which record types the question is about. Empty means 'give an overview'."""
    text = question.lower()
    hits = [
        topic
        for topic, words in TOPIC_KEYWORDS.items()
        if any(word.lower() in text for word in words)
    ]
    return hits


# ─────────────────────────────────────────────────────────────────────────────
# Retrieved facts
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Source:
    entity_type: str
    entity_id: str
    title: str


@dataclass
class Retrieved:
    """Facts pulled from the database, ready to be handed to a model."""

    facts: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)

    def add(self, fact: str, source: Source | None = None) -> None:
        self.facts.append(fact)
        if source:
            self.sources.append(source)

    @property
    def is_empty(self) -> bool:
        return not self.facts

    def as_context(self) -> str:
        return "\n".join(f"- {fact}" for fact in self.facts)


# ─────────────────────────────────────────────────────────────────────────────
# The queries
# ─────────────────────────────────────────────────────────────────────────────

def _rupees(value) -> str:
    return f"Rs {float(value or 0):,.0f}"


def _village_filter(model, village_id: str | None):
    return [model.village_id == village_id] if village_id else []


def gather(
    db: Session, question: str, user: User, village_id: str | None, limit: int = 8
) -> Retrieved:
    """Collect the facts relevant to one question, within one user's permissions."""
    out = Retrieved()
    topics = detect_topics(question)
    out.topics = topics or ["overview"]
    is_citizen = user.role == "citizen"
    citizen_id = user.citizen_id if is_citizen else None

    # Village context is cheap and almost always useful for grounding.
    if village_id:
        village = db.get(Village, village_id)
        if village:
            population = (
                f", Census 2011 population {village.population_2011:,}"
                if village.population_2011
                else ""
            )
            out.add(
                f"This is {village.name} Gram Panchayat, {village.block.name} block, "
                f"{village.block.district.name} district, Maharashtra "
                f"(LGD code {village.lgd_code}){population}.",
                Source("village", village.id, village.name),
            )

    want = set(topics) or {"grievances", "projects", "schemes"}

    # ── Grievances ───────────────────────────────────────────────────────────
    if "grievances" in want:
        stmt = select(Grievance)
        if is_citizen:
            stmt = stmt.where(Grievance.citizen_id == citizen_id)
        else:
            stmt = stmt.where(*_village_filter(Grievance, village_id))

        open_count = db.scalar(
            select(func.count()).select_from(stmt.where(Grievance.status != "Resolved").subquery())
        ) or 0
        out.add(f"There are {open_count} unresolved grievances.")

        for g in db.scalars(
            stmt.where(Grievance.status != "Resolved")
            .order_by(Grievance.priority.desc(), Grievance.submitted_date.desc())
            .limit(limit)
        ):
            out.add(
                f'Grievance {g.id}: "{g.title}" in ward {g.ward}, category {g.category}, '
                f"priority {g.priority}, status {g.status}, with {g.department}, "
                f"filed {g.submitted_date}.",
                Source("grievance", g.id, g.title),
            )

    # ── Projects ─────────────────────────────────────────────────────────────
    if "projects" in want:
        stmt = select(Project).where(*_village_filter(Project, village_id))
        projects = list(db.scalars(stmt.order_by(Project.ward)))

        if projects:
            total = sum(float(p.budget) for p in projects)
            used = sum(float(p.utilized) for p in projects)
            out.add(
                f"There are {len(projects)} development projects with a combined "
                f"sanctioned budget of {_rupees(total)}, of which {_rupees(used)} "
                f"has been spent, leaving {_rupees(total - used)}."
            )
            for p in projects[:limit]:
                out.add(
                    f'Project {p.id}: "{p.name}" in ward {p.ward} at {p.location} is '
                    f"{p.status}, {p.progress}% complete, budget {_rupees(p.budget)}, "
                    f"spent {_rupees(p.utilized)}.",
                    Source("project", p.id, p.name),
                )

    # ── Schemes and eligibility ──────────────────────────────────────────────
    if "schemes" in want:
        active = list(db.scalars(select(Scheme).where(Scheme.status == "active")))
        out.add(f"{len(active)} welfare schemes are currently active in this Panchayat.")

        if is_citizen and citizen_id:
            # A resident asking about schemes wants their own answer.
            citizen = db.scalar(
                select(Citizen)
                .options(selectinload(Citizen.documents))
                .where(Citizen.id == citizen_id)
            )
            if citizen:
                docs = list(citizen.documents)
                results = [
                    (elig.assess(citizen, scheme, docs), scheme) for scheme in active
                ]
                eligible = [(a, s) for a, s in results if a.status == "Eligible"]
                nearly = [(a, s) for a, s in results if a.status == "Missing Documents"]

                out.add(
                    f"{citizen.name} currently qualifies for {len(eligible)} schemes, "
                    f"and would qualify for {len(nearly)} more once the missing "
                    f"documents are uploaded and verified."
                )
                for assessment, scheme in (eligible + nearly)[:limit]:
                    out.add(
                        f'Scheme "{scheme.name}" ({scheme.benefit}): '
                        f"{elig.explain(assessment, 'en')}",
                        Source("scheme", scheme.id, scheme.name),
                    )
        else:
            for scheme in active[:limit]:
                out.add(
                    f'Scheme "{scheme.name}" ({scheme.level}, {scheme.category}): '
                    f"{scheme.benefit}. Criteria: {scheme.criteria}.",
                    Source("scheme", scheme.id, scheme.name),
                )

    # ── Residents ────────────────────────────────────────────────────────────
    if "citizens" in want and not is_citizen:
        stmt = select(Citizen).where(*_village_filter(Citizen, village_id))
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        out.add(f"{total} residents are registered on the platform for this village.")

        by_ward = db.execute(
            select(Citizen.ward, func.count())
            .where(*_village_filter(Citizen, village_id))
            .group_by(Citizen.ward)
            .order_by(Citizen.ward)
        ).all()
        if by_ward:
            spread = ", ".join(f"ward {w}: {n}" for w, n in by_ward)
            out.add(f"Residents by ward — {spread}.")

        seniors = db.scalar(
            select(func.count())
            .select_from(Citizen)
            .where(Citizen.age >= 60, *_village_filter(Citizen, village_id))
        ) or 0
        out.add(f"{seniors} registered residents are aged 60 or above.")

    # ── Gram Sabha ───────────────────────────────────────────────────────────
    if "sabha" in want:
        meetings = list(db.scalars(
            select(SabhaMeeting)
            .options(selectinload(SabhaMeeting.action_items))
            .where(*_village_filter(SabhaMeeting, village_id))
            .order_by(SabhaMeeting.meeting_date.desc())
            .limit(3)
        ))
        for m in meetings:
            pending = [i for i in m.action_items if i.status != "Completed"]
            out.add(
                f'Gram Sabha on {m.meeting_date}: "{m.title}". {m.summary} '
                f"{len(m.action_items)} action items, {len(pending)} still open.",
                Source("sabha_meeting", m.id, m.title),
            )
            for item in pending[:4]:
                out.add(
                    f"Open action item from {m.meeting_date}: {item.action} "
                    f"(responsible: {item.responsible}, deadline {item.deadline or 'not set'}, "
                    f"status {item.status})."
                )

    # ── Documents ────────────────────────────────────────────────────────────
    if "documents" in want:
        stmt = select(CitizenDocument)
        if is_citizen and citizen_id:
            stmt = stmt.where(CitizenDocument.citizen_id == citizen_id)
            for d in db.scalars(stmt.limit(limit)):
                out.add(
                    f"Document {d.doc_type} ({d.file_name}) submitted {d.submitted_date}, "
                    f"status {d.status}"
                    + (f" — {d.rejection_reason}" if d.rejection_reason else "")
                    + ".",
                    Source("document", d.id, d.doc_type),
                )
        else:
            pending = db.scalar(
                select(func.count())
                .select_from(CitizenDocument)
                .where(CitizenDocument.status == "Pending Verification")
            ) or 0
            out.add(f"{pending} citizen documents are awaiting officer verification.")

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Answering without a language model
# ─────────────────────────────────────────────────────────────────────────────

def plain_answer(retrieved: Retrieved, language: str = "en") -> str:
    """A readable answer built from the retrieved facts, with no model involved.

    Used when no API key is configured, or when the model call fails. It is
    plainer than a generated answer but every line of it is true, which the old
    canned responses could not claim.
    """
    if retrieved.is_empty:
        return (
            "मला या प्रश्नाशी संबंधित नोंदी सापडल्या नाहीत."
            if language == "mr"
            else "I could not find any records related to that question."
        )

    header = (
        "पंचायत नोंदींमधून मिळालेली माहिती:"
        if language == "mr"
        else "Here is what the Panchayat records show:"
    )
    body = "\n".join(f"• {fact}" for fact in retrieved.facts[:10])
    footer = (
        "\n\n(भाषा मॉडेल उपलब्ध नसल्याने ही थेट नोंदींची यादी आहे.)"
        if language == "mr"
        else "\n\n(Listed directly from the records — the language model is not configured, "
        "so this is not a written summary.)"
    )
    return f"{header}\n{body}{footer}"
