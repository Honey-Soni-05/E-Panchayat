"""SQLAlchemy models — the single source of truth for the E-Panchayat schema.

Every table below mirrors the TypeScript interfaces the React app is built
around, so the frontend model and the database model can no longer drift.
Bilingual fields follow one convention throughout: `<field>` is English and
`<field>_mr` is Marathi.

Primary keys are short human-readable codes ('cit_101', 'griev_201') rather
than UUIDs, because officers read and quote them and the seed data uses them.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


# ─────────────────────────────────────────────────────────────────────────────
# Administrative hierarchy
#
# India's Local Government Directory (lgdirectory.gov.in) is the official
# registry, and every unit below carries its real LGD code. Modelling the full
# chain — state, district, block, village — rather than a single village field
# means district-level rollups are a query, not a rewrite. Seeding more
# villages is then an insert, not a code change.
# ─────────────────────────────────────────────────────────────────────────────

class State(Base, TimestampMixin):
    __tablename__ = "states"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    lgd_code: Mapped[int | None] = mapped_column(Integer, unique=True)

    districts: Mapped[list[District]] = relationship(back_populates="state")


class District(Base, TimestampMixin):
    __tablename__ = "districts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    lgd_code: Mapped[int | None] = mapped_column(Integer, unique=True)
    state_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True
    )

    state: Mapped[State] = relationship(back_populates="districts")
    blocks: Mapped[list[Block]] = relationship(back_populates="district")


class Block(Base, TimestampMixin):
    """A taluka / tehsil / panchayat samiti, depending on the state's wording."""

    __tablename__ = "blocks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    lgd_code: Mapped[int | None] = mapped_column(Integer, unique=True)
    district_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("districts.id", ondelete="CASCADE"), nullable=False, index=True
    )

    district: Mapped[District] = relationship(back_populates="blocks")
    villages: Mapped[list[Village]] = relationship(back_populates="block")


