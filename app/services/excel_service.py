import pandas as pd
from io import BytesIO
from sqlalchemy.orm import Session
from app.models.clinic_model import Clinic


# Accepted column aliases (flexible for real-world Excel files)
COLUMN_ALIASES = {
    "clinic_name": ["clinic_name", "name", "clinic", "business_name", "practice_name"],
    "email": ["email", "email_address", "contact_email"],
    "phone": ["phone", "phone_number", "contact_phone", "tel"],
    "website": ["website", "url", "site", "web"],
    "city": ["city", "town"],
    "state": ["state", "region", "province"],
    "clinic_type": ["clinic_type", "type", "specialty", "category"],
    "notes": ["notes", "comment", "comments", "description"],
}


def _resolve_column(df_columns, field: str):
    """Find which actual column name matches our field."""
    normalized = {c.lower().strip().replace(" ", "_"): c for c in df_columns}
    for alias in COLUMN_ALIASES.get(field, []):
        if alias in normalized:
            return normalized[alias]
    return None


def parse_excel_to_clinics(file_bytes: bytes, db: Session) -> dict:
    """Parse Excel and insert clinics into DB. Returns counts."""
    try:
        df = pd.read_excel(BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Failed to read Excel file: {str(e)}")

    if df.empty:
        return {"inserted": 0, "skipped": 0, "total": 0, "message": "File is empty"}

    # Map columns
    col_map = {}
    for field in COLUMN_ALIASES.keys():
        resolved = _resolve_column(df.columns, field)
        if resolved:
            col_map[field] = resolved

    if "clinic_name" not in col_map:
        raise ValueError(
            "Excel must contain a 'clinic_name' column (or alias: name, clinic, business_name)"
        )

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        name_val = row.get(col_map["clinic_name"])
        if pd.isna(name_val) or not str(name_val).strip():
            skipped += 1
            continue

        def _get(field):
            col = col_map.get(field)
            if not col:
                return None
            val = row.get(col)
            if pd.isna(val):
                return None
            return str(val).strip()

        clinic = Clinic(
            clinic_name=str(name_val).strip(),
            email=_get("email"),
            phone=_get("phone"),
            website=_get("website"),
            city=_get("city"),
            state=_get("state"),
            clinic_type=_get("clinic_type"),
            notes=_get("notes"),
        )
        db.add(clinic)
        inserted += 1

    db.commit()

    return {
        "inserted": inserted,
        "skipped": skipped,
        "total": len(df),
        "message": f"Imported {inserted} clinics, skipped {skipped} rows",
    }
