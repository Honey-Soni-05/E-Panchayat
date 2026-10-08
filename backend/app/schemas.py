"""Pydantic request/response models.

Every schema serialises to camelCase (`name_mr` → `nameMr`) so the existing
React components keep the field names they already use, while Python keeps
snake_case. Requests accept either spelling.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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
    village_id: str | None = None
    is_active: bool
    last_login_at: datetime | None = None


class UserCreate(ApiModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str
    role: Role = "citizen"
    citizen_id: str | None = None
    # Required for an officer: the Gram Panchayat they serve. Ignored for a
    # resident, whose account takes the village on their own record, and for an
    # admin, who has none.
    village_id: str | None = None


class RegistrationCreate(ApiModel):
    """A resident applying for a portal account.

    Note there is no `role` field. Self-registration always produces a citizen
    account; officer and admin accounts are created by an admin.
    """

    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)
    phone: str | None = Field(default=None, max_length=30)
    claimed_ward: int | None = Field(default=None, ge=1, le=50)
    claimed_citizen_id: str | None = None
    village_id: str | None = None
    note: str | None = None


class RegistrationOut(ApiModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str | None = None
    claimed_ward: int | None = None
    claimed_citizen_id: str | None = None
    note: str | None = None
    village_id: str | None = None
    status: Literal["pending", "approved", "rejected"]
    matched_citizen_id: str | None = None
    review_note: str | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    # Residents whose name or phone resembles the application, so an officer
    # is choosing from candidates rather than searching from scratch.
    suggested_matches: list[dict] = []


class RegistrationDecision(ApiModel):
    approve: bool
    # Required when approving: which resident record this account belongs to.
    citizen_id: str | None = None
    review_note: str | None = None


class PasswordChange(ApiModel):
    current_password: str
    new_password: str = Field(min_length=8)


class AuditEventOut(ApiModel):
    """One entry in the audit trail.

    No request body is carried, because none is stored — see the note on
    `AuditEvent` in `models.py`.
    """

    id: str
    actor_id: str | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    action: str
    method: str
    path: str
    status_code: int
    entity_type: str | None = None
    entity_id: str | None = None
    village_id: str | None = None
    ip: str | None = None
    created_at: datetime


class PasswordResetIssued(ApiModel):
    """What the officer sees after issuing a reset — once.

    The code is in this response and nowhere else readable: the database keeps
    only a bcrypt hash of it. If the officer loses it before the resident has
    it, the fix is to issue another, which is cheap and invalidates this one.
    """

    code: str
    expires_at: datetime
    user_email: str
    user_name: str


class PasswordResetRedeem(ApiModel):
    """A resident setting their own password with a code from the office.

    The officer never sees this password. They hand over a code that permits
    setting one; what gets set is between the resident and the server.
    """

    email: EmailStr
    code: str
    new_password: str = Field(min_length=8)


# ─────────────────────────────────────────────────────────────────────────────
# Administrative hierarchy
# ─────────────────────────────────────────────────────────────────────────────

class PublicVillage(ApiModel):
    """The little that an unauthenticated visitor may see about a village.

    The block, district and state ride along because an applicant choosing
    their Gram Panchayat should be able to see where it sits — a village name
    on its own is ambiguous across a state, and several names repeat. All of it
    is published Local Government Directory data.
    """

    id: str
    name: str
    name_mr: str
    lgd_code: int | None = None
    block_name: str
    block_name_mr: str
    district_name: str
    district_name_mr: str
    state_name: str
    state_name_mr: str


class VillageOut(ApiModel):
    id: str
    name: str
    name_mr: str
    lgd_code: int | None = None
    census_code_2011: int | None = None
    block_id: str
    block_name: str
    block_name_mr: str
    district_name: str
    district_name_mr: str
    state_name: str
    state_name_mr: str
    latitude: float | None = None
    longitude: float | None = None
    population_2011: int | None = None
    households_2011: int | None = None
    ward_count: int = 0
    # 'active' | 'merged_into_municipal_corporation' | 'uncertain'
    gram_panchayat_status: str = "active"
    notes: str | None = None


class VillageDetail(VillageOut):
    registered_citizens: int = 0
    open_grievances: int = 0
    active_projects: int = 0


class VillageSummary(ApiModel):
    """One row of the district rollup."""

    id: str
    name: str
    name_mr: str
    lgd_code: int | None = None
    population_2011: int | None = None
    gram_panchayat_status: str
    registered_citizens: int
    open_grievances: int
    active_projects: int


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

    # Attributes real scheme rules depend on. All synthetic in this project.
    social_category: Literal["Open", "SC", "ST", "OBC", "SEBC", "VJNT", "SBC"] | None = None
    is_bpl: bool = False
    secc_listed: bool = False
    ration_card_type: Literal["Yellow", "Orange", "White", "AAY", "Annapurna"] | None = None
    land_holding_hectares: float | None = Field(default=None, ge=0)
    marital_status: Literal["Single", "Married", "Widowed", "Divorced", "Abandoned"] | None = None
    disability_percent: int | None = Field(default=None, ge=0, le=100)


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
    village_id: str | None = None
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
    level: Literal["central", "state", "district", "panchayat"] = "state"
    category: str | None = None
    announced_on: date | None = None
    source_url: str | None = None
    confidence: Literal["high", "medium", "low"] = "medium"
    notes: str | None = None


class SchemeCreate(SchemeBase):
    id: str | None = None


class SchemeReadResult(ApiModel):
    """What came back from reading a Government Resolution.

    The extra fields exist so the officer reviewing the proposal sees what the
    reader could not handle, rather than only what it managed. A confident-looking
    scheme with three silently dropped conditions is the failure this guards
    against.
    """

    scheme: "SchemeOut"
    # Eligibility conditions in the GR that no automatic rule can express.
    unmappable_conditions: list[str] = []
    # Criteria the reader proposed that this system does not evaluate.
    discarded_criteria: list[str] = []
    confidence_note: str | None = None
    needs_manual_review: bool = False


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


EligibilityStatus = Literal["Eligible", "Missing Documents", "Needs Review", "Ineligible"]


class EligibilityResult(ApiModel):
    citizen_id: str
    citizen_name: str
    citizen_name_mr: str
    ward: int
    scheme_id: str
    scheme_name: str
    scheme_name_mr: str
    status: EligibilityStatus
    status_mr: str
    criteria_passed: bool
    failed_criteria: list[str] = []
    missing_documents: list[DocumentGap] = []
    unverified_documents: list[DocumentGap] = []
    # Attributes the resident record does not hold, so a rule could not be run.
    unknown_attributes: list[str] = []
    explanation: str
    explanation_mr: str


# ─────────────────────────────────────────────────────────────────────────────
# Grievances
# ─────────────────────────────────────────────────────────────────────────────

Priority = Literal["Low", "Medium", "High", "Critical"]
GrievanceStatus = Literal["Pending", "In Progress", "Resolved"]
# 'service' is a repair to something that exists; 'development' is a request
# for something new, which has to become a project to be answered.
RequestType = Literal["service", "development"]


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
    request_type: RequestType | None = None
    requested_quantity: int | None = Field(default=None, ge=1, le=9999)


class GrievanceUpdate(ApiModel):
    status: GrievanceStatus | None = None
    priority: Priority | None = None
    category: str | None = None
    officer_notes: str | None = None
    department: str | None = None
    # The officer's confirmation or correction of what the rules suggested.
    request_type: RequestType | None = None
    requested_quantity: int | None = Field(default=None, ge=1, le=9999)


class GrievanceFeedback(ApiModel):
    """The resident's answer once the office has marked a complaint resolved."""

    resolved: bool
    # Required when the answer is no: what is still wrong.
    note: str | None = Field(default=None, max_length=1000)


