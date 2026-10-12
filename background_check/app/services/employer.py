import logging
from typing import List, Tuple

from sqlalchemy.orm import Session

from app import constants as C
from app.config import get_settings
from app.database import utcnow
from app.models import Candidate, EmployerReference
from app.schemas import EmployerResponseIn
from app.security import TokenError, make_employer_token, read_employer_token
from app.services import audit, notifications

logger = logging.getLogger(__name__)


class AlreadyRespondedError(Exception):
    pass


def reference_link(ref: EmployerReference) -> str:
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/api/v1/employer/references/{make_employer_token(ref.id)}"


def dispatch_pending(db: Session, candidate: Candidate) -> None:
    """Emails each employer exactly once. Failed sends stay unsent and retry on the next run."""
    for ref in candidate.employer_references:
        if ref.token_sent_at is not None:
            continue
        body = (
            f"Hello,\n\n{candidate.full_name} has named {ref.employer_name} as a previous employer "
            f"and consented to a reference check.\n\nPlease confirm their employment details here "
            f"(link expires in {get_settings().employer_token_ttl_days} days):\n{reference_link(ref)}\n"
        )
        try:
            notifications.send_email(ref.contact_email, "Employment reference request", body)
        except Exception:
            logger.exception("Failed to email employer reference %s", ref.id)
            continue
        ref.token_sent_at = utcnow()
        audit.record(db, candidate.candidate_id, "employer_reference_sent", ref.employer_name)


def evaluate(candidate: Candidate) -> Tuple[str, List[str]]:
    refs = candidate.employer_references
    if not refs:
        return C.NOT_APPLICABLE, []
    problems: List[str] = []
    pending = False
    for r in refs:
        if r.status != C.REF_RESPONDED:
            pending = True
            continue
        if not (r.employment_confirmed and r.dates_accurate and r.position_accurate):
            problems.append(f"Employer '{r.employer_name}' did not confirm employment details")
        if r.would_rehire is False:
            problems.append(f"Employer '{r.employer_name}' would not rehire (HR to review)")
    if problems:
        return C.MANUAL_REVIEW, problems
    return (C.PENDING_EMPLOYER if pending else C.VERIFIED), []


def resolve_token(db: Session, token: str) -> EmployerReference:
    ref_id = read_employer_token(token)  # raises TokenError / TokenExpiredError
    ref = db.get(EmployerReference, ref_id)
    if ref is None:
        raise TokenError("Unknown reference")
    return ref


def submit_response(db: Session, token: str, data: EmployerResponseIn) -> EmployerReference:
    ref = resolve_token(db, token)
    if ref.status == C.REF_RESPONDED:
        raise AlreadyRespondedError()
    ref.employment_confirmed = data.employment_confirmed
    ref.dates_accurate = data.dates_accurate
    ref.position_accurate = data.position_accurate
    ref.would_rehire = data.would_rehire
    ref.comments = data.comments
    ref.status = C.REF_RESPONDED
    ref.responded_at = utcnow()
    audit.record(db, ref.candidate_id, "employer_reference_received", ref.employer_name)
    db.commit()
    return ref
