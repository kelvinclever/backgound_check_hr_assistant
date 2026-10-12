import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Candidate


def require_hr(x_api_key: str = Header(default="")) -> None:
    expected = get_settings().hr_api_key.encode()
    if not secrets.compare_digest(x_api_key.encode(), expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


def get_candidate_or_404(candidate_id: str, db: Session = Depends(get_db)) -> Candidate:
    c = db.get(Candidate, candidate_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Candidate record not found.")
    return c
