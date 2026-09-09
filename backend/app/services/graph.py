"""Semantic retrieval with graph expansion.

Two steps, and the second is the one that matters.

**Similarity** finds the chunks whose meaning is closest to the question. This
is what keyword routing could not do: "the tap has been dry since Diwali" has
no word in common with a grievance titled "Water supply interruption", but the
vectors are close.

**Expansion** then walks the links each matched chunk carries — the village it
sits in, the ward's other records — and pulls those in too. So a question that
matches one complaint comes back with its context attached, and the model can
describe the situation rather than just restating the complaint.

Expansion used to reach the resident who filed a matched complaint. It no longer
does: `services/indexer` builds no chunk for any resident, so there is nothing
of theirs to walk to. Complaints still carry a 'filed by' link, which holds an
internal id, is never embedded, and is resolved inside the office rather than by
a model. See the indexer's module docstring for why.

Both steps are scoped before they run, not filtered after. A citizen's search
covers their own records and village-level public facts; an officer's covers
their village. The permission check is a WHERE clause on the candidate set, so
there is no path where a vector similar enough could surface someone else's file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Grievance, KnowledgeChunk, User

# Below this, a "match" is noise. Cosine similarity on Gemini's embeddings puts
# genuinely related text well above 0.6; unrelated text sits near 0.3. Returning
# weak matches is worse than returning nothing, because the model treats
# whatever it is given as relevant.
MIN_SIMILARITY = 0.55

# How many neighbours to pull in per matched chunk. Enough to give context,
# few enough that one match cannot flood the prompt.
EXPAND_PER_HIT = 3


@dataclass
class Hit:
    chunk: KnowledgeChunk
    similarity: float
    # False when the chunk arrived by walking a link rather than by matching.
    matched_directly: bool = True
    via: str | None = None


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _visible_chunks(db: Session, user: User, village_id: str | None) -> list[KnowledgeChunk]:
    """The chunks this user is allowed to have searched at all.

    Scoping happens here rather than after ranking, so an excluded record can
    never be surfaced no matter how well it matches.
    """
    stmt = select(KnowledgeChunk).where(KnowledgeChunk.embedding.is_not(None))

    if user.role == "admin":
        return list(db.scalars(stmt))

    # Schemes carry no village (they are central or state programmes) and are
    # public information, so they stay searchable alongside local records.
    if village_id:
        stmt = stmt.where(
            or_(
                KnowledgeChunk.village_id == village_id,
                KnowledgeChunk.village_id.is_(None),
            )
        )
    else:
        stmt = stmt.where(KnowledgeChunk.village_id.is_(None))

    candidates = list(db.scalars(stmt))

    if user.role != "citizen":
        return candidates

    # A citizen sees public village facts, plus their own record and their own
    # grievances — never another resident's file.
    own_grievances = {
        g.id
        for g in db.scalars(select(Grievance).where(Grievance.citizen_id == user.citizen_id))
    }
    allowed_personal = {"citizen": {user.citizen_id or ""}, "grievance": own_grievances}
    public_types = {"village", "scheme", "project", "facility", "sabha_meeting"}

    return [
        c
        for c in candidates
        if c.entity_type in public_types
        or c.entity_id in allowed_personal.get(c.entity_type, set())
    ]


def _expand(
    db: Session,
    hits: list[Hit],
    visible: list[KnowledgeChunk],
) -> list[Hit]:
    """Walk each hit's links and pull in the records it relates to."""
    by_key = {(c.entity_type, c.entity_id): c for c in visible}
    already = {(h.chunk.entity_type, h.chunk.entity_id) for h in hits}
    added: list[Hit] = []

    for hit in hits:
        links = (hit.chunk.meta or {}).get("links") or []
        for link in links[:EXPAND_PER_HIT]:
            key = (link.get("type"), link.get("id"))
            if key in already:
                continue
            # Only reachable if the neighbour was in the visible set to begin
            # with — expansion must not become a way around scoping.
            neighbour = by_key.get(key)
            if neighbour is None:
                continue
            already.add(key)
            added.append(
                Hit(
                    chunk=neighbour,
                    similarity=hit.similarity,
                    matched_directly=False,
                    via=f"{link.get('label', 'related to')} {hit.chunk.entity_type} "
                    f"{hit.chunk.entity_id}",
                )
            )

    return added


def semantic_search(
    db: Session,
    query_vector: list[float],
    user: User,
    village_id: str | None,
    limit: int = 6,
    expand: bool = True,
) -> list[Hit]:
    """Rank the visible chunks against a question, then walk their links.

    Similarity is computed in Python over a scoped candidate set. See the note
    on `KnowledgeChunk` for why that is the right shape at village scale and
    what to change when it stops being.
    """
    visible = _visible_chunks(db, user, village_id)
    if not visible:
        return []

    scored = [
        Hit(chunk=c, similarity=cosine(query_vector, c.embedding or []))
        for c in visible
    ]
    scored = [h for h in scored if h.similarity >= MIN_SIMILARITY]
    scored.sort(key=lambda h: h.similarity, reverse=True)
    top = scored[:limit]

    if not top or not expand:
        return top

    return top + _expand(db, top, visible)


def index_is_ready(db: Session) -> bool:
    """Whether anything has been embedded yet.

    The assistant checks this to decide whether to use semantic retrieval or
    fall back to keyword routing, so an un-indexed deployment degrades to the
    previous behaviour instead of returning nothing.
    """
    return db.scalar(
        select(KnowledgeChunk.id).where(KnowledgeChunk.embedding.is_not(None)).limit(1)
    ) is not None


def describe(hit: Hit, language: str = "en") -> str:
    """The chunk as a line of context for the model."""
    body = hit.chunk.content
    if language == "mr" and hit.chunk.content_mr:
        body = f"{hit.chunk.content} ({hit.chunk.content_mr})"
    if hit.matched_directly:
        return body
    # Telling the model why a record is present stops it treating an incidental
    # neighbour as though it were the subject of the question.
    return f"{body} [included because it is {hit.via}]"
