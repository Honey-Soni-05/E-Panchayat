"""Digital locker: citizens upload, officers verify."""

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import assert_can_read_citizen, get_current_user, require_officer
from app.db.session import get_db
from app.models import Citizen, CitizenDocument, User
from app.schemas import DocumentOut, DocumentReview

router = APIRouter(tags=["documents"])

UPLOAD_ROOT = Path("uploads/documents")
MAX_BYTES = 10 * 1024 * 1024
ALLOWED = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
STATUS_MR = {
    "Pending Verification": "पडताळणी प्रलंबित",
    "Verified": "पडताळणी पूर्ण",
    "Rejected": "नाकारले",
}


def _to_out(d: CitizenDocument) -> DocumentOut:
    return DocumentOut(
        id=d.id, citizen_id=d.citizen_id,
        citizen_name=d.citizen.name if d.citizen else None,
        doc_type=d.doc_type, doc_type_mr=d.doc_type_mr,
        file_name=d.file_name, status=d.status, status_mr=d.status_mr,
        submitted_date=d.submitted_date, verified_at=d.verified_at,
        rejection_reason=d.rejection_reason, size_bytes=d.size_bytes,
    )


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    citizen_id: str | None = None,
    status_filter: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentOut]:
    stmt = select(CitizenDocument)

    if user.role == "citizen":
        if not user.citizen_id:
            return []
        stmt = stmt.where(CitizenDocument.citizen_id == user.citizen_id)
    elif citizen_id:
        stmt = stmt.where(CitizenDocument.citizen_id == citizen_id)

    if status_filter:
        stmt = stmt.where(CitizenDocument.status == status_filter)

    docs = db.scalars(stmt.order_by(CitizenDocument.submitted_date.desc()))
    return [_to_out(d) for d in docs]


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    # Aliased so multipart fields match the camelCase the rest of the API uses.
    citizen_id: str = Form(..., alias="citizenId"),
    doc_type: str = Form(..., alias="docType"),
    doc_type_mr: str = Form("", alias="docTypeMr"),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    assert_can_read_citizen(db, user, citizen_id)

    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No citizen with that ID.")
    if file.content_type not in ALLOWED:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Upload a PDF, JPEG, PNG or WebP file.",
        )

    payload = await file.read()
    if len(payload) > MAX_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"That file is {len(payload) / 1_048_576:.1f} MB. The limit is 10 MB.",
        )

    doc_id = f"doc_{uuid4().hex[:10]}"
    suffix = Path(file.filename or "").suffix[:10]
    target_dir = UPLOAD_ROOT / citizen_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{doc_id}{suffix}"
    target.write_bytes(payload)

    document = CitizenDocument(
        id=doc_id,
        citizen_id=citizen_id,
        doc_type=doc_type,
        doc_type_mr=doc_type_mr or doc_type,
        file_name=file.filename or target.name,
        storage_path=str(target),
        content_type=file.content_type,
        size_bytes=len(payload),
        status="Pending Verification",
        status_mr=STATUS_MR["Pending Verification"],
        submitted_date=date.today(),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _to_out(document)


@router.get("/documents/{document_id}/file")
def download_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Serve the stored file itself.

    Without this the verification screen asks an officer to approve or reject a
    document they cannot read, which makes the review a rubber stamp — and
    makes the requirement to give a reason for rejection meaningless, because
    there is nothing to form a reason about.

    The same permission rule as every other document route: the resident it
    belongs to, an officer of their village, or an admin. A document id is not
    a capability.
    """
    document = db.get(CitizenDocument, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No document with that ID.")

    assert_can_read_citizen(db, user, document.citizen_id)

    if not document.storage_path:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "This record has no file attached. It was created as sample data "
            "rather than uploaded, so there is nothing to open.",
        )

    path = Path(document.storage_path)
    if not path.is_file():
        # The row survived but the file did not — a redeployed container with
        # ephemeral disk is the usual cause. Say so, rather than a bare 404
        # that looks like a permissions problem.
        raise HTTPException(
            status.HTTP_410_GONE,
            "The stored file is missing from the server. It may have been lost "
            "when the service restarted. Ask the resident to upload it again.",
        )

    return FileResponse(
        path,
        media_type=document.content_type or "application/octet-stream",
        # inline, not attachment: an officer verifying a document wants to look
        # at it, not download it.
        content_disposition_type="inline",
        filename=document.file_name,
    )


@router.post("/documents/{document_id}/review", response_model=DocumentOut)
def review_document(
    document_id: str,
    body: DocumentReview,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> DocumentOut:
    """Verify or reject an uploaded document. Feeds straight into eligibility."""
    document = db.get(CitizenDocument, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No document with that ID.")
    if body.status == "Rejected" and not body.rejection_reason:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Give a reason when rejecting, so the citizen knows what to fix.",
        )

    document.status = body.status
    document.status_mr = STATUS_MR[body.status]
    document.verified_at = datetime.now(timezone.utc)
    document.verified_by_id = officer.id
    document.rejection_reason = body.rejection_reason if body.status == "Rejected" else None

    db.commit()
    db.refresh(document)
    return _to_out(document)
