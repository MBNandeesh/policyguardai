from fastapi import APIRouter
from datetime import datetime, timezone

from app.config import settings

router = APIRouter()


def _ocr_status() -> dict:
    """Best-effort OCR runtime availability.

    The service stays healthy even when Tesseract is missing (text-layer PDFs
    need no OCR); the capability flag lets deployment checks and the README
    state the truth about scanned-PDF support in the current runtime.
    """
    import shutil

    cmd = settings.tesseract_cmd or shutil.which("tesseract")
    available = bool(cmd)
    return {"available": available, "engine": "tesseract" if available else None}


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "policyguard-backend",
        "time": datetime.now(timezone.utc).isoformat(),
        "ocr": _ocr_status(),
    }