class Village(Base, TimestampMixin):
    """A village and, where one exists, its Gram Panchayat.

    `gram_panchayat_status` matters and is not decoration: several Haveli
    villages were absorbed into Pune Municipal Corporation in 2017 and 2021 and
    no longer have a Gram Panchayat at all. A platform for Panchayat
    administration has to know the difference.
    """

    __tablename__ = "villages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    lgd_code: Mapped[int | None] = mapped_column(Integer, index=True)
    census_code_2011: Mapped[int | None] = mapped_column(Integer)

    block_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("blocks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    population_2011: Mapped[int | None] = mapped_column(Integer)
    households_2011: Mapped[int | None] = mapped_column(Integer)
    ward_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 'active' | 'merged_into_municipal_corporation' | 'uncertain'
    gram_panchayat_status: Mapped[str] = mapped_column(
        String(48), default="active", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)

    block: Mapped[Block] = relationship(back_populates="villages")


# ─────────────────────────────────────────────────────────────────────────────
# Identity and access
# ─────────────────────────────────────────────────────────────────────────────

class User(Base, TimestampMixin):
    """A login. Roles are enforced server-side on every protected route."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # 'admin' | 'officer' | 'citizen'
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="citizen")

    # Citizen logins are bound to exactly one citizen record. This is what stops
    # someone reading another resident's file by typing their ID.
    citizen_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("citizens.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Tokens issued before this moment are refused. Access and refresh tokens
    # are stateless JWTs, so there is otherwise no way to end a session early:
    # changing a password would leave whoever already had the account signed in
    # until their refresh token expired, which is a week. Set on password change
    # and on password reset, and compared against the token's `iat` claim in
    # `core.deps`. Null means nothing has ever been revoked.
    #
    # Stored truncated to the second, because `iat` is whole seconds. Keeping
    # the microseconds would reject the very token issued by the sign-in that
    # follows a reset, whenever both landed inside the same second.
    tokens_valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # An officer works for one Gram Panchayat and sees only its records. An
    # admin has no village and sees every village in the district.
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="SET NULL"), index=True
    )

    citizen: Mapped[Citizen | None] = relationship(back_populates="user")


class RegistrationRequest(Base):
    """A resident asking for a portal account.

    Self-registration is deliberately limited to residents, and even then it
    does not create a working account on its own. An officer must match the
    applicant to an existing citizen record and approve them.

    The reason is the whole security model: a citizen account is bound to one
    resident's file, so letting someone self-assert which resident they are
    would hand them another person's income, documents and family details.
    Officer and admin accounts cannot be self-registered at all — an officer
    can read every resident in the village, so that account is created by an
    admin or it is not created.
    """

    __tablename__ = "registration_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Held until approval, so no usable login exists before an officer decides.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    phone: Mapped[str | None] = mapped_column(String(30))
    claimed_ward: Mapped[int | None] = mapped_column(Integer)
    # What the applicant says identifies them — an officer checks it.
    claimed_citizen_id: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)

    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )

    # 'pending' | 'approved' | 'rejected'
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    matched_citizen_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("citizens.id", ondelete="SET NULL")
    )
    reviewed_by_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    review_note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Village records
# ─────────────────────────────────────────────────────────────────────────────

class Family(Base, TimestampMixin):
    """A household. Replaces the denormalised familyId/familyName/familyMembers
    triple that the old frontend model carried on every citizen."""

    __tablename__ = "families"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    ward: Mapped[int] = mapped_column(Integer, nullable=False)
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )
    address: Mapped[str | None] = mapped_column(String(500))
    address_mr: Mapped[str | None] = mapped_column(String(500))

    members: Mapped[list[Citizen]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )


class Citizen(Base, TimestampMixin):
    __tablename__ = "citizens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name_mr: Mapped[str] = mapped_column(String(255), nullable=False)

    # Stored as a date so age is derived, not frozen at seed time.
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    age: Mapped[int] = mapped_column(Integer, nullable=False)

    gender: Mapped[str] = mapped_column(String(20), nullable=False)
    gender_mr: Mapped[str] = mapped_column(String(20), nullable=False)

    occupation: Mapped[str] = mapped_column(String(120), nullable=False)
    occupation_mr: Mapped[str] = mapped_column(String(120), nullable=False)

    # Annual household income in rupees.
    income: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    ward: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )
    phone: Mapped[str | None] = mapped_column(String(30))

    family_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("families.id", ondelete="SET NULL"), index=True
    )
    relation: Mapped[str | None] = mapped_column(String(80))
    relation_mr: Mapped[str | None] = mapped_column(String(80))
    is_head: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Attributes real scheme rules depend on ───────────────────────────────
    # Government eligibility is rarely a simple income test. Ramai Awas is SC
    # only, MJPJAY keys off ration card colour, Saur Krushi Pump off land size,
    # Ladki Bahin off marital status. Without these the engine can only
    # approximate, which for a welfare decision is worse than saying "unknown".
    #
    # These are sensitive personal attributes. Every value in this project is
    # SYNTHETIC — a real deployment needs a lawful basis, consent, and access
    # controls tighter than role-based ones before collecting any of it.

    # 'Open' | 'SC' | 'ST' | 'OBC' | 'SEBC' | 'VJNT' | 'SBC'
    social_category: Mapped[str | None] = mapped_column(String(20), index=True)
    is_bpl: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # SECC-2011 deprivation listing — what PMAY-G and Ayushman Bharat actually use.
    secc_listed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 'Yellow' | 'Orange' | 'White' | 'AAY' | 'Annapurna'
    ration_card_type: Mapped[str | None] = mapped_column(String(20))
    land_holding_hectares: Mapped[float | None] = mapped_column(Float)
    # 'Single' | 'Married' | 'Widowed' | 'Divorced' | 'Abandoned'
    marital_status: Mapped[str | None] = mapped_column(String(20))
    disability_percent: Mapped[int | None] = mapped_column(Integer)

    family: Mapped[Family | None] = relationship(back_populates="members")
    user: Mapped[User | None] = relationship(back_populates="citizen", uselist=False)
    documents: Mapped[list[CitizenDocument]] = relationship(
        back_populates="citizen", cascade="all, delete-orphan"
    )
    grievances: Mapped[list[Grievance]] = relationship(back_populates="citizen")


# ─────────────────────────────────────────────────────────────────────────────
# Schemes
# ─────────────────────────────────────────────────────────────────────────────

class Scheme(Base, TimestampMixin):
    """A welfare scheme.

    Eligibility rules live in `criteria` as data, not in a chain of `if`
    statements keyed on scheme id. Adding a scheme is now an insert, and the
    rule engine in app/services/eligibility.py evaluates whatever it finds.

    criteria example:
        {"min_age": 60, "max_income": 100000, "gender": "Female",
         "occupation_any": ["farmer", "शेतकरी"]}
    """

    __tablename__ = "schemes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_mr: Mapped[str] = mapped_column(Text, nullable=False)

    # Text, not String(255): real government benefit descriptions run long —
    # Birsa Munda lists five separate subsidy caps in one sentence.
    benefit: Mapped[str] = mapped_column(Text, nullable=False)
    benefit_mr: Mapped[str] = mapped_column(Text, nullable=False)

    criteria: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    required_documents: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # 'active' for adopted schemes; 'pending'/'rejected' for the government feed
    # awaiting an officer's decision.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_government_feed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_gov: Mapped[str | None] = mapped_column(String(255))
    form_url: Mapped[str | None] = mapped_column(String(500))

    # 'central' | 'state' | 'district' | 'panchayat'
    level: Mapped[str] = mapped_column(String(20), default="state", nullable=False, index=True)
    # Pension, Housing, Agriculture, Health, Education, Women and Child, …
    category: Mapped[str | None] = mapped_column(String(60), index=True)

    # When the government announced it — drives the "newest first" ordering that
    # both the officer list and the citizen browser sort by.
    announced_on: Mapped[date | None] = mapped_column(Date, index=True)

    # Provenance. Every scheme points back at the official page its rules came
    # from, so any figure in the system can be checked against its source.
    source_url: Mapped[str | None] = mapped_column(String(500))
    # 'high' | 'medium' | 'low' — how well the figures were verified.
    confidence: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


# ─────────────────────────────────────────────────────────────────────────────
# Grievances
# ─────────────────────────────────────────────────────────────────────────────

class Grievance(Base, TimestampMixin):
    __tablename__ = "grievances"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    title_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_mr: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    category_mr: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    priority_mr: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="Pending", index=True)
    status_mr: Mapped[str] = mapped_column(String(30), nullable=False, default="प्रलंबित")

    department: Mapped[str] = mapped_column(String(120), nullable=False)
    department_mr: Mapped[str] = mapped_column(String(120), nullable=False)

    ward: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # Who raised it. citizen_id is null for walk-in complaints logged by an officer.
    citizen_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("citizens.id", ondelete="SET NULL"), index=True
    )
    citizen_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))

    submitted_date: Mapped[date] = mapped_column(Date, nullable=False)
    resolved_date: Mapped[date | None] = mapped_column(Date)
    officer_notes: Mapped[str | None] = mapped_column(Text)

    # Set when the classifier assigned category/priority, so you can report on
    # how often an officer overrode it.
    auto_classified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    citizen: Mapped[Citizen | None] = relationship(back_populates="grievances")
    events: Mapped[list[GrievanceEvent]] = relationship(
        back_populates="grievance", cascade="all, delete-orphan",
        order_by="GrievanceEvent.created_at",
    )


class GrievanceEvent(Base):
    """One entry in a complaint's history.

    A citizen tracking a complaint needs to see what has happened to it, not
    just where it sits now. Every status change is recorded here with who made
    it and when, so the citizen portal can show a real timeline and an officer
    can be held to one.
    """

    __tablename__ = "grievance_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    grievance_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("grievances.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # 'filed' | 'status_changed' | 'priority_changed' | 'note_added'
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str | None] = mapped_column(String(30))

    note: Mapped[str | None] = mapped_column(Text)
    note_mr: Mapped[str | None] = mapped_column(Text)

    actor_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    actor_name: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )

    grievance: Mapped[Grievance] = relationship(back_populates="events")


# ─────────────────────────────────────────────────────────────────────────────
# Development projects
# ─────────────────────────────────────────────────────────────────────────────

class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    description_mr: Mapped[str] = mapped_column(Text, nullable=False)

    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    utilized: Mapped[float] = mapped_column(Numeric(15, 2), default=0, nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status_mr: Mapped[str] = mapped_column(String(30), nullable=False)

    ward: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    location_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    start_date: Mapped[date | None] = mapped_column(Date)
    expected_completion: Mapped[date | None] = mapped_column(Date)


# ─────────────────────────────────────────────────────────────────────────────
# Digital locker
# ─────────────────────────────────────────────────────────────────────────────

class CitizenDocument(Base, TimestampMixin):
    __tablename__ = "citizen_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    citizen_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False, index=True
    )

    doc_type: Mapped[str] = mapped_column(String(120), nullable=False)
    doc_type_mr: Mapped[str] = mapped_column(String(120), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int | None] = mapped_column(Integer)

    # 'Pending Verification' | 'Verified' | 'Rejected'
    status: Mapped[str] = mapped_column(
        String(40), default="Pending Verification", nullable=False, index=True
    )
    status_mr: Mapped[str] = mapped_column(String(40), default="पडताळणी प्रलंबित", nullable=False)

    submitted_date: Mapped[date] = mapped_column(Date, nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    citizen: Mapped[Citizen] = relationship(back_populates="documents")


# ─────────────────────────────────────────────────────────────────────────────
# Gram Sabha
# ─────────────────────────────────────────────────────────────────────────────

class SabhaMeeting(Base, TimestampMixin):
    __tablename__ = "sabha_meetings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    title_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary_mr: Mapped[str] = mapped_column(Text, nullable=False, default="")

    decisions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    decisions_mr: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Provenance for the transcript this was extracted from.
    source_file_name: Mapped[str | None] = mapped_column(String(255))
    transcript_text: Mapped[str | None] = mapped_column(Text)
    extracted_by: Mapped[str | None] = mapped_column(String(40))  # 'llm' | 'manual'

    action_items: Mapped[list[SabhaActionItem]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan",
        order_by="SabhaActionItem.id",
    )


class SabhaActionItem(Base, TimestampMixin):
    """Normalised out of the old `action_items` JSONB blob so items can be
    filtered, assigned and reported on individually."""

    __tablename__ = "sabha_action_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("sabha_meetings.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    action: Mapped[str] = mapped_column(Text, nullable=False)
    action_mr: Mapped[str] = mapped_column(Text, nullable=False)
    responsible: Mapped[str] = mapped_column(String(255), nullable=False)
    responsible_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    deadline: Mapped[date | None] = mapped_column(Date)

    # 'Pending' | 'In Progress' | 'Completed'
    status: Mapped[str] = mapped_column(String(30), default="Pending", nullable=False)
    status_mr: Mapped[str] = mapped_column(String(30), default="प्रलंबित", nullable=False)

    meeting: Mapped[SabhaMeeting] = relationship(back_populates="action_items")


# ─────────────────────────────────────────────────────────────────────────────
# GIS
# ─────────────────────────────────────────────────────────────────────────────

class Facility(Base, TimestampMixin):
    """Village assets shown on the map: schools, health centres, water points."""

    __tablename__ = "facilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_mr: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    ward: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[str | None] = mapped_column(Text)
    details_mr: Mapped[str | None] = mapped_column(Text)


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval index (Phase 3 — pgvector)
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeChunk(Base, TimestampMixin):
    """One embeddable fact about the village.

    Each row is a natural-language rendering of a database record plus the
    foreign keys needed to walk to its neighbours, so retrieval can start from
    a similarity match and expand across relationships before generating.

    The embedding is stored as a plain JSON array rather than a pgvector column,
    and similarity is computed in Python. That is a deliberate choice, not a
    shortcut: one Gram Panchayat produces on the order of a hundred chunks, and
    scanning a hundred 768-dimension vectors takes under a millisecond. A
    pgvector index would add an extension dependency to every deployment and a
    dialect-specific query path to maintain, in exchange for speeding up
    something that is already imperceptible.

    That reasoning stops holding somewhere around a hundred thousand chunks — a
    whole district rather than a village. At that point the fix is a pgvector
    column and an IVFFlat index behind `semantic_search()`, which is why nothing
    outside that one function knows how the vectors are stored.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_chunk_entity"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_mr: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # The embedding vector, as a JSON array of floats. Null until indexed —
    # a chunk with no embedding is skipped by search rather than treated as
    # distance zero, which would make un-indexed rows look maximally relevant.
    #
    # none_as_null is essential and not decoration: by default SQLAlchemy stores
    # a Python None in a JSON column as the JSON value `null`, which is NOT SQL
    # NULL. `embedding IS NOT NULL` would then be true for every un-indexed row,
    # and search would score them against an empty vector. A test caught this.
    embedding: Mapped[list[float] | None] = mapped_column(JSON(none_as_null=True))
    embedding_model: Mapped[str | None] = mapped_column(String(80))

    # Which village this fact belongs to, so semantic search can be scoped the
    # same way every other query in this system is.
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="CASCADE"), index=True
    )

    # Set to the source row's updated_at when embedded, so re-indexing can skip
    # anything unchanged.
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ─────────────────────────────────────────────────────────────────────────────
# Audit trail
# ─────────────────────────────────────────────────────────────────────────────

