from fastapi import FastAPI
from app.api.v1.health import router as health_router
from app.api.v1.documents import router as documents_router
from app.api.v1.regulatory import router as regulatory_router
from app.api.v1.compliance import router as compliance_router
from app.logging_config import setup_logging
from app.config import settings
from app.regulatory.service import seed_default_fixtures

setup_logging()

app = FastAPI(title="PolicyGuard AI - Backend", version="0.1.0")

app.include_router(health_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(regulatory_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")

seed_default_fixtures()


@app.get("/")
def root():
    return {"message": "PolicyGuard AI backend. See /api/v1/health"}