class GrievanceEventOut(ApiModel):
    id: str
    event_type: str
    from_status: str | None = None
    to_status: str | None = None
    note: str | None = None
    note_mr: str | None = None
    actor_name: str | None = None
    created_at: datetime


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
    village_id: str | None = None

    request_type: RequestType = "service"
    request_type_mr: str | None = None
    requested_quantity: int | None = None
    # The work this complaint led to, once an officer has linked it to one.
    project_id: str | None = None
    # How many *other* residents have reported the same problem. A count and
    # nothing else, so it is safe to show someone who may see only their own
    # complaint.
    similar_count: int = 0
    # 'confirmed' | 'reopened' — the resident's answer after resolution.
    citizen_feedback: str | None = None
    feedback_note: str | None = None
    feedback_at: datetime | None = None


class ProjectEventOut(ApiModel):
    """One entry in a work's history. Defined here, ahead of the project
    schemas, because a complaint's detail view carries its work's history."""

    id: str
    event_type: str
    from_stage: str | None = None
    to_stage: str | None = None
    note: str | None = None
    note_mr: str | None = None
    actor_name: str | None = None
    created_at: datetime


class ProjectBrief(ApiModel):
    """What a resident is shown about the work their complaint became.

    Plain enough to read without knowing how a Panchayat budgets: what stage it
    is at, whether the money has been approved and has arrived, how much of the
    work exists, and when it is expected. All of it is public within the
    village; none of it is about any other resident.
    """

    id: str
    name: str
    name_mr: str
    stage: str
    stage_label: str
    stage_label_mr: str
    # Position in the eight-step sequence, for drawing progress. Null when the
    # work has been rejected or put on hold.
    stage_index: int | None = None
    stage_total: int = 8
    status: str
    status_mr: str
    decision_note: str | None = None
    estimated: float | None = None
    requested: float | None = None
    approved: float | None = None
    received: float = 0
    spent: float = 0
    units_planned: int | None = None
    units_done: int = 0
    unit_label: str | None = None
    unit_label_mr: str | None = None
    physical_percent: int = 0
    expected_completion: date | None = None
    # Other residents whose complaints led to the same work — a count only.
    linked_grievances: int = 0
    history: list[ProjectEventOut] = []


