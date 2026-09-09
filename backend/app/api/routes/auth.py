"""Authentication: sign in, refresh, whoami, password change, registration, user admin."""

import difflib
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import (
    get_current_user,
    require_admin,
    require_officer,
    token_is_revoked,
    village_scope,
)
from app.core.security import (
    as_utc,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_reset_code,
    hash_password,
    normalise_reset_code,
    verify_password,
)
from app.db.session import get_db
from app.models import Citizen, PasswordReset, RegistrationRequest, User
from app.services import ratelimit
from app.schemas import (
    LoginRequest,
    PasswordChange,
    PasswordResetIssued,
    PasswordResetRedeem,
    RefreshRequest,
    RegistrationCreate,
    RegistrationDecision,
    RegistrationOut,
    TokenPair,
    UserCreate,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.role, user.citizen_id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=TokenPair)
def login(
    body: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenPair:
    email = body.email.lower()
    ip = ratelimit.client_ip(request)

    # Before the password is checked, not after: a throttled attempt should not
    # get to spend a bcrypt verification, and should not be told whether the
    # address it named exists.
    try:
        ratelimit.check_login_allowed(db, email, ip)
    except HTTPException:
        ratelimit.record(db, email=email, ip=ip, outcome="rate_limited")
        raise

    user = db.scalar(select(User).where(User.email == email))

    # Same message and same work either way, so the response can't be used to
    # discover which email addresses exist.
    if user is None or not verify_password(body.password, user.hashed_password):
        # One exception: somebody who applied for an account and typed their own
        # password correctly is told where their application stands. Proving the
        # password first means this still can't be used to enumerate addresses.
        pending = db.scalar(
            select(RegistrationRequest)
            .where(RegistrationRequest.email == email)
            .where(RegistrationRequest.status.in_(("pending", "rejected")))
            .order_by(RegistrationRequest.created_at.desc())
        )
        if pending and verify_password(body.password, pending.hashed_password):
            # They proved the password, so this is not a guess and must not
            # count toward a lockout — otherwise an applicant checking on their
            # own application would throttle themselves out of it.
            if pending.status == "pending":
                ratelimit.record(
                    db, email=email, ip=ip, outcome="registration_pending"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Your application is still being verified by the Panchayat "
                        "office. You will be able to sign in once it is approved."
                    ),
                )
            ratelimit.record(db, email=email, ip=ip, outcome="registration_rejected")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your application was not approved. "
                    + (pending.review_note or "Contact the Panchayat office for details.")
                ),
            )
        ratelimit.record(
            db,
            email=email,
            ip=ip,
            outcome="bad_password" if user else "no_account",
            user_id=user.id if user else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    if not user.is_active:
        # Correct password, disabled account. Recorded, but not a guess.
        ratelimit.record(
            db, email=email, ip=ip, outcome="inactive", user_id=user.id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact the Panchayat office.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    ratelimit.record(
        db, email=email, ip=ip, outcome="ok", successful=True, user_id=user.id
    )
    return _issue(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token. Sign in again.",
        ) from None

    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable."
        )
    # A refresh token outlives an access token by a week, so this is the one
    # that matters: without the check, a password reset would leave whoever held
    # the account able to mint fresh access tokens for seven more days.
    if token_is_revoked(user, payload):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your password was changed. Sign in again.",
        )
    return _issue(user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


def _revoke_existing_sessions(user: User) -> None:
    """End every session issued before now.

    Truncated to the second because `iat` is whole seconds — see the note on
    `User.tokens_valid_from`.
    """
    user.tokens_valid_from = datetime.now(timezone.utc).replace(microsecond=0)


@router.post("/change-password", response_model=TokenPair)
def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenPair:
    """Change your own password, ending every other session.

    Returns a fresh token pair rather than 204. Changing a password revokes
    every token issued before it, including the one used to make this call, so
    without new tokens the caller would be signed out by their own success. The
    other sessions stay revoked, which is the point: someone who changes their
    password because they think it is known must not leave that person signed
    in for the week a refresh token lasts.
    """
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    user.hashed_password = hash_password(body.new_password)
    _revoke_existing_sessions(user)
    db.commit()
    return _issue(user)


# ─────────────────────────────────────────────────────────────────────────────
# Password reset
#
# There is no email or SMS gateway here, so "we have sent you a link" is not
# available — and building a flow whose message silently never arrives would be
# worse than having none. This uses the channel a Gram Panchayat actually has.
#
# A resident who cannot sign in goes to the office. An officer identifies them
# against the village register, which is the same check that already gates
# account approval, and issues a code. The system shows it once; the officer
# writes it down and hands it over. The resident chooses their own password with
# it, so the officer never learns what it becomes.
#
# An officer may reset residents of their own village and nobody else. An
# officer who could reset another officer, or an admin, would hold a route from
# one village login to the whole block.
# ─────────────────────────────────────────────────────────────────────────────


def _assert_may_reset(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use change-password to set your own password.",
        )
    if actor.role == "admin":
        return
    if target.role != "citizen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an admin can reset a staff account.",
        )
    scope = village_scope(actor)
    if scope is not None and target.village_id != scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That resident belongs to another Gram Panchayat.",
        )


