"""The life of a development work: its stages, its money, and what watches both.

A resident asks for twenty streetlights. Nobody can close that from a desk. The
need has to be checked on the ground, the Panchayat has to decide, somebody has
to say what it will cost, the money has to be asked for, sanctioned and actually
arrive, the work has to be done, and the person who asked should get to say
whether it was. This module is that sequence, and the rules that keep it honest.

**The stages, in order**

    proposed → verified → approved → budget_requested → budget_approved
             → funds_received → in_progress → completed

with `rejected` and `on_hold` to the side. A stage cannot be skipped: there is
no way to start a work whose funds have not been recorded as received, or to
record spending on one that has not started.

**What moves a work**

Two kinds of thing. A *decision* — verify, approve, reject, start, complete,
hold, resume — is an officer saying so, and the ones that close a door need a
reason. A *money entry* moves the stage by itself wherever recording the fact
*is* the step: entering the amount requested is what makes a work "budget
requested", so there is no second button to press and no way for the two to
disagree.

**What this is not**

It is not an accounting system. There are no vouchers, vendor ledgers or cash
books, and nothing here talks to PFMS: "funds received" is an officer recording
that money arrived. And nothing here is decided by a model. Every figure is
typed in by a person — a cost estimate most of all — and every check below is
arithmetic that can be read off this page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.security import as_utc
from app.models import (
    BudgetEntry,
    Facility,
    Grievance,
    Project,
    SabhaMeeting,
    User,
)
from app.services import timeline


class WorksError(Exception):
    """A step that the rules do not allow. Routes turn this into a 4xx."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ─────────────────────────────────────────────────────────────────────────────
# Vocabulary
# ─────────────────────────────────────────────────────────────────────────────

STAGES: list[str] = [
    "proposed", "verified", "approved", "budget_requested",
    "budget_approved", "funds_received", "in_progress", "completed",
]

STAGE_LABELS: dict[str, tuple[str, str]] = {
    "proposed": ("Proposed", "प्रस्तावित"),
    "verified": ("Need verified", "गरज पडताळली"),
    "approved": ("Approved by Panchayat", "पंचायतीची मंजुरी"),
    "budget_requested": ("Budget requested", "निधीची मागणी केली"),
    "budget_approved": ("Budget approved", "निधी मंजूर"),
    "funds_received": ("Funds received", "निधी प्राप्त"),
    "in_progress": ("Work in progress", "काम सुरू"),
    "completed": ("Completed", "पूर्ण"),
    "rejected": ("Not approved", "नामंजूर"),
    "on_hold": ("On hold", "स्थगित"),
}

# The coarse label the dashboards and the map already read.
STATUS_FOR_STAGE: dict[str, str] = {
    "proposed": "Planned", "verified": "Planned", "approved": "Planned",
    "budget_requested": "Planned", "budget_approved": "Planned",
    "funds_received": "Planned", "in_progress": "Ongoing",
    "completed": "Completed", "rejected": "Rejected", "on_hold": "On Hold",
}
STATUS_MR: dict[str, str] = {
    "Planned": "नियोजित", "Ongoing": "सुरू असलेले", "Delayed": "विलंब झालेला",
    "Completed": "पूर्ण झालेले", "On Hold": "स्थगित", "Rejected": "नामंजूर",
}

ENTRY_KINDS = ("estimate", "requested", "approved", "received", "spent")
KIND_LABELS: dict[str, tuple[str, str]] = {
    "estimate": ("Estimated cost", "अंदाजित खर्च"),
    "requested": ("Budget requested", "निधीची मागणी"),
    "approved": ("Budget approved", "निधी मंजूर"),
    "received": ("Funds received", "निधी प्राप्त"),
    "spent": ("Amount spent", "खर्च"),
}

# Where a work's money can come from. Labels only: nothing in this system says
# which fund a particular work must be paid from, because that is decided by
# scheme guidelines and sanction orders this system has not read. An officer
# records the source they were told.
FUNDING_SOURCES: dict[str, tuple[str, str]] = {
    "cfc": ("Central Finance Commission grant", "केंद्रीय वित्त आयोग अनुदान"),
    "state": ("State Government grant", "राज्य शासन अनुदान"),
    "zp": ("Zilla Parishad / Panchayat Samiti grant", "जिल्हा परिषद / पंचायत समिती अनुदान"),
    "own": ("Gram Panchayat own funds", "ग्रामपंचायत स्वनिधी"),
    "scheme": ("Scheme-specific fund", "योजना-विशिष्ट निधी"),
    "mla_mp": ("MLA / MP local area fund", "आमदार / खासदार स्थानिक विकास निधी"),
    "other": ("Other", "इतर"),
}

