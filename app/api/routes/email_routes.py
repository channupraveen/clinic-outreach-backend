from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database.connection import get_db
from app.models.clinic_model import EmailTemplate, Clinic
from app.schemas.clinic_schema import (
    EmailTemplateOut,
    EmailTemplateCreate,
    EmailTemplateUpdate,
)

router = APIRouter(prefix="/emails", tags=["Emails"])


@router.get("", response_model=List[EmailTemplateOut])
def list_emails(status: str = None, db: Session = Depends(get_db)):
    query = db.query(EmailTemplate)
    if status:
        query = query.filter(EmailTemplate.status == status)
    return query.order_by(EmailTemplate.created_at.desc()).all()


@router.get("/{email_id}", response_model=EmailTemplateOut)
def get_email(email_id: int, db: Session = Depends(get_db)):
    email = db.query(EmailTemplate).filter(EmailTemplate.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    return email


@router.post("", response_model=EmailTemplateOut, status_code=201)
def create_email(payload: EmailTemplateCreate, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == payload.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    email = EmailTemplate(**payload.model_dump())
    db.add(email)
    db.commit()
    db.refresh(email)
    return email


@router.put("/{email_id}", response_model=EmailTemplateOut)
def update_email(email_id: int, payload: EmailTemplateUpdate, db: Session = Depends(get_db)):
    email = db.query(EmailTemplate).filter(EmailTemplate.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(email, key, value)

    # Auto-stamp sent_date when status flips to 'sent'
    if data.get("status") == "sent" and not email.sent_date:
        email.sent_date = datetime.utcnow()

    db.commit()
    db.refresh(email)
    return email


@router.delete("/{email_id}", status_code=204)
def delete_email(email_id: int, db: Session = Depends(get_db)):
    email = db.query(EmailTemplate).filter(EmailTemplate.id == email_id).first()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    db.delete(email)
    db.commit()
    return None