@router.post("/users/{user_id}/password-reset", response_model=PasswordResetIssued)
def issue_password_reset(
    user_id: str,
    actor: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> PasswordResetIssued:
    """Issue a one-time code for a resident who cannot sign in.

    The code is in the response and nowhere else readable — only its bcrypt hash
    is stored. Issuing a new code voids any earlier unused one, so a resident
    who has been through this twice cannot be let in by the first slip of paper.
    """
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such account."
        )
    _assert_may_reset(actor, target)

    now = datetime.now(timezone.utc)
    for stale in db.scalars(
        select(PasswordReset)
        .where(PasswordReset.user_id == target.id)
        .where(PasswordReset.used_at.is_(None))
    ):
        stale.used_at = now

    code = generate_reset_code()
    expires_at = now + timedelta(hours=settings.PASSWORD_RESET_TTL_HOURS)
    db.add(
        PasswordReset(
            id=f"pwr_{uuid4().hex[:12]}",
            user_id=target.id,
            hashed_code=hash_password(normalise_reset_code(code)),
            issued_by_id=actor.id,
            expires_at=expires_at,
        )
    )
    db.commit()

    return PasswordResetIssued(
        code=code,
        expires_at=expires_at,
        user_email=target.email,
        user_name=target.full_name,
    )


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def redeem_password_reset(
    body: PasswordResetRedeem, request: Request, db: Session = Depends(get_db)
) -> None:
    """Set a new password using a code issued at the Panchayat office."""
    email = body.email.lower().strip()
    ip = ratelimit.client_ip(request)

    try:
        ratelimit.check_reset_allowed(db, email, ip)
    except HTTPException:
        ratelimit.record(db, email=email, ip=ip, outcome="rate_limited")
        raise

    # One refusal for every way this can fail — wrong code, expired code, code
    # already spent, no such account. Distinguishing them would say whether an
    # address holds an account and whether a reset is outstanding for it.
    refused = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "That reset code is not valid. Codes expire, and can be used only "
            "once. Ask the Panchayat office for a new one."
        ),
    )

    user = db.scalar(select(User).where(User.email == email))
    reset = None
    if user is not None:
        reset = db.scalar(
            select(PasswordReset)
            .where(PasswordReset.user_id == user.id)
            .where(PasswordReset.used_at.is_(None))
            .order_by(PasswordReset.created_at.desc())
        )

    entered = normalise_reset_code(body.code)
    if (
        user is None
        or reset is None
        or as_utc(reset.expires_at) <= datetime.now(timezone.utc)
        or not verify_password(entered, reset.hashed_code)
    ):
        ratelimit.record(db, email=email, ip=ip, outcome="reset_bad_code")
        raise refused

    user.hashed_password = hash_password(body.new_password)
    # Whoever knew the old password is signed out by this, which is the reason
    # a reset exists rather than a convenience on top of it.
    _revoke_existing_sessions(user)
    reset.used_at = datetime.now(timezone.utc)
    db.commit()
    ratelimit.record(
        db, email=email, ip=ip, outcome="reset_redeemed", user_id=user.id
    )