# What a finished work can add to the asset register, and the layer the map
# draws it on.
ASSET_TYPES: dict[str, tuple[str, str]] = {
    "streetlight": ("Streetlights", "पथदिवे"),
    "water": ("Water facility", "पाणी सुविधा"),
    "school": ("School facility", "शाळा सुविधा"),
    "health": ("Health facility", "आरोग्य सुविधा"),
    "road": ("Road", "रस्ता"),
    "drain": ("Drain", "गटार"),
    "toilet": ("Public toilet", "सार्वजनिक शौचालय"),
    "building": ("Public building", "सार्वजनिक इमारत"),
}


def rupees(value) -> str:
    """₹3,50,000 — grouped the way the amount would be written in the office."""
    n = int(round(float(value or 0)))
    digits = str(abs(n))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        digits = ",".join([*groups, tail])
    return f"{'-' if n < 0 else ''}₹{digits}"


def stage_label(stage: str) -> tuple[str, str]:
    return STAGE_LABELS.get(stage, (stage, stage))


def financial_year(day: date) -> str:
    """'2026-27' for any date from 1 April 2026 to 31 March 2027."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def fy_bounds(fy: str) -> tuple[date, date]:
    try:
        start = int(fy.split("-")[0])
    except (ValueError, IndexError) as exc:
        raise WorksError("A financial year looks like 2026-27.") from exc
    return date(start, 4, 1), date(start + 1, 3, 31)


# ─────────────────────────────────────────────────────────────────────────────
# Money
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Money:
    """Where a work's money stands, read off its ledger.

    An estimate, a request and an approval are each a single current figure that
    can be revised, so the latest entry stands and the earlier ones remain as
    history. Receipts and payments happen in instalments, so those add up.
    """

    estimated: float | None = None
    first_estimate: float | None = None
    requested: float | None = None
    approved: float | None = None
    received: float = 0.0
    spent: float = 0.0

    @property
    def awaiting(self) -> float:
        """Sanctioned but not yet arrived."""
        return max((self.approved or 0.0) - self.received, 0.0)

    @property
    def balance(self) -> float:
        """Arrived and not yet paid out."""
        return self.received - self.spent

    @property
    def remaining(self) -> float:
        """Approved and not yet paid out: what is in hand plus what is still to
        arrive. This is the figure people mean by "the remaining budget"."""
        return (self.approved or 0.0) - self.spent

    @property
    def financial_percent(self) -> int:
        if not self.approved:
            return 0
        return round(self.spent / self.approved * 100)


def in_order(entries: list[BudgetEntry]) -> list[BudgetEntry]:
    """A ledger in the order it is read: by the date each thing happened, and
    for two things on one day, by which was recorded first.

    This is what "the latest entry stands" means. The date decides, not the
    moment of typing, so an officer who goes back and fills in an earlier
    approval for the record does not thereby overwrite the current one. Two
    entries on the same date are a correction, and the later one wins.
    """
    return sorted(
        entries,
        key=lambda e: (e.entry_date, as_utc(e.created_at) or clock.now()),
    )


def money(entries: list[BudgetEntry], within: tuple[date, date] | None = None) -> Money:
    """Total a ledger, optionally only the entries dated inside one financial year."""
    m = Money()
    for entry in in_order(entries):
        if within and not (within[0] <= entry.entry_date <= within[1]):
            continue
        amount = float(entry.amount)
        if entry.kind == "received":
            m.received += amount
        elif entry.kind == "spent":
            m.spent += amount
        elif entry.kind == "estimate":
            if m.first_estimate is None:
                m.first_estimate = amount
            m.estimated = amount
        elif entry.kind == "requested":
            m.requested = amount
        elif entry.kind == "approved":
            m.approved = amount
    return m


def _sync_totals(project: Project) -> None:
    """Keep the two legacy columns equal to the ledger.

    `budget` and `utilized` are what the dashboard, the charts and the map were
    already reading. Rewriting them here means none of those needed to learn the
    ledger exists, and there is no second figure to drift from the first.
    """
    m = money(project.entries)
    project.budget = m.approved or 0
    project.utilized = m.spent


def physical_percent(project: Project) -> int:
    if project.units_planned:
        return round((project.units_done or 0) / project.units_planned * 100)
    return int(project.progress or 0)


def _new_entry(
    project: Project,
    kind: str,
    amount: float,
    *,
    entry_date: date,
    actor: User | None,
    funding_source: str | None = None,
    reference: str | None = None,
    note: str | None = None,
    actor_name: str | None = None,
    created_at: datetime | None = None,
) -> BudgetEntry:
    entry = BudgetEntry(
        id=f"bud_{uuid4().hex[:12]}",
        project_id=project.id,
        kind=kind,
        amount=amount,
        entry_date=entry_date,
        funding_source=funding_source,
        reference=(reference or "").strip() or None,
        note=(note or "").strip() or None,
        created_by_id=actor.id if actor else None,
        created_by_name=actor.full_name if actor else actor_name,
        created_at=created_at or clock.now(),
    )
    project.entries.append(entry)
    return entry


# Recording one of these facts *is* the step, so the stage follows the entry.
_ADVANCES: dict[tuple[str, str], str] = {
    ("requested", "approved"): "budget_requested",
    ("approved", "budget_requested"): "budget_approved",
    ("received", "budget_approved"): "funds_received",
}

# The stages at which each kind of entry makes sense.
_ENTRY_STAGES: dict[str, set[str]] = {
    "estimate": {"proposed", "verified", "approved", "budget_requested",
                 "budget_approved", "funds_received", "in_progress"},
    "requested": {"approved", "budget_requested"},
    "approved": {"budget_requested", "budget_approved", "funds_received", "in_progress"},
    "received": {"budget_approved", "funds_received", "in_progress"},
    "spent": {"in_progress", "completed"},
}

_ENTRY_TOO_EARLY: dict[str, str] = {
    "requested": "A budget can be requested once the Panchayat has approved the proposal.",
    "approved": "An approval can be recorded once a budget has been requested.",
    "received": "Funds can be recorded as received once a budget has been approved.",
    "spent": "Spending is recorded once the work has started.",
    "estimate": "The estimate cannot be changed at this stage.",
}


def add_entry(
    db: Session,
    project: Project,
    actor: User | None,
    *,
    kind: str,
    amount: float,
    entry_date: date | None = None,
    funding_source: str | None = None,
    reference: str | None = None,
    note: str | None = None,
) -> BudgetEntry:
    """Record one step in a work's money, and move its stage if that step is one."""
    if kind not in ENTRY_KINDS:
        raise WorksError(f"Unknown kind of entry: {kind}.")
    if amount is None or float(amount) <= 0:
        raise WorksError("An amount has to be more than zero.")
    amount = round(float(amount), 2)

    stage = project.stage
    if stage in ("rejected", "on_hold"):
        raise WorksError(
            f"This work is {stage_label(stage)[0].lower()}. Resume it before recording money.",
            409,
        )
    if stage not in _ENTRY_STAGES[kind]:
        raise WorksError(_ENTRY_TOO_EARLY[kind], 409)

    today = clock.today()
    entry_date = entry_date or today
    if entry_date > today:
        raise WorksError("An entry cannot be dated in the future.")
    if funding_source and funding_source not in FUNDING_SOURCES:
        raise WorksError("That is not a recognised funding source.")

    m = money(project.entries)
    extra = ""
    if kind == "approved":
        if amount + 0.005 < m.received:
            raise WorksError(
                f"{rupees(m.received)} has already been received, so the approved "
                f"amount cannot be revised below that."
            )
        if m.requested and amount + 0.005 < m.requested:
            extra = f" ({rupees(m.requested - amount)} less than was requested)"
    elif kind == "received":
        approved = m.approved or 0.0
        if m.received + amount > approved + 0.005:
            raise WorksError(
                f"That would bring funds received to {rupees(m.received + amount)}, "
                f"more than the {rupees(approved)} approved. Record a revised "
                f"approval first if more was sanctioned."
            )
    elif kind == "spent":
        if m.spent + amount > m.received + 0.005:
            raise WorksError(
                f"That would bring spending to {rupees(m.spent + amount)}, more than "
                f"the {rupees(m.received)} received so far."
            )

    source = funding_source or project.funding_source
    entry = _new_entry(
        project, kind, amount, entry_date=entry_date, actor=actor,
        funding_source=source, reference=reference, note=note,
    )
    if funding_source and kind in ("requested", "approved", "received"):
        project.funding_source = funding_source
    _sync_totals(project)

    label, label_mr = KIND_LABELS[kind]
    text = f"{label}: {rupees(amount)}{extra}"
    text_mr = f"{label_mr}: {rupees(amount)}"
    if entry.note:
        text += f" — {entry.note}"

    advance = _ADVANCES.get((kind, stage))
    if advance:
        _set_stage(db, project, advance, actor, note=text, note_mr=text_mr)
    else:
        timeline.project_event(db, project, "budget_entry", actor, note=text, note_mr=text_mr)
    return entry