class GrievanceDetail(GrievanceOut):
    """A single complaint with its full history — what the citizen's tracking
    view reads."""

    events: list[GrievanceEventOut] = []
    project: ProjectBrief | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────────────────────

class ProjectCreate(ApiModel):
    """A work that is already under way, registered from its two totals.

    The Marathi fields are optional and fall back to the English, as they do on
    a complaint. They used to be required here while the form that posts to
    this left them out unless the officer typed them, so registering a work
    from the screen was refused every time with a list of missing fields.
    """

    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    name_mr: str | None = None
    description: str = ""
    description_mr: str | None = None
    progress: int = Field(default=0, ge=0, le=100)
    budget: float = Field(ge=0)
    utilized: float = Field(default=0, ge=0)
    status: Literal["Ongoing", "Completed", "Delayed"] = "Ongoing"
    # Accepted and ignored: the Marathi label is derived from `status`.
    status_mr: str | None = None
    ward: int
    location: str = Field(min_length=1, max_length=255)
    location_mr: str | None = None
    latitude: float
    longitude: float
    start_date: date | None = None
    expected_completion: date | None = None


class ProjectUpdate(ApiModel):
    progress: int | None = Field(default=None, ge=0, le=100)
    # Still accepted so that an old client gets an explanation rather than
    # silence: spending is a dated ledger entry now, and this is refused with a
    # message saying where to record it.
    utilized: float | None = Field(default=None, ge=0)
    status: Literal["Ongoing", "Completed", "Delayed"] | None = None
    status_mr: str | None = None
    description: str | None = None
    expected_completion: date | None = None
    units_planned: int | None = Field(default=None, ge=1, le=100000)


ProjectStatus = Literal["Planned", "Ongoing", "Delayed", "Completed", "On Hold", "Rejected"]
StageAction = Literal["verify", "approve", "reject", "start", "complete", "hold", "resume"]
EntryKind = Literal["estimate", "requested", "approved", "received", "spent"]


class ProposalCreate(ApiModel):
    """A work somebody thinks should be done. No money and no approval yet.

    Coordinates are optional because an officer turning a complaint into a
    proposal should not have to look them up: they default to the complaint's
    own location, and failing that to the village centre.
    """

    name: str = Field(min_length=3, max_length=255)
    name_mr: str | None = None
    description: str = Field(min_length=3)
    description_mr: str | None = None
    ward: int = Field(ge=1)
    location: str = Field(min_length=2, max_length=255)
    location_mr: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category: str | None = None
    units_planned: int | None = Field(default=None, ge=1, le=100000)
    unit_label: str | None = Field(default=None, max_length=60)
    unit_label_mr: str | None = Field(default=None, max_length=60)
    asset_type: str | None = None
    expected_completion: date | None = None
    # What the officer expects it to cost, if they can say at this point. It is
    # recorded as the first estimate in the ledger, typed by a person and
    # revisable later; leaving it out is fine.
    estimate: float | None = Field(default=None, gt=0, le=1_000_000_000_000)
    estimate_note: str | None = Field(default=None, max_length=1000)
    # The complaints this proposal answers. The first is taken as its origin.
    grievance_ids: list[str] = []
    # Only read for an admin, who has no village of their own. An officer's
    # proposal always belongs to the Gram Panchayat they serve.
    village_id: str | None = None


