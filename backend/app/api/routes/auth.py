"""Authentication: sign in, refresh, whoami, password change, registration, user admin."""

import difflib
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import hashlib
import html
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import func, select
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
    aadhaar_digest,
    generate_otp,
    generate_reset_code,
    hash_password,
    is_valid_aadhaar,
    normalise_aadhaar,
    normalise_reset_code,
    verify_password,
)
from app.db.session import get_db
from app.models import AuthAttempt, Citizen, KnownDevice, LoginChallenge, PasswordReset, RegistrationRequest, User, Village
from app.services import notify, ratelimit
from app.schemas import (
    LoginChallengeOut,
    LoginChallengeStatus,
    LoginRequest,
    OtpRequest,
    OtpReset,
    OtpSent,
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


def _account_key(db: Session, email: str | None, aadhaar: str | None) -> str:
    """The email an identifier resolves to, or a stable stand-in if none does.

    Aadhaar sign-in resolves the number to the resident, then to their account,
    and from there behaves exactly like email sign-in — same throttle, same
    audit row, same refusal. An Aadhaar that matches nobody gets a pseudonymous
    key derived from its digest, so it is throttled identically to a real one
    and the response cannot reveal whether the number is registered.
    """
    if email:
        return email.lower().strip()
    digits = normalise_aadhaar(aadhaar)
    if not is_valid_aadhaar(digits):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An Aadhaar number has 12 digits and does not start with 0 or 1.",
        )
    digest = aadhaar_digest(digits)
    citizen = db.scalar(select(Citizen).where(Citizen.aadhaar_hash == digest))
    if citizen is not None:
        user = db.scalar(select(User).where(User.citizen_id == citizen.id))
        if user is not None:
            return user.email
    return f"aadhaar:{digest[:24]}"


DEMO_DOMAINS = ("@panchayat.gov.in", "@citizen.panchayat.gov.in")


def _is_demo_account(email: str) -> bool:
    """Seeded demo accounts are shared across every laptop at a presentation,
    so they never wait for new-device approval: the listed addresses, and any
    address on the demo domains the seed uses."""
    email = email.lower()
    return email in settings.device_check_exempt or email.endswith(DEMO_DOMAINS)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _new_device_challenge(
    db: Session, user: User, body: LoginRequest, request: Request, ip: str | None
) -> LoginChallengeOut | None:
    """Hold a sign-in from a device this account has never used.

    The first device an account signs in from is trusted as its home device,
    so nobody is challenged on their very first sign-in. After that, a correct
    password from an unknown device is not enough on its own: an alert goes to
    the phone and email on record, and the owner approves or denies it.
    """
    if _is_demo_account(user.email):
        return None  # shared demo account: let every device in
    device_hash = _sha(f"{user.id}:{body.device_id or 'no-device-id'}")
    known = list(db.scalars(select(KnownDevice).where(KnownDevice.user_id == user.id)))
    if not known:
        db.add(KnownDevice(id=f"dev_{uuid4().hex[:16]}", user_id=user.id,
                           device_hash=device_hash, label=body.device_label))
        db.commit()
        return None
    if any(d.device_hash == device_hash for d in known):
        return None

    poll, decision = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    challenge = LoginChallenge(
        id=f"lch_{uuid4().hex[:16]}", user_id=user.id, device_hash=device_hash,
        label=(body.device_label or "Unknown browser")[:200], ip=ip,
        poll_hash=_sha(poll), decision_hash=_sha(decision),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.LOGIN_APPROVAL_TTL_MINUTES),
    )
    db.add(challenge)
    db.commit()

    url = (
        f"{str(request.base_url).rstrip('/')}{settings.API_V1_PREFIX}"
        f"/auth/login-challenges/{challenge.id}/decide?token={decision}"
    )
    phone = user.citizen.phone if user.citizen else None
    notify.send_new_device_alert(phone=phone, email=user.email,
                                 device=challenge.label, decision_url=url)
    ratelimit.record(db, email=user.email, ip=ip, outcome="device_challenged", user_id=user.id)
    return LoginChallengeOut(
        challenge_id=challenge.id,
        poll_token=poll,
        sent_to=[*([_mask_phone(phone)] if phone else []), _mask_email(user.email)],
        expires_in_minutes=settings.LOGIN_APPROVAL_TTL_MINUTES,
        demo_decision_url=url if settings.OTP_DEMO_MODE else None,
    )


