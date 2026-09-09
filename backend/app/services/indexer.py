"""Build the retrieval index: database rows rendered as linked, embeddable facts.

Every row here becomes one `KnowledgeChunk` carrying three things:

  * a natural-language sentence a model can read and an embedding can capture
  * `meta.links` — the ids of the records it relates to, which is what makes
    graph expansion possible at query time
  * the village it belongs to, so search obeys the same scoping as every other
    query in this system

The links are the point. A similarity match on "the hand pump in ward 3 is
still broken" finds one grievance chunk; walking that chunk's links reaches the
ward it sits in and the project that would fix it. Retrieving those neighbours
is what separates this from embedding search over loose sentences — the answer
can describe how records relate, because the relationships were indexed rather
than inferred from prose.

**Resident records are deliberately not indexed.** Embedding a chunk means
sending its text to Google, so anything indexed here leaves the country and,
on the free tier, may be retained to improve their products. Indexing runs over
every row whether or not anyone ever asks a question, so putting residents in
it would export the whole village register to a third party as a standing cost
of the feature.

De-identifying those chunks instead was considered and rejected. At village
scale it does not work: "a 52-year-old female agricultural labourer in ward 3"
identifies one person in a population of a few hundred, so stripping the name
leaves the record re-identifiable. Nothing about a resident is embedded.

The village still is, and so are its grievances, projects, facilities, schemes
and Gram Sabha minutes — none of which describe an individual. What a resident
qualifies for is decided by `services.eligibility`, which is deterministic and
never calls a model at all.

Re-indexing is incremental: a chunk whose source row has not changed since
`indexed_at` is left alone, so re-running this after editing one grievance
re-embeds one row rather than the whole village.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models import (
    Facility,
    Grievance,
    KnowledgeChunk,
    Project,
    SabhaMeeting,
    Scheme,
    Village,
)
from app.services.llm import LLMUnavailable, embed

# Gemini's embedding endpoint takes a batch; this keeps requests well inside
# the payload limit while still being one round trip for a small village.
BATCH = 32


@dataclass
class Draft:
    """A chunk before it has been embedded."""

    entity_type: str
    entity_id: str
    content: str
    content_mr: str | None = None
    village_id: str | None = None
    links: list[dict] = field(default_factory=list)
    source_changed_at: datetime | None = None

    @property
    def key(self) -> str:
        return f"{self.entity_type}:{self.entity_id}"

    @property
    def chunk_id(self) -> str:
        # Deterministic, so re-indexing updates rows rather than duplicating them.
        return "kc_" + hashlib.sha1(self.key.encode()).hexdigest()[:16]


def _link(entity_type: str, entity_id: str | None, label: str) -> dict | None:
    if not entity_id:
        return None
    return {"type": entity_type, "id": entity_id, "label": label}


def _links(*items: dict | None) -> list[dict]:
    return [i for i in items if i is not None]


# ─────────────────────────────────────────────────────────────────────────────
# Rendering rows as sentences
#
# These read like a person describing the record, because that is what the
# embedding has to match against — a question phrased the way a villager or an
# officer would actually ask it.
# ─────────────────────────────────────────────────────────────────────────────

def _village_drafts(db: Session) -> list[Draft]:
    drafts: list[Draft] = []
    for v in db.scalars(select(Village).options(selectinload(Village.block))):
        block = v.block
        district = block.district if block else None
        population = (
            f" Its Census 2011 population was {v.population_2011:,}"
            f" across {v.households_2011 or 0:,} households."
            if v.population_2011
            else ""
        )
        drafts.append(
            Draft(
                entity_type="village",
                entity_id=v.id,
                village_id=v.id,
                content=(
                    f"{v.name} is a village in {block.name if block else 'unknown'} block, "
                    f"{district.name if district else 'unknown'} district, Maharashtra, "
                    f"with LGD code {v.lgd_code}. Gram Panchayat status: "
                    f"{v.gram_panchayat_status}.{population}"
                ),
                content_mr=f"{v.name_mr} हे {block.name_mr if block else ''} तालुक्यातील गाव आहे.",
                source_changed_at=v.updated_at,
            )
        )
    return drafts


def _scheme_drafts(db: Session) -> list[Draft]:
    drafts: list[Draft] = []
    for s in db.scalars(select(Scheme)):
        drafts.append(
            Draft(
                entity_type="scheme",
                entity_id=s.id,
                # Schemes are central or state-level, so they belong to no single
                # village and stay searchable from every one.
                village_id=None,
                content=(
                    f"{s.name} is a {s.level}-level {s.category} scheme. "
                    f"{s.description} Benefit: {s.benefit}."
                ),
                content_mr=f"{s.name_mr}: {s.benefit_mr or ''}",
                source_changed_at=s.updated_at,
            )
        )
    return drafts


def _grievance_drafts(db: Session) -> list[Draft]:
    drafts: list[Draft] = []
    for g in db.scalars(select(Grievance)):
        resolved = (
            f" It was resolved on {g.resolved_date}."
            if g.resolved_date
            else " It is not yet resolved."
        )
        drafts.append(
            Draft(
                entity_type="grievance",
                entity_id=g.id,
                village_id=g.village_id,
                content=(
                    f'A {g.priority.lower()}-priority {g.category.lower()} complaint in ward '
                    f'{g.ward}: "{g.title}". {g.description} It was filed on '
                    f"{g.submitted_date}, is assigned to {g.department}, and its status "
                    f"is {g.status}.{resolved}"
                ),
                content_mr=f"{g.title_mr} — प्रभाग {g.ward}, स्थिती {g.status_mr}.",
                # The 'filed by' link holds an internal id and is never embedded
                # or sent anywhere; it records who the complaint belongs to so
                # the officer UI can resolve it locally. Expansion will not
                # follow it to a chunk, because residents are not indexed.
                links=_links(
                    _link("citizen", g.citizen_id, "filed by"),
                    _link("village", g.village_id, "in village"),
                ),
                source_changed_at=g.updated_at,
            )
        )
    return drafts


def _project_drafts(db: Session) -> list[Draft]:
    drafts: list[Draft] = []
    for p in db.scalars(select(Project)):
        budget = float(p.budget)
        used = float(p.utilized)
        share = f"{used / budget * 100:.0f}%" if budget else "0%"
        drafts.append(
            Draft(
                entity_type="project",
                entity_id=p.id,
                village_id=p.village_id,
                content=(
                    f"{p.name} is a development project at {p.location} in ward {p.ward}. "
                    f"{p.description} It is {p.progress}% complete and its status is "
                    f"{p.status}. Budget ₹{budget:,.0f}, of which ₹{used:,.0f} ({share}) "
                    f"has been spent."
                ),
                content_mr=f"{p.name_mr} — प्रभाग {p.ward}, {p.progress}% पूर्ण, {p.status_mr}.",
                links=_links(_link("village", p.village_id, "in village")),
                source_changed_at=p.updated_at,
            )
        )
    return drafts


def _facility_drafts(db: Session) -> list[Draft]:
    drafts: list[Draft] = []
    for f in db.scalars(select(Facility)):
        ward = f" in ward {f.ward}" if f.ward else ""
        drafts.append(
            Draft(
                entity_type="facility",
                entity_id=f.id,
                village_id=f.village_id,
                content=(
                    f"{f.name} is a {f.facility_type} facility{ward}. {f.details or ''}"
                ).strip(),
                content_mr=f.name_mr,
                links=_links(_link("village", f.village_id, "in village")),
                source_changed_at=f.updated_at,
            )
        )
    return drafts


def _meeting_drafts(db: Session) -> list[Draft]:
    drafts: list[Draft] = []
    stmt = select(SabhaMeeting).options(selectinload(SabhaMeeting.action_items))
    for m in db.scalars(stmt):
        decisions = " ".join(m.decisions or [])
        pending = [a for a in m.action_items if a.status != "Completed"]
        follow_up = (
            f" {len(pending)} of its {len(m.action_items)} follow-up tasks are still open."
            if m.action_items
            else ""
        )
        drafts.append(
            Draft(
                entity_type="sabha_meeting",
                entity_id=m.id,
                village_id=m.village_id,
                content=(
                    f"A Gram Sabha meeting on {m.meeting_date}: {m.title}. {m.summary} "
                    f"Decisions taken: {decisions}{follow_up}"
                ),
                content_mr=f"{m.title_mr} — {m.summary_mr or ''}",
                links=_links(_link("village", m.village_id, "in village")),
                source_changed_at=m.updated_at,
            )
        )
    return drafts


def build_drafts(db: Session) -> list[Draft]:
    """Every indexable record in the database, as sentences with links.

    Residents are absent by design, not by omission — see the module docstring.
    Nothing that describes an individual is embedded, because embedding it means
    sending it to Google.
    """
    return [
        *_village_drafts(db),
        *_scheme_drafts(db),
        *_grievance_drafts(db),
        *_project_drafts(db),
        *_facility_drafts(db),
        *_meeting_drafts(db),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Writing the index
# ─────────────────────────────────────────────────────────────────────────────

def _needs_embedding(existing: KnowledgeChunk | None, draft: Draft) -> bool:
    if existing is None or existing.embedding is None:
        return True
    # Content edited since it was embedded — the old vector no longer describes it.
    if existing.content != draft.content:
        return True
    if existing.embedding_model != settings.GEMINI_EMBED_MODEL:
        return True
    if draft.source_changed_at and existing.indexed_at:
        return draft.source_changed_at > existing.indexed_at
    return False


async def reindex(db: Session, *, force: bool = False) -> dict:
    """Bring the chunk table in line with the database.

    Returns counts rather than printing, so both the CLI and a future admin
    endpoint can report the same numbers.
    """
    drafts = build_drafts(db)
    existing = {c.id: c for c in db.scalars(select(KnowledgeChunk))}
    seen: set[str] = set()

    stale: list[tuple[KnowledgeChunk, Draft]] = []
    unchanged = 0

    for draft in drafts:
        seen.add(draft.chunk_id)
        chunk = existing.get(draft.chunk_id)

        if chunk is None:
            chunk = KnowledgeChunk(
                id=draft.chunk_id,
                entity_type=draft.entity_type,
                entity_id=draft.entity_id,
            )
            db.add(chunk)

        must_embed = force or _needs_embedding(chunk, draft)

        chunk.content = draft.content
        chunk.content_mr = draft.content_mr
        chunk.village_id = draft.village_id
        chunk.meta = {"links": draft.links}

        if must_embed:
            stale.append((chunk, draft))
        else:
            unchanged += 1

    # A record deleted from the database must not linger in the index, or the
    # assistant will keep citing a grievance that no longer exists.
    removed = 0
    for chunk_id, chunk in existing.items():
        if chunk_id not in seen:
            db.delete(chunk)
            removed += 1

    db.commit()

    embedded = 0
    failure: str | None = None
    if stale:
        try:
            for start in range(0, len(stale), BATCH):
                window = stale[start : start + BATCH]
                vectors = await embed([c.content for c, _ in window])
                if len(vectors) != len(window):
                    raise LLMUnavailable(
                        "The embedding service returned a different number of vectors "
                        "than it was given texts."
                    )
                now = datetime.now(timezone.utc)
                for (chunk, _), vector in zip(window, vectors):
                    chunk.embedding = vector
                    chunk.embedding_model = settings.GEMINI_EMBED_MODEL
                    chunk.indexed_at = now
                    embedded += 1
                db.commit()
        except LLMUnavailable as exc:
            # Partial progress is kept: whatever embedded before the failure is
            # committed and usable, and the next run picks up where this stopped.
            db.commit()
            failure = str(exc)

    return {
        "chunks": len(drafts),
        "embedded": embedded,
        "unchanged": unchanged,
        "removed": removed,
        "pending": len(stale) - embedded,
        "error": failure,
    }