# The two kinds that add up, and so the two that can be wrong in a way a new
# entry cannot fix.
CORRECTABLE_KINDS = ("received", "spent")


def recorded_amount(entry: BudgetEntry, entries: list[BudgetEntry]) -> float:
    """What an entry stands at once the corrections made to it are applied."""
    return round(
        float(entry.amount)
        + sum(float(e.amount) for e in entries if e.corrects_id == entry.id),
        2,
    )


def can_correct(project: Project, entry: BudgetEntry) -> bool:
    return (
        entry.kind in CORRECTABLE_KINDS
        and entry.corrects_id is None
        and project.stage not in ("rejected", "on_hold")
    )


def correct_entry(
    db: Session,
    project: Project,
    actor: User | None,
    entry: BudgetEntry,
    *,
    amount: float,
    reason: str,
) -> BudgetEntry:
    """Put right a receipt or a payment that was recorded wrongly.

    An estimate, a request or an approval needs none of this: each is a single
    current figure, so recording the right one replaces the wrong one. A receipt
    or a payment is different, because those add up. Type 1,60,000 where 16,000
    was meant and no later entry can take it back — the total is simply wrong,
    and "remaining" with it, for as long as the work exists.

    So the officer says what the entry should have been and why, and a further
    row is written carrying the difference. Nothing is overwritten: the ledger
    shows the original, the correction, who made it and the reason given.

    The same rules hold after a correction as before one. Money received cannot
    exceed what was approved or fall below what has been spent, and money spent
    cannot exceed what was received. Setting the amount to zero cancels an entry
    that should never have been made — a payment recorded against the wrong
    work, say.
    """
    if entry.project_id != project.id:
        raise WorksError("That entry does not belong to this work.", 404)
    if entry.corrects_id is not None:
        raise WorksError(
            "That line is itself a correction. Correct the entry it belongs to instead."
        )
    if entry.kind not in CORRECTABLE_KINDS:
        label = KIND_LABELS[entry.kind][0].lower()
        raise WorksError(
            f"There is nothing to correct on the {label}: record the right figure "
            f"as a new entry and it stands in place of this one."
        )
    if project.stage in ("rejected", "on_hold"):
        raise WorksError(
            f"This work is {stage_label(project.stage)[0].lower()}. Resume it before "
            f"recording money.",
            409,
        )

    reason = (reason or "").strip()
    if not reason:
        raise WorksError("Say what was wrong with the entry. The reason stays on the record.")
    if amount is None or float(amount) < 0:
        raise WorksError("The corrected amount cannot be less than zero.")
    amount = round(float(amount), 2)

    before = recorded_amount(entry, project.entries)
    if abs(amount - before) < 0.005:
        raise WorksError(f"This entry already stands at {rupees(before)}.")
    difference = round(amount - before, 2)

    m = money(project.entries)
    back_a_stage = False
    if entry.kind == "received":
        total = m.received + difference
        approved = m.approved or 0.0
        if total > approved + 0.005:
            raise WorksError(
                f"That would bring funds received to {rupees(total)}, more than the "
                f"{rupees(approved)} approved."
            )
        if total + 0.005 < m.spent:
            raise WorksError(
                f"{rupees(m.spent)} has already been spent, so the funds received "
                f"cannot be corrected to less than that."
            )
        if total <= 0.005:
            if project.stage != "funds_received":
                raise WorksError(
                    "This work has already started, so its funds cannot be corrected "
                    "to nothing. If the money did not in fact arrive, put the work on "
                    "hold and say so."
                )
            # Nothing has arrived after all, so the work is not at "funds
            # received". It goes back to waiting for them.
            back_a_stage = True
    else:
        total = m.spent + difference
        if total > m.received + 0.005:
            raise WorksError(
                f"That would bring spending to {rupees(total)}, more than the "
                f"{rupees(m.received)} received so far."
            )

    correction = _new_entry(
        project, entry.kind, difference,
        # Dated as the entry it corrects, so a year's totals show the right
        # figure rather than a wrong one in one year and its reversal in the
        # next. When the correction was actually made is its `created_at`.
        entry_date=entry.entry_date, actor=actor,
        funding_source=entry.funding_source, reference=entry.reference, note=reason,
    )
    correction.corrects_id = entry.id
    _sync_totals(project)

    label, label_mr = KIND_LABELS[entry.kind]
    text = (
        f"Correction: {label.lower()} of {entry.entry_date.strftime('%d %b %Y')} "
        f"changed from {rupees(before)} to {rupees(amount)} — {reason}"
    )
    text_mr = (
        f"दुरुस्ती: {entry.entry_date.strftime('%d-%m-%Y')} ची “{label_mr}” नोंद "
        f"{rupees(before)} वरून {rupees(amount)} केली — {reason}"
    )
    if back_a_stage:
        _set_stage(db, project, "budget_approved", actor, note=text, note_mr=text_mr)
    else:
        timeline.project_event(db, project, "budget_entry", actor, note=text, note_mr=text_mr)
    return correction