@router.post(
    "/login",
    response_model=TokenPair,
    responses={202: {"model": LoginChallengeOut, "description": "New device: approval pending"}},
)
def login(
    body: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenPair:
    email = _account_key(db, body.email, body.aadhaar)
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
            detail=(
                "Incorrect Aadhaar number or password."
                if body.aadhaar and not body.email
                else "Incorrect email or password."
            ),
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

    challenge = _new_device_challenge(db, user, body, request, ip)
    if challenge is not None:
        return JSONResponse(status_code=202, content=challenge.model_dump(by_alias=True))

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    ratelimit.record(
        db, email=email, ip=ip, outcome="ok", successful=True, user_id=user.id
    )
    return _issue(user)


def _load_challenge(db: Session, challenge_id: str) -> LoginChallenge:
    challenge = db.get(LoginChallenge, challenge_id)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown sign-in request.")
    if challenge.status == "pending" and as_utc(challenge.expires_at) <= datetime.now(timezone.utc):
        challenge.status = "expired"
        db.commit()
    return challenge


@router.get("/login-challenges/{challenge_id}", response_model=LoginChallengeStatus)
def poll_login_challenge(
    challenge_id: str, poll: str, request: Request, db: Session = Depends(get_db)
) -> LoginChallengeStatus:
    """The waiting device asks whether the owner has answered yet."""
    challenge = _load_challenge(db, challenge_id)
    if not secrets.compare_digest(challenge.poll_hash, _sha(poll)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown sign-in request.")
    if challenge.status != "approved":
        return LoginChallengeStatus(status="denied" if challenge.status == "used" else challenge.status)

    user = db.get(User, challenge.user_id)
    if user is None or not user.is_active:
        return LoginChallengeStatus(status="denied")
    # Tokens are handed over exactly once, and the device becomes trusted.
    challenge.status = "used"
    db.add(KnownDevice(id=f"dev_{uuid4().hex[:16]}", user_id=user.id,
                       device_hash=challenge.device_hash, label=challenge.label))
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    ratelimit.record(db, email=user.email, ip=ratelimit.client_ip(request),
                     outcome="ok", successful=True, user_id=user.id)
    return LoginChallengeStatus(status="approved", tokens=_issue(user))


def _decision_page(title: str, body_html: str) -> HTMLResponse:
    return HTMLResponse(f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,sans-serif;
background:linear-gradient(135deg,#0c1838,#142a63);color:#1e293b}}.c{{background:#fff;border-radius:16px;
padding:28px;max-width:380px;width:calc(100% - 32px);box-shadow:0 20px 40px -12px #0008;border-top:4px solid #ff8a1f}}
h1{{font-size:20px;margin:0 0 8px;color:#0f1f4b}}p{{font-size:14px;line-height:1.5;color:#475569}}
.r{{display:flex;gap:10px;margin-top:18px}}button{{flex:1;padding:12px;border:0;border-radius:10px;font-weight:700;
font-size:14px;cursor:pointer}}.a{{background:#13a05a;color:#fff}}.d{{background:#e11d48;color:#fff}}
dl{{font-size:13px;background:#f1f5f9;border-radius:10px;padding:10px 14px}}dt{{font-weight:700}}dd{{margin:0 0 6px}}</style>
</head><body><div class="c">{body_html}</div></body></html>""")


@router.get("/login-challenges/{challenge_id}/decide", response_class=HTMLResponse)
def decision_form(challenge_id: str, token: str, db: Session = Depends(get_db)) -> HTMLResponse:
    """The page the SMS/email link opens. A GET only shows the question; the
    answer is a POST, so a link preview in a messaging app cannot approve it."""
    challenge = _load_challenge(db, challenge_id)
    if not secrets.compare_digest(challenge.decision_hash, _sha(token)):
        return _decision_page("Invalid link", "<h1>Invalid link</h1><p>This link is not valid.</p>")
    if challenge.status != "pending":
        return _decision_page("Already answered",
                              f"<h1>Already answered</h1><p>This sign-in request is {challenge.status}.</p>")
    when = as_utc(challenge.created_at).strftime("%d %b %Y, %H:%M UTC")
    return _decision_page("Is this you?", f"""
<h1>New sign-in detected</h1>
<p>Someone entered the correct password for your E-Panchayat account from a device we do not recognise. <b>Is this you?</b></p>
<dl><dt>Device</dt><dd>{html.escape(challenge.label or "Unknown")}</dd>
<dt>IP address</dt><dd>{html.escape(challenge.ip or "Unknown")}</dd><dt>Time</dt><dd>{when}</dd></dl>
<form method="post" class="r"><input type="hidden" name="token" value="{html.escape(token)}">
<button class="a" name="action" value="approve">Yes, approve</button>
<button class="d" name="action" value="deny">No, deny entry</button></form>""")


@router.post("/login-challenges/{challenge_id}/decide", response_class=HTMLResponse)
def decide(
    challenge_id: str,
    request: Request,
    token: str = Form(...),
    action: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    challenge = _load_challenge(db, challenge_id)
    if not secrets.compare_digest(challenge.decision_hash, _sha(token)) or action not in ("approve", "deny"):
        return _decision_page("Invalid link", "<h1>Invalid link</h1><p>This link is not valid.</p>")
    if challenge.status != "pending":
        return _decision_page("Already answered",
                              f"<h1>Already answered</h1><p>This sign-in request is {challenge.status}.</p>")
    challenge.status = "approved" if action == "approve" else "denied"
    db.commit()
    user = db.get(User, challenge.user_id)
    ratelimit.record(db, email=user.email if user else "", ip=ratelimit.client_ip(request),
                     outcome=f"device_{challenge.status}", user_id=challenge.user_id)
    if action == "approve":
        return _decision_page("Approved", "<h1>&#10003; Sign-in approved</h1>"
                              "<p>The device will be signed in and remembered. You can close this page.</p>")
    return _decision_page("Denied", "<h1>&#10007; Entry denied</h1><p>The device was blocked. Someone knows "
                          "your password: change it now, or use <b>Forgot password</b> to reset it.</p>")


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
# Self-service recovery by OTP
#
# A resident who has forgotten their password asks for a six-digit OTP, sent to
# the phone and email on record. Two conditions send them to the office instead:
#
#   * the account is locked — five wrong passwords inside the sign-in window.
#     Someone who is guessing may also be holding the resident's phone, so an
#     OTP is no longer enough; an officer verifies them in person and issues the
#     office reset code (POST /auth/users/{id}/password-reset).
#   * the account is staff. Officer and admin passwords are reset by an admin.
# ─────────────────────────────────────────────────────────────────────────────

_OTP_LOCKED = HTTPException(
    status_code=status.HTTP_423_LOCKED,
    detail=(
        "This account is locked after repeated failed sign-in attempts. For your "
        "security, visit the Gram Panchayat office: an officer will verify you and "
        "give you a reset code."
    ),
)


def _is_locked(db: Session, email: str) -> bool:
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.LOGIN_WINDOW_MINUTES)
    return (
        ratelimit._count_failures(db, since=since, email=email)
        >= settings.LOGIN_MAX_FAILURES_PER_EMAIL
    )


def _mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return f"SMS to ******{digits[-4:]}" if len(digits) >= 4 else "SMS"


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"Email to {local[:1]}{'*' * max(len(local) - 1, 2)}@{domain}"


@router.post("/forgot-password", response_model=OtpSent)
def request_otp(
    body: OtpRequest, request: Request, db: Session = Depends(get_db)
) -> OtpSent:
    email = _account_key(db, body.email, body.aadhaar)
    ip = ratelimit.client_ip(request)

    if _is_locked(db, email):
        ratelimit.record(db, email=email, ip=ip, outcome="otp_locked")
        raise _OTP_LOCKED

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    sent_recently = db.scalar(
        select(func.count())
        .select_from(AuthAttempt)
        .where(AuthAttempt.email == email)
        .where(AuthAttempt.outcome == "otp_sent")
        .where(AuthAttempt.created_at >= since)
    ) or 0
    if sent_recently >= settings.OTP_MAX_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many OTPs requested. Wait an hour, or visit the Panchayat office.",
            headers={"Retry-After": "3600"},
        )

    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or user.role != "citizen":
        # Staff and unknown accounts get the same answer: nothing self-service.
        ratelimit.record(db, email=email, ip=ip, outcome="otp_refused")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "We could not send an OTP for that account. Residents can recover "
                "access at the Panchayat office; staff should contact the administrator."
            ),
        )

    otp = generate_otp()
    now = datetime.now(timezone.utc)
    # A new OTP voids any earlier unused one, office codes included.
    for old in db.scalars(
        select(PasswordReset)
        .where(PasswordReset.user_id == user.id)
        .where(PasswordReset.used_at.is_(None))
    ):
        old.used_at = now
    db.add(PasswordReset(
        id=f"pwr_{uuid4().hex[:16]}",
        user_id=user.id,
        hashed_code=hash_password(otp),
        issued_by_id=None,  # None marks a self-service OTP
        expires_at=now + timedelta(minutes=settings.OTP_TTL_MINUTES),
    ))
    db.commit()

    phone = user.citizen.phone if user.citizen else None
    sent_to = notify.send_otp(otp, phone=phone, email=user.email)
    ratelimit.record(db, email=email, ip=ip, outcome="otp_sent", user_id=user.id)

    return OtpSent(
        sent_to=[*( [_mask_phone(phone)] if phone else []), _mask_email(user.email)]
        if sent_to else [],
        expires_in_minutes=settings.OTP_TTL_MINUTES,
        demo_otp=otp if settings.OTP_DEMO_MODE else None,
    )


@router.post("/forgot-password/verify", status_code=status.HTTP_204_NO_CONTENT)
def verify_otp(body: OtpReset, request: Request, db: Session = Depends(get_db)) -> None:
    email = _account_key(db, body.email, body.aadhaar)
    ip = ratelimit.client_ip(request)

    try:
        ratelimit.check_reset_allowed(db, email, ip)
    except HTTPException:
        ratelimit.record(db, email=email, ip=ip, outcome="rate_limited")
        raise
    if _is_locked(db, email):
        raise _OTP_LOCKED

    refused = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="That OTP is not valid or has expired. Request a new one.",
    )
    user = db.scalar(select(User).where(User.email == email))
    reset = None
    if user is not None:
        reset = db.scalar(
            select(PasswordReset)
            .where(PasswordReset.user_id == user.id)
            .where(PasswordReset.used_at.is_(None))
            .where(PasswordReset.issued_by_id.is_(None))
            .order_by(PasswordReset.created_at.desc())
        )
    entered = "".join(ch for ch in body.otp if ch.isdigit())
    if (
        user is None
        or reset is None
        or as_utc(reset.expires_at) <= datetime.now(timezone.utc)
        or not verify_password(entered, reset.hashed_code)
    ):
        ratelimit.record(db, email=email, ip=ip, outcome="reset_bad_code")
        raise refused

    user.hashed_password = hash_password(body.new_password)
    _revoke_existing_sessions(user)
    reset.used_at = datetime.now(timezone.utc)
    db.commit()
    ratelimit.record(db, email=email, ip=ip, outcome="otp_redeemed", user_id=user.id)


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

    if db.scalar(select(User).where(User.email == req.email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        )

    if not body.citizen_id:
        if user.email.lower() not in settings.demo_unmatched_approvers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approving an application requires choosing the resident record it belongs to.",
            )
        body.citizen_id = _citizen_from_application(db, req, scope)
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


def _citizen_from_application(db: Session, req: RegistrationRequest, scope: str | None) -> str:
    """Demo accounts only: register an applicant who is not on the village
    register by creating a resident record from what they applied with. The
    unknown attributes are left at neutral defaults for an officer to complete."""
    village_id = req.village_id or scope
    if village_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The application names no village. Ask the applicant which Gram Panchayat they belong to.",
        )
    citizen = Citizen(
        id=f"cit_{uuid4().hex[:8]}",
        name=req.full_name,
        name_mr=req.full_name,
        age=18,
        gender="Other",
        gender_mr="इतर",
        occupation="Not recorded",
        occupation_mr="नोंद नाही",
        income=0,
        ward=req.claimed_ward or 1,
        village_id=village_id,
        phone=req.phone,
    )
    db.add(citizen)
    db.flush()
    return citizen.id


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
    # Which village the account belongs to is decided here and nowhere else.
    #
    # This used to store no village at all, for any role. An officer made this
    # way was therefore unscoped, and unscoped is what an admin is: they saw
    # every resident in the block. There was no field to say which Gram
    # Panchayat they served, so there was no way to create one correctly.
    village_id: str | None = None
    citizen_id: str | None = None

    if body.role == "citizen":
        if not body.citizen_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A citizen account must be linked to a citizen record.",
            )
        citizen = db.get(Citizen, body.citizen_id)
        if citizen is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="That resident record does not exist.",
            )
        # A resident's account follows the resident; it is not the admin's to
        # choose, or an account could be pointed at a village its owner does
        # not live in.
        citizen_id = citizen.id
        village_id = citizen.village_id
    elif body.role == "officer":
        if not body.village_id or db.get(Village, body.village_id) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "An officer account must be assigned to a Gram Panchayat. "
                    "Give the village it serves."
                ),
            )
        village_id = body.village_id
    # An admin has no village: that absence is what "the whole block" means.

    user = User(
        id=f"usr_{uuid4().hex[:12]}",
        email=email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        citizen_id=citizen_id,
        village_id=village_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
