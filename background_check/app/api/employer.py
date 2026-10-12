from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app import constants as C
from app.database import get_db
from app.schemas import EmployerResponseIn
from app.security import TokenError, TokenExpiredError
from app.services import employer as employer_service
from app.workflow.runner import schedule_rerun_if_started

# Employer-facing: the signed, expiring token is the credential.
router = APIRouter(prefix="/api/v1/employer/references", tags=["employer reference"])


def _resolve(db: Session, token: str):
    try:
        return employer_service.resolve_token(db, token)
    except TokenExpiredError:
        raise HTTPException(410, "This reference link has expired.")
    except TokenError:
        raise HTTPException(404, "Invalid reference link.")


@router.get("/{token}")
def reference_info(token: str, db: Session = Depends(get_db)):
    ref = _resolve(db, token)
    return {
        "employer_name": ref.employer_name,
        "candidate_name": ref.candidate.full_name,
        "already_responded": ref.status == C.REF_RESPONDED,
    }


@router.post("/{token}")
def submit_reference(token: str, body: EmployerResponseIn, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        ref = employer_service.submit_response(db, token, body)
    except TokenExpiredError:
        raise HTTPException(410, "This reference link has expired.")
    except TokenError:
        raise HTTPException(404, "Invalid reference link.")
    except employer_service.AlreadyRespondedError:
        raise HTTPException(409, "A response has already been submitted.")
    schedule_rerun_if_started(background_tasks, ref.candidate)
    return {"message": "Thank you. Your response has been recorded."}
