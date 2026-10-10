"""
GeminiVisionTagger
==================
Uses Google Gemini Vision (gemini-1.5-flash) to extract structured visual
attributes from CCTV person-crop images.

The tagger replaces / augments the simple HSV colour analysis with a proper
multimodal understanding: shirt colour, pants colour, accessories, actions.

Output format
-------------
Returns a list of normalised tags compatible with the existing retriever
query-parser vocabulary, e.g.:
    ['red_shirt', 'black_pants', 'holding_phone', 'wearing_backpack']

Usage
-----
    from detection.gemini_tagger import GeminiVisionTagger

    tagger = GeminiVisionTagger(api_key="AIza...")
    tags = tagger.tag(crop_bgr)          # synchronous, thread-safe

Design
------
- Encodes each crop as base64 JPEG (≤200 KB) before sending.
- Uses a strict JSON prompt so the model returns parseable output.
- Falls back to [] on any network / parse error — caller always gets HSV tags.
- Optional in-memory LRU-style cache keyed on a fast perceptual hash so the
  same crop (same track best-frame) is never sent twice per session.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from typing import Optional

import cv2
import numpy as np

# ── Gemini SDK import (optional — graceful fallback if not installed) ─────────
try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────────────────
# Prompt sent to Gemini for each person crop
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a CCTV forensic attribute extractor. Given a cropped image of a person
from a surveillance camera, output ONLY a valid JSON object with these fields:

{
  "shirt_color": "<color or null>",
  "pants_color": "<color or null>",
  "jacket_color": "<color or null>",
  "hair_accessory": "<pink_bow / ribbon / hat / cap / null>",
  "holding_phone": true/false,
  "holding_bag": true/false,
  "wearing_backpack": true/false,
  "gender_guess": "male"/"female"/"unknown",
  "approximate_age": "child"/"teenager"/"adult"/"elderly"/"unknown"
}

Rules:
- Use only these colour names: black, white, gray, red, blue, green, yellow,
  orange, purple, pink, brown, silver, cyan. Use null if unclear.
- hair_accessory should identify hair clips, bows (e.g. "pink_bow"), ribbons, or headwear.
- holding_phone is true ONLY if the person is visibly holding or using a phone.
- holding_bag is true ONLY if holding a handbag, clutch, or shopping bag.
- wearing_backpack is true if they have a backpack on their back.
- Output ONLY the JSON — no explanation, no markdown fences.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Normalise Gemini output → retriever-compatible tag list
# ─────────────────────────────────────────────────────────────────────────────
def _json_to_tags(data: dict) -> list[str]:
    tags: list[str] = []

    def _add_color(value: str | None, suffix: str) -> None:
        if value and isinstance(value, str):
            c = value.strip().lower()
            if c not in ("null", "none", "unknown", ""):
                tags.append(c)                   # plain: "red"
                tags.append(f"{c}_{suffix}")     # tagged: "red_shirt"

    _add_color(data.get("shirt_color"), "shirt")
    _add_color(data.get("pants_color"), "pants")
    _add_color(data.get("jacket_color"), "jacket")

    hair_acc = data.get("hair_accessory")
    if hair_acc and isinstance(hair_acc, str):
        acc_str = hair_acc.strip().lower().replace(" ", "_")
        if acc_str not in ("null", "none", "unknown", ""):
            tags.append(acc_str)
            tags.append("wearing_bow") if "bow" in acc_str else None

    if data.get("holding_phone"):
        tags.append("holding_phone")
    if data.get("holding_bag"):
        tags.append("holding_bag")
    if data.get("wearing_backpack"):
        tags.append("wearing_backpack")
    if data.get("wearing_helmet"):
        tags.append("wearing_helmet")

    age = data.get("approximate_age", "")
    if age in ("child", "teenager", "elderly"):
        tags.append(age)

    return list(dict.fromkeys(tags))  # deduplicate, preserve order


# ─────────────────────────────────────────────────────────────────────────────
class GeminiVisionTagger:
    """
    Thread-safe Gemini Vision attribute tagger with in-memory crop cache.

    Parameters
    ----------
    api_key : str | None
        Gemini API key. Falls back to the GEMINI_API_KEY env variable.
        If neither is set, all calls return [] immediately.
    model   : str
        Gemini model name (default: gemini-1.5-flash for speed & cost).
    max_size_bytes : int
        Maximum JPEG bytes to send per crop (crops are scaled-down first).
    cache_size : int
        Number of tag-lists to cache in memory (keyed by crop SHA-256).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        max_size_bytes: int = 180_000,
        cache_size: int = 512,
    ) -> None:
        self._key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._model_name = model
        self._max_size = max_size_bytes
        self._cache: dict[str, list[str]] = {}
        self._cache_size = cache_size
        self._lock = threading.Lock()
        self._client = None  # lazy-initialised
        self._fallback_models = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
        self._rate_limited_until = 0.0

        if self._key and _GENAI_AVAILABLE:
            genai.configure(api_key=self._key)
            self._client = genai.GenerativeModel(model)

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """True if Gemini SDK is installed and a key is configured."""
        return bool(self._client)

    def tag(self, crop_bgr: np.ndarray | None) -> list[str]:
        """
        Synchronously extract attribute tags from a BGR person crop.
        Returns [] on failure (caller should fall back to HSV tags).
        """
        if not self.is_available or crop_bgr is None or crop_bgr.size == 0:
            return []

        if time.time() < self._rate_limited_until:
            return []

        jpeg_bytes = self._encode(crop_bgr)
        if not jpeg_bytes:
            return []

        cache_key = hashlib.sha256(jpeg_bytes).hexdigest()
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        tags: list[str] = []
        image_part = {
            "mime_type": "image/jpeg",
            "data": base64.b64encode(jpeg_bytes).decode(),
        }

        # Try active model, fallback to alternative models if needed
        models_to_try = [self._model_name] + [m for m in self._fallback_models if m != self._model_name]
        
        for candidate_model in models_to_try:
            try:
                client = genai.GenerativeModel(candidate_model)
                response = client.generate_content(
                    [_SYSTEM_PROMPT, image_part],
                    generation_config={"temperature": 0.1, "max_output_tokens": 256},
                    request_options={"timeout": 30},
                )
                raw = response.text.strip()
                # Strip accidental markdown fences
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]
                data = json.loads(raw)
                tags = _json_to_tags(data)
                # If successful, remember this working model
                self._client = client
                self._model_name = candidate_model
                break
            except Exception as err:
                err_str = str(err)
                if "429" in err_str or "quota" in err_str.lower():
                    self._rate_limited_until = time.time() + 60.0
                    print("[GeminiVisionTagger] Rate limit reached (Gemini Free Tier). Seamlessly falling back to local HSV analysis for 60s.")
                    break
                print(f"[GeminiVisionTagger] Model {candidate_model} warning: {err}")
                continue

        with self._lock:
            if len(self._cache) >= self._cache_size:
                # Evict oldest entry (Python 3.7+ dicts preserve insertion order)
                self._cache.pop(next(iter(self._cache)))
            self._cache[cache_key] = tags

        return tags

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _encode(self, crop_bgr: np.ndarray) -> bytes | None:
        """Encode crop as JPEG, scaling down if it exceeds max_size_bytes."""
        quality = 85
        for _ in range(4):
            ok, buf = cv2.imencode(".jpg", crop_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok:
                return None
            data = buf.tobytes()
            if len(data) <= self._max_size:
                return data
            # Scale down by 50% and retry
            h, w = crop_bgr.shape[:2]
            crop_bgr = cv2.resize(crop_bgr, (max(1, w // 2), max(1, h // 2)))
            quality = max(50, quality - 10)
        return None
