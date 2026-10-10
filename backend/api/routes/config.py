from __future__ import annotations

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from detection.gemini_tagger import GeminiVisionTagger
except ImportError:
    from backend.detection.gemini_tagger import GeminiVisionTagger

router = APIRouter(prefix="/api/v1/config", tags=["config"])

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class GeminiKeyRequest(BaseModel):
    api_key: str


def _mask_key(key: str) -> str:
    if not key or len(key) < 8:
        return ""
    return f"{key[:4]}...{key[-4:]}"


def _save_env_key(key: str) -> None:
    lines = []
    found = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                lines.append(f"GEMINI_API_KEY={key}")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"GEMINI_API_KEY={key}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


@router.get("/gemini")
def get_gemini_config():
    """Return whether Gemini Vision is configured and available."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return {
        "configured": bool(key),
        "masked_key": _mask_key(key),
        "model": "gemini-3.6-flash",
    }


@router.post("/gemini")
def set_gemini_config(req: GeminiKeyRequest):
    """Save or update the Gemini API key in memory and .env file."""
    key = req.api_key.strip()
    if not key:
        # Clear key
        os.environ.pop("GEMINI_API_KEY", None)
        _save_env_key("")
        return {"configured": False, "masked_key": "", "message": "Gemini API key removed."}

    # Verify key format or basic validity
    try:
        tagger = GeminiVisionTagger(api_key=key)
        if not tagger.is_available:
            raise HTTPException(status_code=400, detail="Gemini SDK could not initialise with this key.")
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"Invalid Gemini API key: {err}")

    os.environ["GEMINI_API_KEY"] = key
    _save_env_key(key)

    return {
        "configured": True,
        "masked_key": _mask_key(key),
        "message": "Gemini API key saved! Visual attribute tagging is active.",
    }
