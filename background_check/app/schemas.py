from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmployerIn(BaseModel):
    employer_name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr


class CandidateCreate(BaseModel):
    candidate_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    full_name: str = Field(min_length=2, max_length=200)
    national_id: str = Field(pattern=r"^\d{7,8}$")
    kra_pin: str = Field(pattern=r"^[AP]\d{9}[A-Z]$")
    email: EmailStr
    phone_number: str = Field(pattern=r"^(\+254|0)[17]\d{8}$")
    knec_index_number: str = Field(min_length=3, max_length=40)
    university_name: str = Field(min_length=2, max_length=200)
    previous_employers: List[EmployerIn] = Field(default_factory=list, max_length=10)

    @field_validator("kra_pin", mode="before")
    @classmethod
    def _upper_pin(cls, v):
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("full_name", "national_id", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class CandidateCreated(BaseModel):
    candidate_id: str
    full_name: str
    interview_status: str
    consent_signed: bool
    employer_references: int


class InterviewUpdate(BaseModel):
    passed: bool


class OtpVerify(BaseModel):
    otp: str = Field(pattern=r"^\d{6}$")


class EmployerResponseIn(BaseModel):
    employment_confirmed: bool
    dates_accurate: bool
    position_accurate: bool
    would_rehire: Optional[bool] = None
    comments: Optional[str] = Field(default=None, max_length=2000)


class EmployerRefStatus(BaseModel):
    employer_name: str
    status: str


class StatusOut(BaseModel):
    candidate_id: str
    full_name: str
    interview_status: str
    consent_signed: bool
    workflow_status: str
    dci_status: str
    dci_reference: Optional[str]
    academic_status: str
    employment_status: str
    final_scorecard: str
    discrepancies: List[str]
    employer_references: List[EmployerRefStatus]
