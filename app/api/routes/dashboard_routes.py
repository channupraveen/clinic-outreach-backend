from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.models.clinic_model import Clinic, EmailTemplate

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_clinics = db.query(func.count(Clinic.id)).scalar() or 0
    emails_sent = (
        db.query(func.count(EmailTemplate.id))
        .filter(EmailTemplate.status == "sent")
        .scalar()
        or 0
    )
    replies = (
        db.query(func.count(EmailTemplate.id))
        .filter(EmailTemplate.status == "replied")
        .scalar()
        or 0
    )
    followups = (
        db.query(func.count(EmailTemplate.id))
        .filter(EmailTemplate.status == "followup")
        .scalar()
        or 0
    )

    return {
        "totalClinics": total_clinics,
        "emailsSent": emails_sent,
        "replies": replies,
        "followups": followups,
    }
