from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.clinic_model import Clinic
from app.schemas.clinic_schema import PromptGenerateRequest, PromptGenerateResponse
from app.services.prompt_service import generate_prompt

router = APIRouter(prefix="/prompt", tags=["Prompt"])


@router.post("/generate", response_model=PromptGenerateResponse)
def generate(payload: PromptGenerateRequest, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == payload.clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    prompt = generate_prompt(clinic, payload.issue, payload.service, payload.tone or "friendly")
    return PromptGenerateResponse(prompt=prompt)
