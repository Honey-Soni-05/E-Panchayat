"""Development projects and budget tracking."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_officer, village_scope
from app.db.session import get_db
from app.models import Project, User
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])

STATUS_MR = {"Ongoing": "सुरू असलेले", "Completed": "पूर्ण झालेले", "Delayed": "विलंब झालेला"}


@router.get("", response_model=list[ProjectOut])
def list_projects(
    status_filter: str | None = None,
    ward: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Project]:
    stmt = select(Project)
    scope = village_scope(user)
    if scope is not None:
        stmt = stmt.where(Project.village_id == scope)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    if ward is not None:
        stmt = stmt.where(Project.ward == ward)
    return list(db.scalars(stmt.order_by(Project.ward, Project.name)))


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No project with that ID.")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> Project:
    project_id = body.id or f"proj_{uuid4().hex[:10]}"
    if db.get(Project, project_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "That project ID is already in use.")
    project = Project(
        id=project_id,
        village_id=village_scope(officer),
        **body.model_dump(exclude={"id"}),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No project with that ID.")

    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(project, field, value)

    # Keep the Marathi status label in step whenever status changes, and treat
    # 100% progress as completion unless an officer said otherwise.
    if "status" in data:
        project.status_mr = STATUS_MR.get(project.status, project.status_mr)
    elif project.progress == 100 and project.status != "Completed":
        project.status = "Completed"
        project.status_mr = STATUS_MR["Completed"]

    if float(project.utilized) > float(project.budget):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Utilised amount cannot exceed the sanctioned budget.",
        )

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> None:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No project with that ID.")
    db.delete(project)
    db.commit()
