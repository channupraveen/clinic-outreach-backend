from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
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
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/clinics", tags=["Clinics"])


# ---- Bulk import schema ----
class BulkImportItem(BaseModel):
    clinic_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    clinic_type: Optional[str] = None

class BulkImportRequest(BaseModel):
    clinics: List[BulkImportItem]

class BulkImportResponse(BaseModel):
    imported: int
    skipped: int
    updated: int
    total: int
    message: str


def normalize_name(name: str) -> str:
    """Normalize clinic name for comparison."""
    return ' '.join(name.lower().strip().split())


def normalize_phone(phone: str) -> str:
    """Strip non-digit chars for phone comparison."""
    if not phone:
        return ''
    return ''.join(c for c in phone if c.isdigit())[-10:]  # last 10 digits


def normalize_website(url: str) -> str:
    """Normalize website URL for comparison."""
    if not url:
        return ''
    url = url.lower().strip().rstrip('/')
    for prefix in ['https://www.', 'http://www.', 'https://', 'http://']:
        if url.startswith(prefix):
            url = url[len(prefix):]
            break
    # Remove query params and trailing slashes
    url = url.split('?')[0].split('#')[0].rstrip('/')
    return url


def find_duplicate(db: Session, clinic_data: dict) -> Optional[Clinic]:
    """
    Check if a clinic already exists by matching:
    1. Exact website domain match (strongest signal)
    2. Same phone number (last 10 digits)
    3. Same name + same city (fuzzy)
    """
    name = clinic_data.get('clinic_name', '')
    phone = clinic_data.get('phone', '')
    website = clinic_data.get('website', '')
    city = clinic_data.get('city', '')

    # 1. Website match — strongest dedup signal
    if website:
        norm_web = normalize_website(website)
        if norm_web:
            all_clinics = db.query(Clinic).filter(Clinic.website.isnot(None), Clinic.website != '').all()
            for c in all_clinics:
                if normalize_website(c.website or '') == norm_web:
                    return c

    # 2. Phone match (last 10 digits)
    if phone:
        norm_phone = normalize_phone(phone)
        if len(norm_phone) >= 7:  # at least 7 digits to match
            all_clinics = db.query(Clinic).filter(Clinic.phone.isnot(None), Clinic.phone != '').all()
            for c in all_clinics:
                if normalize_phone(c.phone or '') == norm_phone:
                    return c

    # 3. Name + City match
    if name and city:
        norm_name = normalize_name(name)
        norm_city = city.lower().strip()
        all_clinics = db.query(Clinic).filter(
            Clinic.city.isnot(None)
        ).all()
        for c in all_clinics:
            if (normalize_name(c.clinic_name) == norm_name and
                    (c.city or '').lower().strip() == norm_city):
                return c

    return None


# ---- Static paths FIRST ----

@router.get("", response_model=List[ClinicOut])
def list_clinics(db: Session = Depends(get_db)):
    return db.query(Clinic).order_by(Clinic.created_at.desc()).all()


@router.post("", response_model=ClinicOut, status_code=201)
def create_clinic(payload: ClinicCreate, db: Session = Depends(get_db)):
    # Check for duplicate
    existing = find_duplicate(db, payload.model_dump())
    if existing:
        # Update empty fields on existing record instead of creating duplicate
        updated = False
        if payload.email and not existing.email:
            existing.email = payload.email
            updated = True
        if payload.phone and not existing.phone:
            existing.phone = payload.phone
            updated = True
        if payload.website and not existing.website:
            existing.website = payload.website
            updated = True
        if payload.clinic_type and not existing.clinic_type:
            existing.clinic_type = payload.clinic_type
            updated = True
        if updated:
            db.commit()
            db.refresh(existing)
        return existing

    clinic = Clinic(**payload.model_dump())
    db.add(clinic)
    db.commit()
    db.refresh(clinic)
    return clinic


@router.post("/bulk-import", response_model=BulkImportResponse)
def bulk_import_clinics(payload: BulkImportRequest, db: Session = Depends(get_db)):
    """
    Import multiple clinics at once with smart dedup.
    - Skips exact duplicates
    - Updates existing records if new data fills empty fields (e.g., email found later)
    """
    imported = 0
    skipped = 0
    updated = 0

    for item in payload.clinics:
        data = item.model_dump()

        # Skip if no name
        if not data.get('clinic_name', '').strip():
            skipped += 1
            continue

        existing = find_duplicate(db, data)

        if existing:
            # Merge: fill in any empty fields on existing record
            did_update = False
            if data.get('email') and not existing.email:
                existing.email = data['email']
                did_update = True
            if data.get('phone') and not existing.phone:
                existing.phone = data['phone']
                did_update = True
            if data.get('website') and not existing.website:
                existing.website = data['website']
                did_update = True
            if data.get('city') and not existing.city:
                existing.city = data['city']
                did_update = True
            if data.get('state') and not existing.state:
                existing.state = data['state']
                did_update = True
            if data.get('clinic_type') and not existing.clinic_type:
                existing.clinic_type = data['clinic_type']
                did_update = True

            if did_update:
                updated += 1
            else:
                skipped += 1
        else:
            clinic = Clinic(**data)
            db.add(clinic)
            imported += 1

    db.commit()

    total = imported + skipped + updated
    message = f"Done! {imported} new, {updated} updated, {skipped} skipped."
    return BulkImportResponse(
        imported=imported,
        skipped=skipped,
        updated=updated,
        total=total,
        message=message,
    )


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
