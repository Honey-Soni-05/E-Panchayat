"""Writing down what happened to a complaint or a work.

Both histories are append-only and both are read by the person on the other
side of the counter: a resident follows their complaint through
`GrievanceEvent`, and through `ProjectEvent` once it has become a work. Every
change goes through one of these two functions, so the timeline somebody is
shown is the record of what was done rather than a story reconstructed from the
current state.

They live here rather than in a router because the rules that move a complaint
or a work — `services.demand`, `services.works` — have to write history too,
and a service that imported it from a router would have the dependency pointing
the wrong way.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core import clock
from app.models import Grievance, GrievanceEvent, Project, ProjectEvent, User


def grievance_event(
    db: Session,
    grievance: Grievance,
    event_type: str,
    actor: User | None,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
    note_mr: str | None = None,
    actor_name: str | None = None,
) -> None:
    """Record one step in a complaint's history.

    `actor` is None for something the system did by rule — raising a priority
    because more residents reported the same problem, say. `actor_name` then
    says so, because an entry with no author reads as though someone hid it.
    """
    db.add(GrievanceEvent(
        id=f"gev_{uuid4().hex[:12]}",
        grievance_id=grievance.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
        note_mr=note_mr,
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else actor_name,
        # Stamped here rather than left to the column default, which is only
        # evaluated when the row is flushed. Two entries written in one request
        # must keep the order they were written in.
        created_at=clock.now(),
    ))


def project_event(
    db: Session,
    project: Project,
    event_type: str,
    actor: User | None,
    *,
    from_stage: str | None = None,
    to_stage: str | None = None,
    note: str | None = None,
    note_mr: str | None = None,
    actor_name: str | None = None,
) -> None:
    """Record one step in a work's history."""
    db.add(ProjectEvent(
        id=f"pev_{uuid4().hex[:12]}",
        project_id=project.id,
        event_type=event_type,
        from_stage=from_stage,
        to_stage=to_stage,
        note=note,
        note_mr=note_mr,
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else actor_name,
        created_at=clock.now(),
    ))