class StageDecision(ApiModel):
    action: StageAction
    # Required for verify, reject and hold — see services/works.py.
    note: str | None = Field(default=None, max_length=2000)
    # For 'approve': the Gram Sabha meeting the decision was taken in.
    sabha_meeting_id: str | None = None


class BudgetEntryCreate(ApiModel):
    kind: EntryKind
    amount: float = Field(gt=0, le=1_000_000_000_000)
    entry_date: date | None = None
    funding_source: str | None = None
    reference: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


class ProgressUpdate(ApiModel):
    units_done: int | None = Field(default=None, ge=0)
    progress: int | None = Field(default=None, ge=0, le=100)
    note: str | None = Field(default=None, max_length=1000)


class LinkGrievances(ApiModel):
    grievance_ids: list[str] = Field(min_length=1)


class BudgetEntryOut(ApiModel):
    id: str
    kind: str
    kind_label: str
    kind_label_mr: str
    amount: float
    entry_date: date
    funding_source: str | None = None
    funding_source_label: str | None = None
    funding_source_label_mr: str | None = None
    reference: str | None = None
    note: str | None = None
    created_by_name: str | None = None
    created_at: datetime
    # Set on a correction: the entry it puts right. `amount` is then the
    # difference applied, and may be negative.
    corrects_id: str | None = None
    # On an entry that has been corrected: what it stands at now.
    corrected_to: float | None = None
    # Whether a correction may be recorded against this entry.
    can_correct: bool = False


class EntryCorrection(ApiModel):
    """What a receipt or a payment should have been, and why it was wrong."""

    amount: float = Field(ge=0, le=1_000_000_000_000)
    reason: str = Field(min_length=3, max_length=1000)


class ProjectFlag(ApiModel):
    """Something a person should look at. A comparison of recorded figures,
    never a finding that anything is wrong."""

    code: str
    severity: Literal["warning", "info"]
    message: str
    message_mr: str


class ProjectFinance(ApiModel):
    estimated: float | None = None
    requested: float | None = None
    approved: float | None = None
    received: float = 0
    spent: float = 0
    # Sanctioned but not yet arrived, and arrived but not yet paid out.
    awaiting: float = 0
    balance: float = 0
    # Approved less spent — the two above added together.
    remaining: float = 0
    financial_percent: int = 0


class ProjectSteps(ApiModel):
    """What may be done to this work now. The screen offers exactly these."""

    actions: list[str] = []
    entry_kinds: list[str] = []
    can_record_progress: bool = False


class ProjectOut(ApiModel):
    id: str
    village_id: str | None = None
    name: str
    name_mr: str
    description: str
    description_mr: str
    progress: int
    budget: float
    utilized: float
    status: ProjectStatus
    status_mr: str
    ward: int
    location: str
    location_mr: str
    latitude: float
    longitude: float
    start_date: date | None = None
    expected_completion: date | None = None

    stage: str
    stage_label: str
    stage_label_mr: str
    stage_index: int | None = None
    stage_total: int = 8
    stage_changed_at: datetime | None = None
    days_in_stage: int | None = None
    # Where a work on hold will return to when it is resumed.
    held_from_stage: str | None = None
    category: str | None = None
    units_planned: int | None = None
    units_done: int = 0
    unit_label: str | None = None
    unit_label_mr: str | None = None
    asset_type: str | None = None
    physical_percent: int = 0
    funding_source: str | None = None
    funding_source_label: str | None = None
    funding_source_label_mr: str | None = None
    decision_note: str | None = None
    sabha_meeting_id: str | None = None
    financial_year: str | None = None

    finance: ProjectFinance = ProjectFinance()
    flags: list[ProjectFlag] = []
    linked_grievances: int = 0
    # Residents whose complaints led here — people, not complaints.
    residents_affected: int = 0
    steps: ProjectSteps = ProjectSteps()