class AuditEvent(Base):
    """One accountable action: who did what, to whose record, and when.

    The system already recorded a complaint's history and, since sign-in
    throttling, every authentication attempt. Neither answers the question a
    resident is most entitled to ask — *who has been reading my file* — and
    neither says who rejected a document or approved an account.

    **What is recorded, and what deliberately is not.** Every change of state by
    an authenticated user, and every read that names one individual. Not list
    endpoints: an officer opening the resident directory is their job and
    happens on every page load, so recording it buries the events that matter
    under traffic. That is a real limit rather than an oversight — this trail
    answers "who opened Savita's file", not "who could have".

    **No request bodies.** Only the method, the path, the outcome and the record
    named. A body would put a resident's income, a document's contents or a new
    password into a table whose whole purpose is to be kept and read later.

    The trail is itself sensitive: it says who looked at whom. Reading it is
    admin-only, and `services.audit.prune()` drops rows past a year.
    """

    __tablename__ = "audit_events"
    __table_args__ = (
        # How the trail is actually read: everything touching one record, and
        # everything one person did, both newest first.
        Index("ix_audit_entity_time", "entity_type", "entity_id", "created_at"),
        Index("ix_audit_actor_time", "actor_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # Null only if the account was deleted afterwards; the denormalised email
    # and role survive that, because an audit row that cannot say who acted is
    # not an audit row.
    actor_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255))
    actor_role: Mapped[str | None] = mapped_column(String(20))

    # 'read' for a request that named one record, otherwise the HTTP verb
    # lowercased — 'post', 'patch', 'delete'.
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)

    # The record acted on, derived from the path: ('citizen', 'cit_102').
    # Null when the request named no single record.
    entity_type: Mapped[str | None] = mapped_column(String(40), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), index=True)

    # Which Gram Panchayat the actor was working in, so a district admin can
    # filter the trail the same way every other list here is scoped.
    village_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("villages.id", ondelete="SET NULL"), index=True
    )

    ip: Mapped[str | None] = mapped_column(String(64))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Password resets