def open_ledger(
    db: Session, project: Project, *, on: date | None = None, actor: User | None = None
) -> None:
    """Give a work that was recorded as two totals the entries that add up to them.

    Works existed before the ledger did, as a sanctioned amount and an amount
    spent. Rather than keep two ways of holding the same figures, each of those
    gets opening entries saying exactly that, and from then on is no different
    from a work that came up through the stages.

    The sanctioned amount is entered as both approved and received. The old
    record could not tell the two apart, and treating the sanction as available
    is what keeps "remaining" on every screen equal to what it showed before.
    """
    if project.entries:
        return
    on = on or project.start_date or clock.today()
    budget = float(project.budget or 0)
    used = float(project.utilized or 0)
    note = "Opening balance carried over from the project record."
    for kind, amount in (("approved", budget), ("received", budget), ("spent", used)):
        if amount > 0:
            _new_entry(
                project, kind, amount, entry_date=on, actor=actor, note=note,
                funding_source=project.funding_source,
                actor_name="Carried over",
            )
    project.stage = "completed" if project.status == "Completed" else "in_progress"
    project.stage_changed_at = project.stage_changed_at or clock.now()
    _sync_totals(project)


# ─────────────────────────────────────────────────────────────────────────────
# Stages
# ─────────────────────────────────────────────────────────────────────────────

