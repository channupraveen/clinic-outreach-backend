from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List

from app.database.connection import get_db
from app.models.clinic_model import Clinic, ClinicIssue
from app.schemas.clinic_schema import (
    ClinicOut,
    ClinicCreate,
    ClinicUpdate,
    UploadResponse,
    ClinicIssueCreate,
    ClinicIssueOut,
)
from app.services.excel_service import parse_excel_to_clinics

router = APIRouter(prefix="/clinics", tags=["Clinics"])


# ---- Static paths FIRST (before /{clinic_id} param) ----

@router.get("", response_model=List[ClinicOut])
def list_clinics(db: Session = Depends(get_db)):
    return db.query(Clinic).order_by(Clinic.created_at.desc()).all()


@router.post("", response_model=ClinicOut, status_code=201)
def create_clinic(payload: ClinicCreate, db: Session = Depends(get_db)):
    clinic = Clinic(**payload.model_dump())
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.post("/upload-excel", response_model=UploadResponse)
async def upload_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only .xlsx and .xls files are supported")

    contents = await file.read()
    try:
        result = parse_excel_to_clinics(contents, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

    return result


@router.get("/issues/all", response_model=List[ClinicIssueOut])
def list_all_issues(db: Session = Depends(get_db)):
    return db.query(ClinicIssue).order_by(ClinicIssue.created_at.desc()).all()


@router.delete("/issues/{issue_id}", status_code=204)
def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(ClinicIssue).filter(ClinicIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    db.delete(issue)
    db.commit()
    return None


# ---- Parameterized paths ----

@router.get("/{clinic_id}", response_model=ClinicOut)
def get_clinic(clinic_id: int, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return clinic


@router.put("/{clinic_id}", response_model=ClinicOut)
def update_clinic(clinic_id: int, payload: ClinicUpdate, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(clinic, key, value)

    db.commit()
    db.refresh(clinic)
    return clinic


@router.delete("/{clinic_id}", status_code=204)
def delete_clinic(clinic_id: int, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    db.delete(clinic)
    db.commit()
    return None


@router.get("/{clinic_id}/issues", response_model=List[ClinicIssueOut])
def list_clinic_issues(clinic_id: int, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    return db.query(ClinicIssue).filter(ClinicIssue.clinic_id == clinic_id).order_by(ClinicIssue.created_at.desc()).all()


@router.post("/{clinic_id}/issues", response_model=ClinicIssueOut, status_code=201)
def create_clinic_issue(clinic_id: int, payload: ClinicIssueCreate, db: Session = Depends(get_db)):
    clinic = db.query(Clinic).filter(Clinic.id == clinic_id).first()
    if not clinic:
        raise HTTPException(status_code=404, detail="Clinic not found")
    issue = ClinicIssue(clinic_id=clinic_id, issue_type=payload.issue_type, priority_score=payload.priority_score or 0.0)
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue
