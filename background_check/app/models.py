import uuid
from typing import List, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import constants as C
from app.database import Base, utcnow
from app.security import EncryptedString


class Candidate(Base):
    __tablename__ = "candidates"

    candidate_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    national_id: Mapped[str] = mapped_column(EncryptedString)
    national_id_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kra_pin: Mapped[str] = mapped_column(EncryptedString)
    email: Mapped[str] = mapped_column(String(254))
    phone_number: Mapped[str] = mapped_column(String(20))
    knec_index_number: Mapped[str] = mapped_column(String(40))
    university_name: Mapped[str] = mapped_column(String(200))

    interview_status: Mapped[str] = mapped_column(String(40), default=C.INTERVIEW_PENDING)

    consent_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_signed_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    otp_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    otp_expires_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    otp_sent_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    otp_attempts: Mapped[int] = mapped_column(Integer, default=0)

    dci_certificate_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    dci_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    dci_status: Mapped[str] = mapped_column(String(60), default=C.PENDING)
    academic_status: Mapped[str] = mapped_column(String(60), default=C.PENDING)
    employment_status: Mapped[str] = mapped_column(String(60), default=C.PENDING)
    final_scorecard: Mapped[str] = mapped_column(String(60), default=C.PENDING)
    discrepancies: Mapped[list] = mapped_column(JSON, default=list)
    workflow_status: Mapped[str] = mapped_column(String(20), default=C.WF_NOT_STARTED)

    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    employer_references: Mapped[List["EmployerReference"]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class EmployerReference(Base):
    __tablename__ = "employer_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.candidate_id"), index=True)
    employer_name: Mapped[str] = mapped_column(String(200))
    contact_email: Mapped[str] = mapped_column(String(254))

    status: Mapped[str] = mapped_column(String(20), default=C.REF_PENDING)
    token_sent_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[Optional[object]] = mapped_column(DateTime, nullable=True)

    employment_confirmed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    dates_accurate: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    position_accurate: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    would_rehire: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    candidate: Mapped[Candidate] = relationship(back_populates="employer_references")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.candidate_id"), index=True)
    event: Mapped[str] = mapped_column(String(80))
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime, default=utcnow)