def _set_stage(
    db: Session,
    project: Project,
    to_stage: str,
    actor: User | None,
    *,
    note: str | None = None,
    note_mr: str | None = None,
    actor_name: str | None = None,
) -> None:
    previous = project.stage
    project.stage = to_stage
    project.stage_changed_at = clock.now()
    status = STATUS_FOR_STAGE[to_stage]
    project.status = status
    project.status_mr = STATUS_MR[status]
    timeline.project_event(
        db, project, "stage_changed", actor,
        from_stage=previous, to_stage=to_stage, note=note, note_mr=note_mr,
        actor_name=actor_name,
    )


_ACTIVE = {"proposed", "verified", "approved", "budget_requested",
           "budget_approved", "funds_received", "in_progress"}

# action → (stages it is allowed from, stage it leads to, reason required)
_ACTIONS: dict[str, tuple[set[str], str | None, bool]] = {
    "verify": ({"proposed"}, "verified", True),
    "approve": ({"verified"}, "approved", False),
    # Once money has arrived a work is held, not rejected: there are funds to
    # account for, and "rejected" would leave them attached to nothing.
    "reject": ({"proposed", "verified", "approved", "budget_requested",
                "budget_approved"}, "rejected", True),
    "start": ({"funds_received"}, "in_progress", False),
    "complete": ({"in_progress"}, "completed", False),
    "hold": (_ACTIVE, "on_hold", True),
    "resume": ({"on_hold"}, None, False),
}

_REASON_PROMPTS: dict[str, str] = {
    "verify": "Say what the field check found — it is the evidence the decision rests on.",
    "reject": "Give the reason. The residents who asked for this will be shown it.",
    "hold": "Say why the work is being held.",
}


def act(
    db: Session,
    project: Project,
    action: str,
    actor: User | None,
    *,
    note: str | None = None,
    sabha_meeting_id: str | None = None,
) -> None:
    """Take one decision on a work."""
    rule = _ACTIONS.get(action)
    if rule is None:
        raise WorksError(f"Unknown action: {action}.")
    allowed_from, to_stage, reason_required = rule

    if project.stage not in allowed_from:
        raise WorksError(
            f"That is not possible while the work is at “{stage_label(project.stage)[0]}”.",
            409,
        )
    note = (note or "").strip() or None
    if reason_required and not note:
        raise WorksError(_REASON_PROMPTS[action])

    if action == "approve":
        if sabha_meeting_id:
            meeting = db.get(SabhaMeeting, sabha_meeting_id)
            if meeting is None or meeting.village_id != project.village_id:
                raise WorksError("That Gram Sabha meeting was not found in this village.")
            project.sabha_meeting_id = meeting.id
        project.decision_note = note
    elif action == "reject":
        project.decision_note = note
        _tell_residents_it_was_not_approved(db, project, actor, note or "")
    elif action == "hold":
        project.held_from_stage = project.stage
    elif action == "resume":
        to_stage = project.held_from_stage or "proposed"
        project.held_from_stage = None
    elif action == "start":
        project.start_date = project.start_date or clock.today()
    elif action == "complete":
        _complete(db, project, actor)

    assert to_stage is not None
    _set_stage(db, project, to_stage, actor, note=note)


