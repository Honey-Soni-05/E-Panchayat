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

Retrieval happens entirely inside this server: it is database queries and, on
the semantic path, a comparison against vectors already stored. Nothing about a
resident leaves the building to answer a question — the model, when it is
called at all, is called afterwards and only with facts cleared for it.

Facts about one identified resident are marked `personal=True` as they are
collected. They are returned to the person entitled to see them exactly as
before; what changes is that they are never used as prompt material. The
eligibility decision they describe was made by `services.eligibility`, which is
deterministic and calls no model, so nothing is lost by keeping the model out
of this path — only the phrasing is plainer.
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
from app.services.classifier import CATEGORY_KEYWORDS
from app.services import graph
from app.services.llm import LLMUnavailable, embed

# ─────────────────────────────────────────────────────────────────────────────
# Intent routing
# ─────────────────────────────────────────────────────────────────────────────

def _service_words() -> list[str]:
    """Every keyword the grievance classifier recognises, flattened.

    Imported rather than copied so the two cannot drift: a word added for
    classification immediately helps retrieval find the same complaints.
    """
    return [w for words in CATEGORY_KEYWORDS.values() for w in words]


TOPIC_KEYWORDS: dict[str, list[str]] = {
    "grievances": [
        "grievance", "complaint", "issue", "problem", "pending", "resolved",
        "broken", "not working", "fix", "repair", "what to do",
        "तक्रार", "समस्या", "प्रलंबित", "निराकरण", "बंद", "दुरुस्ती",
        # Plus every word the grievance classifier knows — water, drains,
        # roads, electricity, health, in both languages. Villagers describe a
        # problem ("the tap has been dry"), they do not say "grievance", and
        # this list existed already rather than needing to be invented twice.
        *_service_words(),
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
        # "ward" deliberately absent: nearly every question about a village
        # names a ward, so routing on it sent "the tap in ward 1 is dry" to the
        # resident directory, which for a citizen returns nothing at all.
        "citizen", "resident", "population", "people", "household", "family",
        "how many live",
        "नागरिक", "रहिवासी", "लोकसंख्या", "कुटुंब",
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
    """Facts pulled from the database, ready to be handed to a model.

    Some of them are not, though. `has_personal` marks a set of facts that
    describes an identified individual — what they earn, which social category
    they belong to, whether they are on the BPL list, what their disability
    assessment says, which documents sit in their file. Those are collected
    normally, shown to the person entitled to see them, and never sent to
    Google. See `api.routes.assistant` for where that is enforced.
    """

    facts: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    # 'semantic' when the embedded index answered, 'keyword' when it fell back.
    # Surfaced in the UI so nobody has to guess which path ran.
    mode: str = "keyword"
    # True once any fact describes one identified resident. Sticky: a set of
    # facts is only as shareable as its most sensitive member.
    has_personal: bool = False

    def add(
        self, fact: str, source: Source | None = None, *, personal: bool = False
    ) -> None:
        self.facts.append(fact)
        if personal:
            self.has_personal = True
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


async def gather_semantic(
    db: Session, question: str, user: User, village_id: str | None, limit: int = 6
) -> Retrieved:
    """Retrieve by meaning, then walk the links of what matched.

    Falls back to `gather()` whenever the semantic path cannot run - no index
    built, no API key, an embedding call that failed, or a question that matched
    nothing above the similarity floor. The fallback is not a degraded copy: it
    is the same keyword retrieval that served this endpoint before, so the
    assistant keeps working on a deployment where nobody has run the indexer.
    """
    if not graph.index_is_ready(db):
        return gather(db, question, user, village_id)

    try:
        vectors = await embed([question])
    except LLMUnavailable:
        return gather(db, question, user, village_id)

    if not vectors:
        return gather(db, question, user, village_id)

    hits = graph.semantic_search(db, vectors[0], user, village_id, limit=limit)
    if not hits:
        # A question the index has nothing close to. Keyword routing may still
        # have something useful, and an empty answer helps nobody.
        return gather(db, question, user, village_id)

    out = Retrieved()
    out.mode = "semantic"
    out.topics = sorted({h.chunk.entity_type for h in hits})
    for hit in hits:
        # `indexer` does not build resident chunks, so this should never fire.
        # It is here so that if someone reintroduces them, the assistant treats
        # them as personal and withholds them from the model rather than
        # quietly resuming the export this was written to stop.
        out.add(
            graph.describe(hit),
            Source(hit.chunk.entity_type, hit.chunk.entity_id, hit.chunk.content[:80]),
            personal=hit.chunk.entity_type == "citizen",
        )
    return out


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

        if is_citizen:
            # A resident asking about a problem wants to know what to do about
            # it, not to be handed a count. Their own complaints are the only
            # ones they may see, so when none of them match, the useful answer
            # is how to raise one — not silence.
            out.add(
                f"This resident has {open_count} unresolved complaint(s) of their own "
                f"on record. A resident can only see complaints they filed themselves."
            )
            out.add(
                "To report a new problem, a resident files a grievance from the "
                "Grievances page of this portal. It is recorded with a ward and a "
                "category, routed to the responsible department automatically, and "
                "its status becomes visible to them here as the office updates it. "
                "Urgent problems can also be reported at the Gram Panchayat office "
                "in person."
            )
        else:
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

                # Personal: an eligibility explanation carries the reason the
                # engine decided as it did, and those reasons are the resident's
                # income, social category, BPL status, ration card and
                # disability assessment. This is the data the assistant must
                # never hand to a third-party model, so it is flagged here and
                # answered from a template instead.
                out.add(
                    f"{citizen.name} currently qualifies for {len(eligible)} "
                    f"{'scheme' if len(eligible) == 1 else 'schemes'}, and would "
                    f"qualify for {len(nearly)} more once the missing documents "
                    f"are uploaded and verified.",
                    personal=True,
                )
                for assessment, scheme in (eligible + nearly)[:limit]:
                    out.add(
                        f'Scheme "{scheme.name}" ({scheme.benefit}): '
                        f"{elig.explain(assessment, 'en')}",
                        Source("scheme", scheme.id, scheme.name),
                        personal=True,
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
            # Personal: which documents one named resident has filed, and why
            # any of them was rejected, is their own file rather than village
            # information.
            for d in db.scalars(stmt.limit(limit)):
                out.add(
                    f"Document {d.doc_type} ({d.file_name}) submitted {d.submitted_date}, "
                    f"status {d.status}"
                    + (f" — {d.rejection_reason}" if d.rejection_reason else "")
                    + ".",
                    Source("document", d.id, d.doc_type),
                    personal=True,
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

    Used in three cases: no API key is configured, the model call failed, or the
    facts describe an identified resident and so are not eligible to be sent to
    a model at all. It is plainer than a generated answer but every line of it
    is true, which the old canned responses could not claim.

    The closing note says which of the three happened. A resident reading an
    answer about their own pension should be told that their income and category
    were not sent to Google, rather than left to assume they were.
    """
    if retrieved.is_empty:
        return (
            "मला या प्रश्नाशी संबंधित नोंदी सापडल्या नाहीत. तुम्ही ग्रामपंचायत "
            "कार्यालयात विचारू शकता, किंवा तक्रार असल्यास 'तक्रारी' पानावरून नोंदवू शकता."
            if language == "mr"
            else "I could not find any records related to that question. You can ask "
            "at the Gram Panchayat office, or file it from the Grievances page if it "
            "is a problem that needs fixing."
        )

    header = (
        "पंचायत नोंदींमधून मिळालेली माहिती:"
        if language == "mr"
        else "Here is what the Panchayat records show:"
    )
    body = "\n".join(f"• {fact}" for fact in retrieved.facts[:10])

    if retrieved.has_personal:
        footer = (
            "\n\n(ही तुमची वैयक्तिक माहिती असल्याने ती कोणत्याही बाहेरील AI सेवेकडे "
            "पाठवली जात नाही. म्हणून हे उत्तर थेट नोंदींमधून दिले आहे. पात्रता "
            "नियमांनुसार ठरवली जाते, AI ने नाही.)"
            if language == "mr"
            else "\n\n(Listed directly from the records. This answer concerns your own "
            "file, so it was written here rather than by an AI service — your income, "
            "category and documents are never sent outside this system. The eligibility "
            "decision itself is made by a rule engine, not by AI.)"
        )
    else:
        footer = (
            "\n\n(भाषा मॉडेल उपलब्ध नसल्याने ही थेट नोंदींची यादी आहे.)"
            if language == "mr"
            else "\n\n(Listed directly from the records — the language model is not configured, "
            "so this is not a written summary.)"
        )
    return f"{header}\n{body}{footer}"
