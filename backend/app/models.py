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

    citizen: Mapped[Citizen | None] = relationship(back_populates="user")


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
    phone: Mapped[str | None] = mapped_column(String(30))

    family_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("families.id", ondelete="SET NULL"), index=True
    )
    relation: Mapped[str | None] = mapped_column(String(80))
    relation_mr: Mapped[str | None] = mapped_column(String(80))
    is_head: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

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

    benefit: Mapped[str] = mapped_column(String(255), nullable=False)
    benefit_mr: Mapped[str] = mapped_column(String(255), nullable=False)

    criteria: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    required_documents: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # 'active' for adopted schemes; 'pending'/'rejected' for the government feed
    # awaiting an officer's decision.
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    is_government_feed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_gov: Mapped[str | None] = mapped_column(String(255))
    form_url: Mapped[str | None] = mapped_column(String(500))


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

    The `embedding` column is added by its own migration once pgvector is
    enabled, so Phase 1 can run on a plain Postgres without the extension.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_chunk_entity"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_mr: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Set to the source row's updated_at when embedded, so re-indexing can skip
    # anything unchanged.
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
