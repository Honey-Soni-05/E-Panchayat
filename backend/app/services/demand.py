"""How many residents have the same problem, and what that does to its priority.

When thirty people report the same dark lane, that is one problem that thirty
people have, and it matters more than a problem one person has. Two things
follow, and this module does both:

  * the complaints are recognised as being about the same thing, so an officer
    can answer them with one work instead of thirty;
  * the priority of every one of them goes up as the number of residents
    reporting it grows.

**How "the same problem" is decided.** Rules, not a model: the same village, the
same ward, the same category, the same kind of request (a repair or new work),
both still open, and at least one specific keyword in common — "streetlight",
"drain", "hand pump". Words every complaint in a category uses ("water",
"road") are too weak to count on their own; they are used only when a complaint
has nothing more specific to offer.

It is wrong at the edges and it is meant to be read as a suggestion. Two
different leaks in one ward will be grouped; a power cut described as "no
electricity" and one described as "outage" will not. An officer sees the
suggested group and chooses what to link, and nothing is merged or deleted
either way — every resident keeps their own complaint.

**What it does to priority.** The number that counts is residents, not
complaints: one person filing three times is one person.

    3 or more residents   one level higher than the complaint's own wording gave
    5 or more residents   two levels higher

The rise stops at High. Critical is kept for danger — contamination, a live
wire, a collapse — and popularity must not be able to reach it, or it stops
meaning what it says. A priority an officer set by hand is never touched, and
nothing here ever lowers one.

Not used, deliberately: who the residents are. Ranking a complaint by the caste,
income or disability of the people who filed it would mean putting the most
sensitive fields in this system to work in a place nobody asked them to be. The
count is enough.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Grievance
from app.services import timeline
from app.services.classifier import CATEGORY_KEYWORDS, PRIORITY_MR, classify

PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]
# The highest priority that numbers alone can reach.
DEMAND_CEILING = "High"

# (residents reporting, levels raised) — checked in order, first match wins.
DEMAND_STEPS: list[tuple[int, int]] = [(5, 2), (3, 1)]

# Present in nearly every complaint of their category, so sharing one says
# nothing about whether two complaints are about the same thing.
GENERIC_TERMS = {
    "water", "supply", "पाणी",
    "electricity", "power", "वीज",
    "road", "street", "transport", "रस्ता", "वाहतूक",
    "health", "आरोग्य",
    "dirty", "waste", "स्वच्छता",
}


def _terms(grievance: Grievance) -> set[str]:
    """The keywords that say what this complaint is specifically about."""
    text = f"{grievance.title} {grievance.description}".lower()
    found = {
        word.lower()
        for word in CATEGORY_KEYWORDS.get(grievance.category, [])
        if word.lower() in text
    }
    specific = found - GENERIC_TERMS
    # Fall back to the generic words only when they are all there is. "No water
    # for three days" has nothing more specific to match on, and should still
    # find the neighbour who wrote the same sentence.
    return specific or found


def _same_reporter(a: Grievance, b: Grievance) -> bool:
    return bool(a.citizen_id) and a.citizen_id == b.citizen_id


def similar_open(db: Session, grievance: Grievance) -> list[Grievance]:
    """Other unresolved complaints about the same problem, newest first."""
    mine = _terms(grievance)
    if not mine:
        return []

    candidates = db.scalars(
        select(Grievance)
        .where(
            Grievance.id != grievance.id,
            Grievance.village_id == grievance.village_id,
            Grievance.ward == grievance.ward,
            Grievance.category == grievance.category,
            Grievance.request_type == grievance.request_type,
            Grievance.status != "Resolved",
        )
        .order_by(Grievance.submitted_date.desc())
    )
    return [g for g in candidates if mine & _terms(g)]


def other_reporters(grievance: Grievance, similar: list[Grievance]) -> int:
    """How many *other* residents the similar complaints represent.

    A walk-in complaint has no resident record behind it, so each one counts as
    its own person; there is no way to tell two of them are the same visitor,
    and assuming they are would undercount.
    """
    return len({
        g.citizen_id or g.id
        for g in similar
        if not _same_reporter(grievance, g)
    })


def boosted(base: str, residents: int) -> str:
    """The priority a complaint is entitled to, given who else has reported it."""
    if base not in PRIORITY_ORDER:
        return base
    ceiling = PRIORITY_ORDER.index(DEMAND_CEILING)
    start = PRIORITY_ORDER.index(base)
    if start >= ceiling:
        return base
    for threshold, levels in DEMAND_STEPS:
        if residents >= threshold:
            return PRIORITY_ORDER[min(start + levels, ceiling)]
    return base


def apply_demand(db: Session, grievance: Grievance) -> int:
    """Re-rank an open problem after a complaint joins it.

    Returns the number of residents now reporting it, this one included. Every
    complaint in the group is lifted, not only the newest — the fourth person to
    report a dark lane has made it more urgent for the first three as well.
    """
    if grievance.status == "Resolved":
        return 1

    similar = similar_open(db, grievance)
    residents = other_reporters(grievance, similar) + 1

    for member in (grievance, *similar):
        # An officer who set a priority by hand has made a decision. A count
        # does not get to overrule it.
        if not member.auto_classified:
            continue
        base = classify(member.title, member.description).priority
        target = boosted(base, residents)
        if PRIORITY_ORDER.index(target) <= PRIORITY_ORDER.index(member.priority):
            continue

        previous = member.priority
        member.priority = target
        member.priority_mr = PRIORITY_MR[target]
        timeline.grievance_event(
            db, member, "priority_changed", None,
            actor_name="Raised automatically",
            note=(
                f"Priority raised from {previous} to {target}: {residents} residents "
                f"have now reported this problem in ward {member.ward}."
            ),
            note_mr=(
                f"प्राधान्य {PRIORITY_MR.get(previous, previous)} वरून {PRIORITY_MR[target]} "
                f"करण्यात आले: प्रभाग {member.ward} मधील {residents} रहिवाशांनी ही "
                f"समस्या नोंदवली आहे."
            ),
        )
    return residents


def counts_for(db: Session, grievances: list[Grievance]) -> dict[str, int]:
    """For each complaint in a list, how many other residents report the same.

    One query for the whole list rather than one per row. A resident is told
    the number and nothing else — not who the others are, and not what they
    wrote — so this can be shown to someone who may see only their own
    complaint.
    """
    open_ones = [g for g in grievances if g.status != "Resolved"]
    if not open_ones:
        return {}

    villages = {g.village_id for g in open_ones}
    stmt = select(Grievance).where(Grievance.status != "Resolved")
    if None not in villages:
        stmt = stmt.where(Grievance.village_id.in_(villages))

    buckets: dict[tuple, list[Grievance]] = {}
    for g in db.scalars(stmt):
        key = (g.village_id, g.ward, g.category, g.request_type)
        buckets.setdefault(key, []).append(g)

    counts: dict[str, int] = {}
    for g in open_ones:
        mine = _terms(g)
        if not mine:
            continue
        key = (g.village_id, g.ward, g.category, g.request_type)
        similar = [o for o in buckets.get(key, []) if o.id != g.id and mine & _terms(o)]
        if similar:
            counts[g.id] = other_reporters(g, similar)
    return counts