# ─────────────────────────────────────────────────────────────────────────────
# Registration
#
# A resident can apply for an account. Applying never creates a working login:
# it creates a request that an officer must match to a real resident record and
# approve. That gate exists because a citizen account can read one resident's
# income, documents and family details, so "which resident are you" is not a
# question the applicant gets to answer for themselves.
#
# Officer and admin accounts are not self-registrable at all. An officer can
# read every resident in the village; an admin can read the whole block. Those
# accounts are created by an admin through POST /auth/users.
# ─────────────────────────────────────────────────────────────────────────────


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _suggest_matches(db: Session, req: RegistrationRequest) -> list[dict]:
    """Residents who plausibly are this applicant, best first.

    This only ranks candidates for a human. Nothing here approves anything —
    the officer picks the record, and an unconvincing list is the correct
    outcome when the applicant does not appear in the register.
    """
    stmt = select(Citizen)
    if req.village_id:
        stmt = stmt.where(Citizen.village_id == req.village_id)
    candidates = list(db.scalars(stmt))

    applicant_phone = _digits(req.phone)
    name = (req.full_name or "").strip().lower()

    scored: list[tuple[float, Citizen, list[str]]] = []
    for c in candidates:
        reasons: list[str] = []
        score = 0.0

        if req.claimed_citizen_id and c.id == req.claimed_citizen_id.strip():
            score += 1.0
            reasons.append("ID quoted by applicant")

        if applicant_phone and _digits(c.phone) and _digits(c.phone)[-10:] == applicant_phone[-10:]:
            score += 0.8
            reasons.append("phone matches")

        similarity = difflib.SequenceMatcher(None, name, (c.name or "").lower()).ratio()
        if similarity >= 0.6:
            score += similarity * 0.6
            reasons.append(f"name {round(similarity * 100)}% similar")

        if req.claimed_ward is not None and c.ward == req.claimed_ward:
            score += 0.15
            reasons.append("same ward")

        if score >= 0.4:
            scored.append((score, c, reasons))

    scored.sort(key=lambda row: row[0], reverse=True)

    taken = {u.citizen_id for u in db.scalars(select(User).where(User.citizen_id.is_not(None)))}
    return [
        {
            "citizenId": c.id,
            "name": c.name,
            "nameMr": c.name_mr,
            "age": c.age,
            "ward": c.ward,
            "phone": c.phone,
            "villageId": c.village_id,
            "alreadyHasAccount": c.id in taken,
            "reasons": reasons,
            "confidence": round(min(score, 1.0), 2),
        }
        for score, c, reasons in scored[:8]
    ]


def _registration_out(db: Session, req: RegistrationRequest) -> RegistrationOut:
    out = RegistrationOut.model_validate(req, from_attributes=True)
    out.suggested_matches = _suggest_matches(db, req) if req.status == "pending" else []
    return out


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register(
    body: RegistrationCreate, request: Request, db: Session = Depends(get_db)
) -> dict:
    """Apply for a citizen account. Always returns the same acknowledgement.

    The response deliberately says nothing about whether the email is already
    registered — otherwise this endpoint becomes a way to test which residents
    hold accounts.
    """
    email = body.email.lower().strip()
    ip = ratelimit.client_ip(request)
    # An application is unauthenticated and lands in an officer's queue, so it
    # is the one endpoint here a script could use to bury real applicants.
    ratelimit.check_registration_allowed(db, ip)

    acknowledgement = {
        "status": "pending",
        "message": (
            "Your application has been sent to the Panchayat office. An officer "
            "will match it against the village register and you will be able to "
            "sign in once it is approved."
        ),
    }

    if db.scalar(select(User).where(User.email == email)):
        return acknowledgement
    existing = db.scalar(
        select(RegistrationRequest)
        .where(RegistrationRequest.email == email)
        .where(RegistrationRequest.status == "pending")
    )
    if existing:
        return acknowledgement

    db.add(
        RegistrationRequest(
            id=f"reg_{uuid4().hex[:12]}",
            full_name=body.full_name.strip(),
            email=email,
            hashed_password=hash_password(body.password),
            phone=body.phone,
            claimed_ward=body.claimed_ward,
            claimed_citizen_id=body.claimed_citizen_id,
            note=body.note,
            village_id=body.village_id,
            status="pending",
        )
    )
    db.commit()
    # Counted only when an application was actually created. The two early
    # returns above write nothing, so there is nothing there to throttle.
    ratelimit.record(db, email=email, ip=ip, outcome="registration_filed")
    return acknowledgement


