from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    clinic_name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    website = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    clinic_type = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    issues = relationship("ClinicIssue", back_populates="clinic", cascade="all, delete-orphan")
    emails = relationship("EmailTemplate", back_populates="clinic", cascade="all, delete-orphan")


class ClinicIssue(Base):
    __tablename__ = "clinic_issues"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    issue_type = Column(String(100), nullable=False)
    priority_score = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="issues")


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id", ondelete="CASCADE"), nullable=False)
    service_type = Column(String(100), nullable=True)
    subject = Column(String(500), nullable=True)
    email_body = Column(Text, nullable=True)
    prompt_used = Column(Text, nullable=True)
    status = Column(String(50), default="draft")  # draft, sent, replied, followup
    sent_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="emails")