def _tell_residents_it_was_not_approved(
    db: Session, project: Project, actor: User | None, reason: str
) -> None:
    """Put the reason on each linked complaint's own timeline, which is the
    only place its resident will look.

    The complaints themselves stay open. The Panchayat has refused one way of
    answering a problem, which is not the same as the problem going away: the
    lane is still dark. What happens to each complaint next — a smaller repair,
    a later proposal, or closing it with an explanation — is the officer's
    decision, and it is made on the complaint, not here.
    """
    for grievance in project.grievances:
        timeline.grievance_event(
            db, grievance, "note_added", actor,
            note=(
                f"The proposal this request was part of — “{project.name}” — was not "
                f"approved by the Panchayat. Reason given: {reason}"
            ),
            note_mr=(
                f"ही मागणी ज्या प्रस्तावाचा भाग होती — “{project.name_mr}” — तो "
                f"पंचायतीने मंजूर केला नाही. कारण: {reason}"
            ),
        )


def _complete(db: Session, project: Project, actor: User | None) -> None:
    """Close a work: check the count, register what it built, and hand the
    question back to the residents who asked for it."""
    if project.units_planned:
        done = project.units_done or 0
        if done != project.units_planned:
            unit = project.unit_label or "units"
            raise WorksError(
                f"{done} of {project.units_planned} {unit} are recorded as done. "
                f"Record the rest, or revise the planned number, before completing."
            )
    project.progress = 100
    today = clock.today()

    if project.asset_type:
        _register_asset(db, project, today)

    for grievance in project.grievances:
        if grievance.status == "Resolved":
            continue
        previous = grievance.status
        grievance.status = "Resolved"
        grievance.status_mr = "निराकरण झाले"
        grievance.resolved_date = today
        # A fresh resolution deserves a fresh answer from the resident.
        grievance.citizen_feedback = None
        grievance.feedback_note = None
        grievance.feedback_at = None
        timeline.grievance_event(
            db, grievance, "status_changed", actor,
            from_status=previous, to_status="Resolved",
            note=(
                f"The work this request led to is complete: “{project.name}”. "
                f"Please confirm that it has been done."
            ),
            note_mr=(
                f"या मागणीतून झालेले काम पूर्ण झाले आहे: “{project.name_mr}”. "
                f"कृपया काम झाल्याची खात्री करा."
            ),
        )


def _register_asset(db: Session, project: Project, installed_on: date) -> None:
    """Add what the work built to the asset register, once.

    One row with a quantity, at the place the work was done. This system knows
    twenty streetlights were installed under this work and where the work was;
    it does not know where each pole stands, and a pin per pole at made-up
    coordinates would be drawing a survey nobody carried out.
    """
    already = db.scalar(select(Facility.id).where(Facility.project_id == project.id))
    if already:
        return

    label, label_mr = ASSET_TYPES.get(
        project.asset_type or "", (project.unit_label or "Assets", project.unit_label_mr or "मालमत्ता")
    )
    count = project.units_done or project.units_planned or 1
    if project.units_planned:
        unit, unit_mr = project.unit_label or "units", project.unit_label_mr or "घटक"
        details = f"{count} {unit} installed under “{project.name}”."
        details_mr = f"“{project.name_mr}” अंतर्गत {count} {unit_mr} बसवले."
    else:
        details = f"Built under “{project.name}”."
        details_mr = f"“{project.name_mr}” अंतर्गत उभारले."
    db.add(Facility(
        id=f"fac_{uuid4().hex[:10]}",
        name=f"{label} — {project.location}",
        name_mr=f"{label_mr} — {project.location_mr}",
        facility_type=project.asset_type,
        village_id=project.village_id,
        latitude=project.latitude,
        longitude=project.longitude,
        ward=project.ward,
        quantity=count,
        project_id=project.id,
        installed_on=installed_on,
        details=details,
        details_mr=details_mr,
    ))


def record_progress(
    db: Session,
    project: Project,
    actor: User | None,
    *,
    units_done: int | None = None,
    progress: int | None = None,
    note: str | None = None,
) -> None:
    """Record how much of the work physically exists."""
    if project.stage != "in_progress":
        raise WorksError("Progress is recorded while the work is in progress.", 409)

    if project.units_planned:
        if units_done is None:
            raise WorksError(
                f"This work is counted in {project.unit_label or 'units'}. "
                f"Give the number completed."
            )
        if not 0 <= units_done <= project.units_planned:
            raise WorksError(
                f"The number completed has to be between 0 and {project.units_planned}."
            )
        previous = project.units_done or 0
        project.units_done = units_done
        project.progress = physical_percent(project)
        unit = project.unit_label or "units"
        unit_mr = project.unit_label_mr or "घटक"
        text = f"Progress recorded: {units_done} of {project.units_planned} {unit} (was {previous})."
        text_mr = f"प्रगती नोंद: {project.units_planned} पैकी {units_done} {unit_mr} (आधी {previous})."
    else:
        if progress is None or not 0 <= progress <= 100:
            raise WorksError("Give the progress as a percentage from 0 to 100.")
        previous = project.progress
        project.progress = progress
        text = f"Progress recorded: {progress}% (was {previous}%)."
        text_mr = f"प्रगती नोंद: {progress}% (आधी {previous}%)."

    if note and note.strip():
        text += f" {note.strip()}"
    timeline.project_event(db, project, "progress", actor, note=text, note_mr=text_mr)