@router.get("/registrations", response_model=list[RegistrationOut])
def list_registrations(
    status_filter: str = "pending",
    user: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> list[RegistrationOut]:
    stmt = select(RegistrationRequest).order_by(RegistrationRequest.created_at.desc())
    if status_filter != "all":
        stmt = stmt.where(RegistrationRequest.status == status_filter)

    scope = village_scope(user)
    if scope is not None:
        # An officer sees applications for their own village, plus ones that did
        # not name a village at all — those are the applicants who need help
        # most, and an officer can only ever approve them onto a local record.
        stmt = stmt.where(
            (RegistrationRequest.village_id == scope)
            | (RegistrationRequest.village_id.is_(None))
        )

    return [_registration_out(db, req) for req in db.scalars(stmt)]


@router.post("/registrations/{registration_id}/decision", response_model=RegistrationOut)
def decide_registration(
    registration_id: str,
    body: RegistrationDecision,
    user: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> RegistrationOut:
    req = db.get(RegistrationRequest, registration_id)
    if req is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found.")
    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This application was already {req.status}.",
        )

    scope = village_scope(user)
    if scope is not None and req.village_id is not None and req.village_id != scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This application belongs to another village.",
        )

    if not body.approve:
        req.status = "rejected"
        req.review_note = body.review_note
        req.reviewed_by_id = user.id
        req.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(req)
        return _registration_out(db, req)

    if not body.citizen_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approving an application requires choosing the resident record it belongs to.",
        )
    citizen = db.get(Citizen, body.citizen_id)
    if citizen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="That resident record does not exist."
        )
    # An officer must not be able to attach an account to a resident of a
    # village they do not run.
    if scope is not None and citizen.village_id != scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That resident belongs to another village.",
        )
    if db.scalar(select(User).where(User.citizen_id == citizen.id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That resident already has a portal account.",
        )
    if db.scalar(select(User).where(User.email == req.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    db.add(
        User(
            id=f"usr_{uuid4().hex[:12]}",
            email=req.email,
            # Reused as the applicant set it. It was never a working login until
            # this moment, so nothing was exposed by holding it.
            hashed_password=req.hashed_password,
            full_name=req.full_name,
            role="citizen",
            citizen_id=citizen.id,
            village_id=citizen.village_id,
        )
    )
    req.status = "approved"
    req.matched_citizen_id = citizen.id
    req.review_note = body.review_note
    req.reviewed_by_id = user.id
    req.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(req)
    return _registration_out(db, req)


@router.get("/users", response_model=list[UserOut])
def list_users(
    user: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[User]:
    """The portal accounts this user may act on.

    Admin-only until the password reset needed it. An officer may reset a
    resident of their own village, but had no way to find that resident's
    account: the reset takes a user id, and the only endpoint that could
    produce one was closed to them. An officer at the counter with a resident
    in front of them could not complete the flow the feature exists for.

    So the list is scoped to exactly what the reset itself permits. An officer
    sees the resident accounts of their own village and nothing else — not
    other officers, not admins, not a neighbouring Gram Panchayat's residents.
    An admin sees everything. The two rules are deliberately the same, so the
    list can never offer an account that the reset would then refuse.
    """
    stmt = select(User).order_by(User.email)
    scope = village_scope(user)
    if scope is not None:
        stmt = stmt.where(User.role == "citizen", User.village_id == scope)
    return list(db.scalars(stmt))


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )
    if body.role == "citizen" and not body.citizen_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A citizen account must be linked to a citizen record.",
        )

    user = User(
        id=f"usr_{uuid4().hex[:12]}",
        email=email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        citizen_id=body.citizen_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
