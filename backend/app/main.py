from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.api.v1.documents import router as documents_router
from app.api.v1.regulatory import router as regulatory_router
from app.api.v1.retrieval import router as retrieval_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.verification import router as verification_router
from app.api.v1.audit import router as audit_router
from app.api.v1.review import router as review_router
from app.config import settings
from app.logging_config import setup_logging

setup_logging()

app = FastAPI(title="PolicyGuard AI - Backend", version="0.2.0")

# Allow the frontend (hosted separately) to call this API from browsers.
_origins = [o.strip() for o in (settings.cors_origins or "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(regulatory_router, prefix="/api/v1")
app.include_router(retrieval_router, prefix="/api/v1")
app.include_router(compliance_router, prefix="/api/v1")
app.include_router(verification_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(review_router, prefix="/api/v1")