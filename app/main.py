from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database.connection import Base, engine
from app.models import clinic_model  # noqa: F401 - ensures models are registered
from app.api.routes import (
    clinic_routes,
    email_routes,
    prompt_routes,
    dashboard_routes,
)

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Clinic Outreach API",
    version="1.0.0",
    description="Backend API for managing US clinic outreach campaigns",
)

# CORS — allow Angular dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Clinic Outreach API is running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


# Register routers under /api/v1 prefix
API_PREFIX = "/api/v1"
app.include_router(clinic_routes.router, prefix=API_PREFIX)
app.include_router(email_routes.router, prefix=API_PREFIX)
app.include_router(prompt_routes.router, prefix=API_PREFIX)
app.include_router(dashboard_routes.router, prefix=API_PREFIX)
