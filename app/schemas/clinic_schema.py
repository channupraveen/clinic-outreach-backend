from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


# --- Clinic ---
class ClinicBase(BaseModel):
    clinic_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    clinic_type: Optional[str] = None
    notes: Optional[str] = None


class ClinicCreate(ClinicBase):
    pass


class ClinicUpdate(BaseModel):
    clinic_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    clinic_type: Optional[str] = None
    notes: Optional[str] = None


class ClinicOut(ClinicBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Clinic Issue ---
class ClinicIssueBase(BaseModel):
    issue_type: str
    priority_score: Optional[float] = 0.0


class ClinicIssueCreate(ClinicIssueBase):
    clinic_id: int


class ClinicIssueOut(ClinicIssueBase):
    id: int
    clinic_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Email Template ---
class EmailTemplateBase(BaseModel):
    service_type: Optional[str] = None
    subject: Optional[str] = None
    email_body: Optional[str] = None
    prompt_used: Optional[str] = None
    status: Optional[str] = "draft"


class EmailTemplateCreate(EmailTemplateBase):
    clinic_id: int


class EmailTemplateUpdate(BaseModel):
    subject: Optional[str] = None
    email_body: Optional[str] = None
    status: Optional[str] = None


class EmailTemplateOut(EmailTemplateBase):
    id: int
    clinic_id: int
    sent_date: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Prompt Generation ---
class PromptGenerateRequest(BaseModel):
    clinic_id: int
    issue: str
    service: str
    tone: Optional[str] = "friendly"


class PromptGenerateResponse(BaseModel):
    prompt: str


# --- Upload response ---
class UploadResponse(BaseModel):
    inserted: int
    skipped: int
    total: int
    message: str
