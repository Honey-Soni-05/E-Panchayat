"""Reading the audit trail.

Admin only, and that is a privacy decision rather than a hierarchy one. This
table records who opened whose file, so it is more revealing than most of the
records it describes: an officer who could read it would learn which residents
their colleagues have been looking at. Writing to it happens in middleware and
is available to nobody.

There is no endpoint to delete or amend an event. An audit trail that its
subjects can edit is not one, and retention is handled by
`services.audit.prune()` rather than by a route.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models import AuditEvent, User
from app.schemas import AuditEventOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=list[AuditEventOut])
def list_events(
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    limit: int = Query(default=100, le=500),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditEvent]:
    """The trail, newest first.

    The filters are the two questions this exists to answer: everything that
    touched one record (`entity_type` + `entity_id`), and everything one person
    did (`actor_id`).
    """
    stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc())

    if entity_type:
        stmt = stmt.where(AuditEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditEvent.entity_id == entity_id)
    if actor_id:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)

    return list(db.scalars(stmt.limit(limit)))