# ─────────────────────────────────────────────────────────────────────────────

class PasswordReset(Base):
    """A one-time code that lets someone set a new password.

    There is no email or SMS gateway in this deployment, so the usual "we have
    sent you a link" flow cannot exist — and inventing one would mean a reset
    that silently never arrives. This uses the channel a Gram Panchayat actually
    has: the office counter.

    A resident who cannot sign in goes to the Panchayat office. An officer
    identifies them against the village register — the same check that already
    gates account approval — and issues a code, which the system shows once and
    the officer hands over. The resident redeems it for a password of their own
    choosing. The officer never learns that password.

    The code is stored only as a bcrypt hash, exactly like a password, so a
    reader of this table cannot use what they find. It expires, it is single
    use, and issuing a new one invalidates any earlier unused code for that
    account — otherwise every reset ever issued would stay live.

    Who may reset whom is the part that matters. An officer may reset residents
    of their own village and nobody else: letting an officer reset another
    officer, or an admin, would turn a village login into a route to the whole
    block. That check lives in the route.
    """

    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # bcrypt, never the code itself.
    hashed_code: Mapped[str] = mapped_column(String(255), nullable=False)

    issued_by_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Set when redeemed. A code with this set is spent and cannot be reused.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sign-in attempts
# ─────────────────────────────────────────────────────────────────────────────

