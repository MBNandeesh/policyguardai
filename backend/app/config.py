import os
import shutil

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    database_url: str | None = None
    vector_db_url: str | None = None
    ai_provider: str | None = None
    ai_api_key: str | None = None
    storage_path: str = "./storage"
    app_env: str = "development"
    # Comma-separated list of allowed CORS origins. "*" allows any origin (fine for demos).
    cors_origins: str = "*"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    tesseract_cmd: str | None = None
    tesseract_lang: str = "eng"
    ocr_psm: int = 6
    ocr_oem: int = 3


settings = Settings()

discovered = os.getenv("TESSERACT_CMD") or settings.tesseract_cmd or shutil.which("tesseract")
if not discovered:
    default_locations = [
        os.path.join(os.getenv("ProgramFiles", r"C:\Program Files"), "Tesseract-OCR", "tesseract.exe"),
        os.path.join(os.getenv("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Tesseract-OCR", "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in default_locations:
        if os.path.exists(candidate):
            discovered = candidate
            break

if discovered:
    settings.tesseract_cmd = discovered
    os.environ["TESSERACT_CMD"] = discovered
