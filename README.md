# PolicyGuard AI — Phase 0 scaffold

This repository contains a Phase 0 scaffold for PolicyGuard AI.

Supported Python version

- Python 3.12.x is the supported runtime for backend development. Many PDF/OCR and ML dependencies require a 3.12-compatible environment.

Quick start (backend):

```bash
# Install Python 3.12 and ensure the `py` launcher or `python3.12` is available.
python -m pip install -r backend/requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Virtual environment helpers

- Windows PowerShell helper: `backend/setup_venv.ps1` (uses `py -3.12` to create `backend/.venv` and install requirements).
- POSIX helper: `backend/setup_venv.sh` (uses `python3.12` or `py -3.12` to create `backend/.venv`).

Run the appropriate helper after installing Python 3.12 to create the venv and install dependencies.

Frontend (requires Node.js):

```bash
cd frontend
npm install
npm run dev
```

Run backend tests:

```bash
pytest -q
```
