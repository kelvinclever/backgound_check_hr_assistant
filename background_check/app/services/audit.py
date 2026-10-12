from typing import Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def record(db: Session, candidate_id: str, event: str, detail: Optional[str] = None) -> None:
    """Adds an audit row to the session (caller commits). Never put raw PII in `detail`."""
    db.add(AuditLog(candidate_id=candidate_id, event=event, detail=detail))
