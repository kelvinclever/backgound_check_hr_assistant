import os
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import constants as C
from app.api.deps import get_candidate_or_404, require_hr
from app.config import get_settings
from app.database import get_db
from app.models import Candidate, EmployerReference
from app.schemas import CandidateCreate, CandidateCreated, InterviewUpdate
from app.security import hash_identifier
from app.services import audit
from app.workflow.runner import schedule_rerun_if_started

router = APIRouter(prefix="/api/v1/candidates", tags=["candidates (HR)"], dependencies=[Depends(require_hr)])


@router.post("", response_model=CandidateCreated, status_code=201)
def create_candidate(payload: CandidateCreate, db: Session = Depends(get_db)):
    cid = payload.candidate_id or f"CAND-{uuid.uuid4().hex[:10].upper()}"
    nid_hash = hash_identifier(payload.national_id)
    if db.get(Candidate, cid) or db.scalar(select(Candidate).where(Candidate.national_id_hash == nid_hash)):
        raise HTTPException(409, "A candidate with this ID or national ID already exists.")

    c = Candidate(
        candidate_id=cid,
        full_name=payload.full_name,
        national_id=payload.national_id,
        national_id_hash=nid_hash,
        kra_pin=payload.kra_pin,
        email=payload.email,
        phone_number=payload.phone_number,
        knec_index_number=payload.knec_index_number,
        university_name=payload.university_name,
    )
    for e in payload.previous_employers:
        c.employer_references.append(EmployerReference(employer_name=e.employer_name, contact_email=e.contact_email))
    db.add(c)
    audit.record(db, cid, "candidate_created")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A candidate with this ID or national ID already exists.")
    return CandidateCreated(
        candidate_id=cid,
        full_name=c.full_name,
        interview_status=c.interview_status,
        consent_signed=c.consent_signed,
        employer_references=len(c.employer_references),
    )


@router.patch("/{candidate_id}/interview")
def set_interview_result(
    body: InterviewUpdate, c: Candidate = Depends(get_candidate_or_404), db: Session = Depends(get_db)
):
    c.interview_status = C.INTERVIEW_PASSED if body.passed else C.INTERVIEW_FAILED
    audit.record(db, c.candidate_id, "interview_status_set", c.interview_status)
    db.commit()
    return {"candidate_id": c.candidate_id, "interview_status": c.interview_status}


@router.post("/{candidate_id}/dci-certificate")
def upload_dci_certificate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    c: Candidate = Depends(get_candidate_or_404),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, f"File exceeds {settings.max_upload_bytes // (1024 * 1024)} MB limit.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are accepted.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    new_path = upload_dir / f"{uuid.uuid4().hex}.pdf"  # never use client-supplied names
    new_path.write_bytes(data)

    old_path = c.dci_certificate_path
    c.dci_certificate_path = str(new_path)
    audit.record(db, c.candidate_id, "dci_certificate_uploaded")
    db.commit()
    if old_path and os.path.exists(old_path):
        os.remove(old_path)

    schedule_rerun_if_started(background_tasks, c)
    return {"candidate_id": c.candidate_id, "message": "Certificate stored.", "reverification_queued": c.workflow_status != C.WF_NOT_STARTED}