# ─────────────────────────────────────────────────────────────────────────────
# Proposals and the complaints behind them
# ─────────────────────────────────────────────────────────────────────────────

def propose(db: Session, actor: User | None, **fields) -> Project:
    """Record a proposed work. It has no money and no approval yet — only the
    statement that somebody thinks it should be done."""
    project = Project(
        id=fields.pop("id", None) or f"proj_{uuid4().hex[:10]}",
        progress=0, budget=0, utilized=0,
        status="Planned", status_mr=STATUS_MR["Planned"],
        stage="proposed", stage_changed_at=clock.now(), units_done=0,
        **fields,
    )
    db.add(project)
    db.flush()
    timeline.project_event(
        db, project, "proposed", actor, to_stage="proposed",
        note="Proposal recorded.", note_mr="प्रस्ताव नोंदवला.",
    )
    return project


def link_grievances(
    db: Session, project: Project, grievances: list[Grievance], actor: User | None
) -> int:
    """Attach complaints to the work that answers them.

    Nothing is merged. Each resident keeps their own complaint with its own
    history; what changes is that it now points at the shared work, so its
    owner can follow that work's stages from their own page.
    """
    linked = 0
    for grievance in grievances:
        if grievance.project_id == project.id:
            continue
        if grievance.village_id != project.village_id:
            raise WorksError("A complaint can only be linked to a work in its own village.", 403)
        if grievance.project_id:
            raise WorksError(
                f"Complaint {grievance.id} is already linked to another work.", 409
            )

        grievance.project_id = project.id
        timeline.grievance_event(
            db, grievance, "linked_to_project", actor,
            note=f"Included in development proposal “{project.name}”.",
            note_mr=f"“{project.name_mr}” या विकास प्रस्तावात समाविष्ट.",
        )
        if grievance.status == "Pending":
            grievance.status = "In Progress"
            grievance.status_mr = "प्रगतीपथावर"
            timeline.grievance_event(
                db, grievance, "status_changed", actor,
                from_status="Pending", to_status="In Progress",
                note="Taken up as a development work. Follow its progress below.",
                note_mr="विकास काम म्हणून हाती घेतले. त्याची प्रगती खाली पाहा.",
            )
        linked += 1

    if linked:
        timeline.project_event(
            db, project, "grievance_linked", actor,
            note=f"{linked} complaint(s) linked to this work.",
            note_mr=f"{linked} तक्रारी या कामाशी जोडल्या.",
        )
    return linked


