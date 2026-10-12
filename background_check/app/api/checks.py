import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import constants as C
from app.api.deps import get_candidate_or_404, require_hr
from app.database import get_db, utcnow
from app.models import AuditLog, Candidate
from app.schemas import EmployerRefStatus, StatusOut
from app.services import audit
from app.workflow.runner import run_background_check

router = APIRouter(prefix="/api/v1/background-check", tags=["background check (HR)"], dependencies=[Depends(require_hr)])

_STALE_LOCK = datetime.timedelta(minutes=10)


@router.post("/{candidate_id}/trigger", status_code=202)
def trigger(background_tasks: BackgroundTasks, c: Candidate = Depends(get_candidate_or_404), db: Session = Depends(get_db)):
    if c.interview_status != C.INTERVIEW_PASSED:
        raise HTTPException(400, "Trigger Blocked: Candidate has not passed the interview stage.")
    if not c.consent_signed:
        raise HTTPException(400, "Consent Blocked: Digital consent (OTP verification) is required.")
    if c.workflow_status in (C.WF_QUEUED, C.WF_RUNNING) and c.updated_at and utcnow() - c.updated_at < _STALE_LOCK:
        raise HTTPException(409, "A verification run is already in progress.")

    c.workflow_status = C.WF_QUEUED
    audit.record(db, c.candidate_id, "workflow_triggered")
    db.commit()
    background_tasks.add_task(run_background_check, c.candidate_id)
    return {"status": "accepted", "candidate_id": c.candidate_id,
            "message": f"Background verification queued for {c.full_name}."}


@router.get("/status/{candidate_id}", response_model=StatusOut)
def get_status(c: Candidate = Depends(get_candidate_or_404)):
    return StatusOut(
        candidate_id=c.candidate_id,
        full_name=c.full_name,
        interview_status=c.interview_status,
        consent_signed=c.consent_signed,
        workflow_status=c.workflow_status,
        dci_status=c.dci_status,
        dci_reference=c.dci_reference,
        academic_status=c.academic_status,
        employment_status=c.employment_status,
        final_scorecard=c.final_scorecard,
        discrepancies=c.discrepancies or [],
        employer_references=[EmployerRefStatus(employer_name=r.employer_name, status=r.status) for r in c.employer_references],
    )


@router.get("/{candidate_id}/audit")
def get_audit(c: Candidate = Depends(get_candidate_or_404), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.candidate_id == c.candidate_id).order_by(AuditLog.id)).all()
    return [{"at": r.created_at.isoformat(), "event": r.event, "detail": r.detail} for r in rows]
