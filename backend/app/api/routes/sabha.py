"""Gram Sabha meetings, transcript processing and action-item tracking."""

from datetime import date, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_officer, village_scope
from app.db.session import get_db
from app.models import SabhaActionItem, SabhaMeeting, User
from app.schemas import (
    ActionItemOut,
    ActionItemUpdate,
    SabhaMeetingCreate,
    SabhaMeetingOut,
)
from app.services.llm import LLMUnavailable
from app.services.transcript import UnsupportedTranscript, extract_text, summarise

router = APIRouter(prefix="/sabha", tags=["gram sabha"])

ACTION_STATUS_MR = {
    "Pending": "प्रलंबित",
    "In Progress": "प्रगतीपथावर",
    "Completed": "पूर्ण झाले",
}
MAX_UPLOAD = 8 * 1024 * 1024


@router.get("/meetings", response_model=list[SabhaMeetingOut])
def list_meetings(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[SabhaMeeting]:
    stmt = select(SabhaMeeting).options(selectinload(SabhaMeeting.action_items))
    scope = village_scope(user)
    if scope is not None:
        stmt = stmt.where(SabhaMeeting.village_id == scope)
    return list(db.scalars(stmt.order_by(SabhaMeeting.meeting_date.desc())))


@router.get("/meetings/{meeting_id}", response_model=SabhaMeetingOut)
def get_meeting(
    meeting_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SabhaMeeting:
    meeting = db.get(SabhaMeeting, meeting_id)
    if meeting is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No meeting with that ID.")
    return meeting


@router.post("/meetings", response_model=SabhaMeetingOut, status_code=status.HTTP_201_CREATED)
def create_meeting(
    body: SabhaMeetingCreate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> SabhaMeeting:
    meeting = SabhaMeeting(
        id=f"sabha_{uuid4().hex[:10]}",
        meeting_date=body.meeting_date,
        title=body.title,
        title_mr=body.title_mr or body.title,
        summary=body.summary,
        summary_mr=body.summary_mr,
        decisions=body.decisions,
        decisions_mr=body.decisions_mr,
        extracted_by="manual",
        village_id=village_scope(officer),
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return meeting


@router.post(
    "/meetings/process",
    response_model=SabhaMeetingOut,
    status_code=status.HTTP_201_CREATED,
)
async def process_transcript(
    file: UploadFile = File(...),
    # Aliased so multipart fields match the camelCase the rest of the API uses.
    meeting_date: date = Form(..., alias="meetingDate"),
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> SabhaMeeting:
    """Read an uploaded minutes file and extract the summary, decisions and
    action items from its actual contents."""
    payload = await file.read()
    if len(payload) > MAX_UPLOAD:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"That file is {len(payload) / 1_048_576:.1f} MB. The limit is 8 MB.",
        )

    try:
        text = extract_text(file.filename or "", payload)
    except UnsupportedTranscript as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        extracted = await summarise(text, meeting_date.isoformat())
    except LLMUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{exc} Save the meeting manually, or set GEMINI_API_KEY on the server.",
        ) from exc

    meeting = SabhaMeeting(
        id=f"sabha_{uuid4().hex[:10]}",
        meeting_date=meeting_date,
        title=extracted.get("title", "Gram Sabha Meeting"),
        title_mr=extracted.get("titleMr", "ग्रामसभा बैठक"),
        summary=extracted.get("summary", ""),
        summary_mr=extracted.get("summaryMr", ""),
        decisions=extracted.get("decisions", []),
        decisions_mr=extracted.get("decisionsMr", []),
        source_file_name=file.filename,
        transcript_text=text,
        extracted_by="llm",
        village_id=village_scope(officer),
    )
    db.add(meeting)
    db.flush()

    for item in extracted.get("actionItems", []):
        deadline = None
        if raw := item.get("deadline"):
            try:
                deadline = datetime.strptime(raw[:10], "%Y-%m-%d").date()
            except ValueError:
                deadline = None  # model gave prose rather than a date; drop it
        db.add(
            SabhaActionItem(
                id=f"act_{uuid4().hex[:10]}",
                meeting_id=meeting.id,
                action=item.get("action", ""),
                action_mr=item.get("actionMr", ""),
                responsible=item.get("responsible", "Not specified"),
                responsible_mr=item.get("responsibleMr", "निर्दिष्ट नाही"),
                deadline=deadline,
                status="Pending",
                status_mr=ACTION_STATUS_MR["Pending"],
            )
        )

    db.commit()
    db.refresh(meeting)
    return meeting


@router.patch("/action-items/{item_id}", response_model=ActionItemOut)
def update_action_item(
    item_id: str,
    body: ActionItemUpdate,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> SabhaActionItem:
    item = db.get(SabhaActionItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No action item with that ID.")

    data = body.model_dump(exclude_unset=True)
    if (new_status := data.get("status")) is not None:
        item.status = new_status
        item.status_mr = ACTION_STATUS_MR[new_status]
    if "responsible" in data and data["responsible"]:
        item.responsible = data["responsible"]
    if "deadline" in data:
        item.deadline = data["deadline"]

    db.commit()
    db.refresh(item)
    return item


@router.get("/action-items", response_model=list[ActionItemOut])
def list_action_items(
    status_filter: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SabhaActionItem]:
    stmt = select(SabhaActionItem)
    if status_filter:
        stmt = stmt.where(SabhaActionItem.status == status_filter)
    return list(db.scalars(stmt.order_by(SabhaActionItem.deadline)))