class LinkedGrievance(ApiModel):
    """A complaint attached to a work, as an officer sees it."""

    id: str
    title: str
    title_mr: str
    ward: int
    status: str
    priority: str
    citizen_name: str
    submitted_date: date
    citizen_feedback: str | None = None
    feedback_note: str | None = None


class ProjectDetail(ProjectOut):
    entries: list[BudgetEntryOut] = []
    events: list[ProjectEventOut] = []
    # Officers only. A resident opening a public work is told how many people
    # asked for it, not who they were.
    grievances: list[LinkedGrievance] = []


# ─────────────────────────────────────────────────────────────────────────────
# Budget
# ─────────────────────────────────────────────────────────────────────────────

class FundingSourceOut(ApiModel):
    code: str
    label: str
    label_mr: str


class BudgetTotals(ApiModel):
    estimated: float = 0
    # Asked for and still awaiting a decision.
    requested_pending: float = 0
    approved: float = 0
    received: float = 0
    spent: float = 0
    awaiting: float = 0
    balance: float = 0
    # Approved less spent: in hand plus still to arrive.
    remaining: float = 0
    utilisation_percent: int = 0


class BudgetProjectRow(ApiModel):
    id: str
    name: str
    name_mr: str
    ward: int
    stage: str
    stage_label: str
    stage_label_mr: str
    status: str
    funding_source: str | None = None
    funding_source_label: str | None = None
    funding_source_label_mr: str | None = None
    estimated: float | None = None
    requested: float | None = None
    approved: float | None = None
    received: float = 0
    spent: float = 0
    balance: float = 0
    remaining: float = 0
    physical_percent: int = 0
    financial_percent: int = 0
    flags: list[ProjectFlag] = []
    # What may be recorded against the work now, so the budget screen can
    # offer an officer the next entry without a second copy of the rules.
    steps: ProjectSteps = ProjectSteps()


class BudgetSourceRow(ApiModel):
    code: str | None = None
    label: str
    label_mr: str
    approved: float = 0
    received: float = 0
    spent: float = 0
    projects: int = 0


class BudgetOverview(ApiModel):
    """The Panchayat's money across all its works: a roll-up of the ledgers.

    Budget tracking, not accounts. Every figure is a sum of entries officers
    recorded against individual works; there are no vouchers behind them and
    nothing here is reconciled against a bank or PFMS.
    """

    financial_year: str | None = None
    financial_years: list[str] = []
    totals: BudgetTotals = BudgetTotals()
    projects: list[BudgetProjectRow] = []
    sources: list[BudgetSourceRow] = []
    stage_counts: dict[str, int] = {}


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


class ActionItemCreate(ApiModel):
    """A follow-up task an officer assigns against a meeting by hand.

    The Marathi fields are optional: an officer typing quickly in one language
    should not be blocked, and the reader falls back to whichever was given
    rather than being shown an empty string.
    """

    action: str = Field(min_length=2, max_length=500)
    action_mr: str | None = None
    responsible: str = Field(min_length=2, max_length=255)
    responsible_mr: str | None = None
    deadline: date | None = None


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
    # More than one when a single work installed several of the same thing.
    quantity: int = 1
    project_id: str | None = None
    installed_on: date | None = None


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
    # Works that exist as proposals but have not started, and the subset of
    # those waiting on a budget decision.
    planned_projects: int = 0
    budget_pending_projects: int = 0


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
    # How the answer was written:
    #   llm                      the model wrote it from retrieved facts
    #   retrieval_only           no model key, or the call failed
    #   retrieval_only_personal  the facts describe one resident, so they were
    #                            deliberately not sent to the model
    # The last two read the same to a user unless they are told apart, and they
    # mean very different things — one is a degraded service, the other is the
    # privacy rule working.
    mode: Literal["llm", "retrieval_only", "retrieval_only_personal", "unavailable"]
    # How the records were found: by embedding similarity plus graph expansion,
    # or by keyword routing. Reported rather than assumed, because the semantic
    # path silently falls back and the reader deserves to know which ran.
    retrieval: Literal["semantic", "keyword"] = "keyword"
