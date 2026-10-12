import datetime
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_candidate_or_404
from app.config import get_settings
from app.database import get_db, utcnow
from app.models import Candidate
from app.schemas import OtpVerify
from app.security import generate_otp, hash_otp
from app.services import audit, notifications

# Candidate-facing: the emailed OTP is the credential, so no HR key here.
router = APIRouter(prefix="/api/v1/candidates/{candidate_id}/consent", tags=["consent (candidate)"])


@router.post("/request-otp", status_code=202)
def request_otp(c: Candidate = Depends(get_candidate_or_404), db: Session = Depends(get_db)):
    s = get_settings()
    if c.consent_signed:
        raise HTTPException(409, "Consent already recorded.")
    now = utcnow()
    if c.otp_sent_at and (now - c.otp_sent_at).total_seconds() < s.otp_resend_seconds:
        raise HTTPException(429, f"Please wait {s.otp_resend_seconds}s before requesting another code.")

    otp = generate_otp()
    c.otp_hash = hash_otp(c.candidate_id, otp)
    c.otp_sent_at = now
    c.otp_expires_at = now + datetime.timedelta(minutes=s.otp_ttl_minutes)
    c.otp_attempts = 0
    audit.record(db, c.candidate_id, "consent_otp_requested")
    db.commit()

    notifications.send_email(
        c.email,
        "Background check consent code",
        f"Your verification code is {otp}. It expires in {s.otp_ttl_minutes} minutes.\n"
        "By entering it you consent to pre-employment background verification "
        "(criminal record, academic and employment checks).",
    )
    return {"message": "Verification code sent to the email on file."}


@router.post("/verify-otp")
def verify_otp(body: OtpVerify, c: Candidate = Depends(get_candidate_or_404), db: Session = Depends(get_db)):
    s = get_settings()
    if c.consent_signed:
        raise HTTPException(409, "Consent already recorded.")
    if not c.otp_hash or not c.otp_expires_at or c.otp_expires_at < utcnow():
        raise HTTPException(400, "Code expired or not requested. Request a new one.")
    if c.otp_attempts >= s.otp_max_attempts:
        raise HTTPException(429, "Too many attempts. Request a new code.")

    c.otp_attempts += 1
    if not secrets.compare_digest(hash_otp(c.candidate_id, body.otp), c.otp_hash):
        db.commit()
        raise HTTPException(400, "Invalid code.")

    c.consent_signed = True
    c.consent_signed_at = utcnow()
    c.otp_hash = None
    audit.record(db, c.candidate_id, "consent_signed")
    db.commit()
    return {"candidate_id": c.candidate_id, "consent_signed": True}