def unlink_grievance(
    db: Session, project: Project, grievance: Grievance, actor: User | None
) -> None:
    if grievance.project_id != project.id:
        raise WorksError("That complaint is not linked to this work.", 404)
    grievance.project_id = None
    timeline.grievance_event(
        db, grievance, "note_added", actor,
        note=f"No longer part of the development work “{project.name}”.",
        note_mr=f"आता “{project.name_mr}” या विकास कामाचा भाग नाही.",
    )
    timeline.project_event(
        db, project, "grievance_unlinked", actor,
        note=f"Complaint {grievance.id} unlinked.",
        note_mr=f"तक्रार {grievance.id} वेगळी केली.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# What can happen next, and what looks wrong
# ─────────────────────────────────────────────────────────────────────────────

def next_steps(project: Project, m: Money | None = None) -> dict:
    """What an officer may do to this work now.

    Sent with every project so the screen offers exactly these and nothing
    else. The alternative is a second copy of the stage rules in the frontend,
    which would be right until the first time one of them changed.
    """
    stage = project.stage
    m = m or money(project.entries)
    kinds = [k for k in ENTRY_KINDS if stage in _ENTRY_STAGES[k]]
    # Nothing is offered that could only be refused. Once the whole sanction
    # has arrived there is nothing left to receive, and nothing can be paid out
    # of an empty balance; a button for either would lead straight to an error.
    if m.awaiting <= 0.005 and "received" in kinds:
        kinds.remove("received")
    if m.balance <= 0.005 and "spent" in kinds:
        kinds.remove("spent")
    return {
        "actions": [a for a, (allowed, _, _) in _ACTIONS.items() if stage in allowed],
        "entry_kinds": kinds,
        "can_record_progress": stage == "in_progress",
    }


@dataclass
class Flag:
    """Something about a work that a person should look at.

    Each is a plain comparison of two recorded figures, stated as what it is.
    None of them says anything is wrong: spending can run ahead of visible work
    for good reasons — materials bought, an advance paid — and a flag is only
    the suggestion that somebody go and see.
    """

    code: str
    severity: str  # 'warning' | 'info'
    message: str
    message_mr: str


# Spending this many percentage points ahead of recorded work raises a flag.
SPEND_AHEAD_POINTS = 25
# How long a work may sit at a stage before it is called stalled.
STALL_DAYS: dict[str, int] = {
    "proposed": 30, "verified": 30, "approved": 30,
    "budget_requested": 60, "budget_approved": 45, "funds_received": 30,
}
# An estimate revised upward by at least this fraction of the first one.
ESTIMATE_RISE = 0.20


def days_in_stage(project: Project, today: date | None = None) -> int | None:
    """Whole days since the work reached its current stage.

    Counted in calendar days, not twenty-four-hour periods. A work that reached
    a stage on 20 July has been there 76 days on 4 October whatever the time of
    day anyone looks, and a figure that changed between the morning and the
    afternoon would be one more thing to explain.
    """
    since = as_utc(project.stage_changed_at)
    if since is None:
        return None
    return max(((today or clock.today()) - since.date()).days, 0)


def flags(project: Project, m: Money | None = None, today: date | None = None) -> list[Flag]:
    m = m or money(project.entries)
    today = today or clock.today()
    stage = project.stage
    out: list[Flag] = []

    if stage == "in_progress" and m.approved:
        physical = physical_percent(project)
        if m.financial_percent - physical >= SPEND_AHEAD_POINTS:
            out.append(Flag(
                "spend_ahead", "warning",
                f"{m.financial_percent}% of the approved budget has been spent with "
                f"{physical}% of the work recorded. Worth checking on site.",
                f"मंजूर निधीपैकी {m.financial_percent}% खर्च झाला आहे, पण कामाची नोंद "
                f"{physical}% आहे. स्थळावर पडताळणी करावी.",
            ))

    waited = days_in_stage(project, today)
    limit = STALL_DAYS.get(stage)
    if limit is not None and waited is not None and waited > limit:
        label, label_mr = stage_label(stage)
        out.append(Flag(
            "stalled", "warning",
            f"At “{label}” for {waited} days.",
            f"“{label_mr}” या टप्प्यावर {waited} दिवस झाले.",
        ))

    if (
        project.expected_completion
        and project.expected_completion < today
        and stage in _ACTIVE
    ):
        when = project.expected_completion.strftime("%d %b %Y")
        out.append(Flag(
            "overdue", "warning",
            f"Expected by {when} and not yet complete.",
            f"अपेक्षित पूर्णता {when}; काम अद्याप पूर्ण नाही.",
        ))

    if m.first_estimate and m.estimated and m.estimated >= m.first_estimate * (1 + ESTIMATE_RISE):
        rise = round((m.estimated / m.first_estimate - 1) * 100)
        out.append(Flag(
            "estimate_up", "warning",
            f"Estimate revised from {rupees(m.first_estimate)} to {rupees(m.estimated)} (+{rise}%).",
            f"अंदाजपत्रक {rupees(m.first_estimate)} वरून {rupees(m.estimated)} करण्यात आले (+{rise}%).",
        ))

    if m.requested and m.approved and m.approved + 0.005 < m.requested:
        out.append(Flag(
            "partial_approval", "info",
            f"{rupees(m.approved)} approved against {rupees(m.requested)} requested.",
            f"{rupees(m.requested)} मागणीपैकी {rupees(m.approved)} मंजूर.",
        ))

    if stage in ("funds_received", "in_progress") and m.awaiting > 0.005:
        out.append(Flag(
            "funds_awaited", "info",
            f"{rupees(m.awaiting)} of the approved amount has not yet been received.",
            f"मंजूर रकमेपैकी {rupees(m.awaiting)} अद्याप प्राप्त झालेले नाहीत.",
        ))

    reopened = sum(1 for g in project.grievances if g.citizen_feedback == "reopened")
    if reopened:
        out.append(Flag(
            "reopened", "warning",
            f"{reopened} resident(s) say this work is not done.",
            f"{reopened} रहिवाशांच्या मते हे काम पूर्ण झालेले नाही.",
        ))

    return out
