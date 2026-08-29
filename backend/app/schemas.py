"""Pydantic request/response models.

Every schema serialises to camelCase (`name_mr` → `nameMr`) so the existing
React components keep the field names they already use, while Python keeps
snake_case. Requests accept either spelling.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def to_camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


Role = Literal["admin", "officer", "citizen"]


# ─────────────────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────────────────

class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenPair(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(ApiModel):
    refresh_token: str


class UserOut(ApiModel):
    id: str
    email: EmailStr
    full_name: str
    role: Role
    citizen_id: str | None = None
    is_active: bool
    last_login_at: datetime | None = None


class UserCreate(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: Role = "citizen"
    citizen_id: str | None = None


class PasswordChange(ApiModel):
    current_password: str
    new_password: str = Field(min_length=8)


# ─────────────────────────────────────────────────────────────────────────────
# Families and citizens
# ─────────────────────────────────────────────────────────────────────────────

class FamilyMemberOut(ApiModel):
    id: str
    name: str
    name_mr: str
    relation: str | None = None
    relation_mr: str | None = None
    age: int
    is_head: bool


class FamilyOut(ApiModel):
    id: str
    name: str
    name_mr: str
    ward: int
    address: str | None = None
    address_mr: str | None = None
    members: list[FamilyMemberOut] = []


class CitizenBase(ApiModel):
    name: str
    name_mr: str
    age: int = Field(ge=0, le=130)
    gender: Literal["Male", "Female", "Other"]
    gender_mr: str
    occupation: str
    occupation_mr: str
    income: float = Field(ge=0)
    ward: int = Field(ge=1)
    phone: str | None = None
    family_id: str | None = None
    relation: str | None = None
    relation_mr: str | None = None
    is_head: bool = False
    date_of_birth: date | None = None


class CitizenCreate(CitizenBase):
    id: str | None = None  # generated when omitted


class CitizenUpdate(ApiModel):
    name: str | None = None
    name_mr: str | None = None
    age: int | None = Field(default=None, ge=0, le=130)
    gender: Literal["Male", "Female", "Other"] | None = None
    gender_mr: str | None = None
    occupation: str | None = None
    occupation_mr: str | None = None
    income: float | None = Field(default=None, ge=0)
    ward: int | None = None
    phone: str | None = None
    family_id: str | None = None
    relation: str | None = None
    relation_mr: str | None = None
    is_head: bool | None = None


class CitizenOut(CitizenBase):
    id: str
    family_name: str | None = None
    family_name_mr: str | None = None
    family_members: list[FamilyMemberOut] = []
    created_at: datetime | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Schemes and eligibility
# ─────────────────────────────────────────────────────────────────────────────

class RequiredDocument(ApiModel):
    name: str
    name_mr: str


class SchemeBase(ApiModel):
    name: str
    name_mr: str
    description: str
    description_mr: str
    benefit: str
    benefit_mr: str
    criteria: dict[str, Any] = {}
    required_documents: list[RequiredDocument] = []
    status: Literal["active", "pending", "rejected"] = "active"
    is_government_feed: bool = False
    source_gov: str | None = None
    form_url: str | None = None


class SchemeCreate(SchemeBase):
    id: str | None = None


class SchemeUpdate(ApiModel):
    name: str | None = None
    name_mr: str | None = None
    description: str | None = None
    description_mr: str | None = None
    benefit: str | None = None
    benefit_mr: str | None = None
    criteria: dict[str, Any] | None = None
    required_documents: list[RequiredDocument] | None = None
    status: Literal["active", "pending", "rejected"] | None = None


class SchemeOut(SchemeBase):
    id: str


class DocumentGap(ApiModel):
    name: str
    name_mr: str
    file_status: str | None = None  # None when the document was never uploaded


class EligibilityResult(ApiModel):
    citizen_id: str
    citizen_name: str
    citizen_name_mr: str
    ward: int
    scheme_id: str
    status: Literal["Eligible", "Missing Documents", "Ineligible"]
    status_mr: str
    criteria_passed: bool
    failed_criteria: list[str] = []
    missing_documents: list[DocumentGap] = []
    unverified_documents: list[DocumentGap] = []
    explanation: str
    explanation_mr: str


# ─────────────────────────────────────────────────────────────────────────────
# Grievances
# ─────────────────────────────────────────────────────────────────────────────

Priority = Literal["Low", "Medium", "High", "Critical"]
GrievanceStatus = Literal["Pending", "In Progress", "Resolved"]


class GrievanceCreate(ApiModel):
    title: str
    title_mr: str | None = None
    description: str
    description_mr: str | None = None
    ward: int
    citizen_name: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Optional overrides; the classifier fills these when omitted.
    category: str | None = None
    priority: Priority | None = None


class GrievanceUpdate(ApiModel):
    status: GrievanceStatus | None = None
    priority: Priority | None = None
    category: str | None = None
    officer_notes: str | None = None
    department: str | None = None


class GrievanceOut(ApiModel):
    id: str
    title: str
    title_mr: str
    description: str
    description_mr: str
    category: str
    category_mr: str
    priority: Priority
    priority_mr: str
    status: GrievanceStatus
    status_mr: str
    department: str
    department_mr: str
    ward: int
    latitude: float | None = None
    longitude: float | None = None
    citizen_id: str | None = None
    citizen_name: str
    phone: str | None = None
    submitted_date: date
    resolved_date: date | None = None
    officer_notes: str | None = None
    auto_classified: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

class ProjectBase(ApiModel):
    name: str
    name_mr: str
    description: str
    description_mr: str
    progress: int = Field(ge=0, le=100)
    budget: float = Field(ge=0)
    utilized: float = Field(ge=0)
    status: Literal["Ongoing", "Completed", "Delayed"]
    status_mr: str
    ward: int
    location: str
    location_mr: str
    latitude: float
    longitude: float
    start_date: date | None = None
    expected_completion: date | None = None


class ProjectCreate(ProjectBase):
    id: str | None = None


class ProjectUpdate(ApiModel):
    progress: int | None = Field(default=None, ge=0, le=100)
    utilized: float | None = Field(default=None, ge=0)
    status: Literal["Ongoing", "Completed", "Delayed"] | None = None
    status_mr: str | None = None
    description: str | None = None
    expected_completion: date | None = None


class ProjectOut(ProjectBase):
    id: str

    @field_validator("budget", "utilized", mode="before")
    @classmethod
    def _decimal_to_float(cls, v: Any) -> Any:
        return float(v) if v is not None else v


# ─────────────────────────────────────────────────────────────────────────────
# Documents
# ─────────────────────────────────────────────────────────────────────────────

class DocumentOut(ApiModel):
    id: str
    citizen_id: str
    citizen_name: str | None = None
    doc_type: str
    doc_type_mr: str
    file_name: str
    status: Literal["Pending Verification", "Verified", "Rejected"]
    status_mr: str
    submitted_date: date
    verified_at: datetime | None = None
    rejection_reason: str | None = None
    size_bytes: int | None = None


class DocumentReview(ApiModel):
    status: Literal["Verified", "Rejected"]
    rejection_reason: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Gram Sabha
# ─────────────────────────────────────────────────────────────────────────────

ActionStatus = Literal["Pending", "In Progress", "Completed"]


class ActionItemOut(ApiModel):
    id: str
    meeting_id: str
    action: str
    action_mr: str
    responsible: str
    responsible_mr: str
    deadline: date | None = None
    status: ActionStatus
    status_mr: str


class ActionItemUpdate(ApiModel):
    status: ActionStatus | None = None
    responsible: str | None = None
    deadline: date | None = None


class SabhaMeetingOut(ApiModel):
    id: str
    meeting_date: date
    title: str
    title_mr: str
    summary: str
    summary_mr: str
    decisions: list[str] = []
    decisions_mr: list[str] = []
    source_file_name: str | None = None
    extracted_by: str | None = None
    action_items: list[ActionItemOut] = []


class SabhaMeetingCreate(ApiModel):
    meeting_date: date
    title: str
    title_mr: str | None = None
    summary: str = ""
    summary_mr: str = ""
    decisions: list[str] = []
    decisions_mr: list[str] = []


# ─────────────────────────────────────────────────────────────────────────────
# GIS and analytics
# ─────────────────────────────────────────────────────────────────────────────

class FacilityOut(ApiModel):
    id: str
    name: str
    name_mr: str
    facility_type: str
    latitude: float
    longitude: float
    ward: int | None = None
    details: str | None = None
    details_mr: str | None = None


class DashboardStats(ApiModel):
    total_citizens: int
    total_families: int
    open_grievances: int
    critical_grievances: int
    resolved_grievances: int
    active_projects: int
    delayed_projects: int
    total_budget: float
    total_utilized: float
    pending_documents: int
    next_meeting_date: date | None = None


class NamedCount(ApiModel):
    label: str
    label_mr: str | None = None
    value: float


# ─────────────────────────────────────────────────────────────────────────────
# Assistant
# ─────────────────────────────────────────────────────────────────────────────

class AssistantQuery(ApiModel):
    query: str = Field(min_length=1, max_length=2000)
    language: Literal["en", "mr"] = "en"


class RetrievedSource(ApiModel):
    entity_type: str
    entity_id: str
    title: str
    score: float | None = None


class AssistantAnswer(ApiModel):
    answer: str
    sources: list[RetrievedSource] = []
    mode: Literal["llm", "retrieval_only", "unavailable"]
