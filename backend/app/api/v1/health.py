from fastapi import APIRouter
from datetime import datetime

router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "policyguard-backend",
        "time": datetime.utcnow().isoformat() + "Z",
    }
