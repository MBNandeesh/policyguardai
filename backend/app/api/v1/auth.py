"""Officer auth API: login, session check, logout (client discards token).

Bearer-protected helper `require_officer` is used by decision endpoints so
officer actions are attributed to a real logged-in officer.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.auth import service as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    officer_id: str
    password: str


class LoginResponse(BaseModel):
    token: str
    officer_id: str
    name: str
    role: str
    expires_at: str


def require_officer(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """FastAPI dependency: validates 'Authorization: Bearer <token>'."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Login required")
    token = authorization.split(" ", 1)[1].strip()
    payload = auth_service.verify_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Session invalid or expired. Please log in again.")
    return {
        "officer_id": payload["officer_id"],
        "name": payload["name"],
        "role": payload["role"],
    }


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    officer_id = (payload.officer_id or "").strip()
    password = payload.password or ""
    if not officer_id or not password:
        raise HTTPException(status_code=422, detail="officer_id and password are required")
    session = auth_service.authenticate(officer_id, password)
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid officer ID or password")
    return session


@router.get("/me")
def me(officer: Dict[str, Any] = Depends(require_officer)):
    return officer


@router.post("/logout")
def logout(officer: Dict[str, Any] = Depends(require_officer)):
    # Tokens are stateless; the client discards it. Endpoint confirms identity.
    return {"status": "logged_out", "officer_id": officer["officer_id"]}


@router.get("/officers")
def officers():
    """List officer accounts (no credentials returned) — for the login screen dropdown."""
    return auth_service.list_officers()