class AuthAttempt(Base):
    """One sign-in attempt, successful or not.

    Two jobs, which is why it is a table rather than a counter in memory.

    It throttles. `services.ratelimit` counts recent failures against this table
    to decide whether to accept another attempt, so `/auth/login` stops being an
    unlimited password oracle. Keeping the count in the database rather than in
    the process matters on this deployment specifically: the API sleeps after
    fifteen minutes of inactivity, and an in-memory counter would be cleared by
    every cold start — which is to say, by waiting.

    It is also the audit trail for authentication. A failed sign-in is the event
    a Panchayat most needs a record of, and the row survives long enough to
    answer "who has been trying to get into this officer's account".

    The email is stored exactly as it was typed (lowercased), whether or not any
    such account exists. That is deliberate: throttling only known accounts
    would turn the throttle itself into a way to discover which emails are
    registered — a slow response for real accounts and a fast one for the rest.

    No password or token is stored here, successful attempt or not.
    """

    __tablename__ = "auth_attempts"
    __table_args__ = (
        # The shape of the throttle's own two queries: recent failures for one
        # email, and recent failures from one source. Declared here as well as
        # in the migration so the two cannot drift — `alembic check` compares
        # them, and caught exactly that when these were only in the migration.
        Index("ix_auth_attempts_email_outcome_time", "email", "outcome", "created_at"),
        Index("ix_auth_attempts_ip_outcome_time", "ip", "outcome", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)

    # As typed, lowercased. Not a foreign key — most failures name no real account.
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Best-effort, and spoofable behind a proxy that does not strip the header.
    # The per-email limit is the guarantee; this one narrows the blast radius.
    ip: Mapped[str | None] = mapped_column(String(64), index=True)

    successful: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 'ok' | 'bad_password' | 'no_account' | 'inactive'
    # | 'registration_pending' | 'registration_rejected' | 'rate_limited'
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)

    # Set only when the attempt matched a real account, so a successful sign-in
    # can be tied to a user without inventing one for a failure that did not.
    user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )
