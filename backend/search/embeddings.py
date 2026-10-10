from __future__ import annotations

import math
from typing import Sequence
import cv2
import numpy as np
import torch
from PIL import Image

try:
    from transformers import CLIPModel, CLIPProcessor
    _CLIP_AVAILABLE = True
except Exception:
    _CLIP_AVAILABLE = False


class VisualEmbeddingEngine:
    """Multimodal visual-semantic embedding engine using Hugging Face CLIP.
    
    Generates normalized 512-dimensional dense feature vectors (||v||_2 = 1.0)
    enabling real-time cosine similarity search for CCTV video tracks and
    open-vocabulary natural language queries (e.g. "red top person", "blue jacket").
    """

    _shared_model = None
    _shared_processor = None
    _shared_device = None

    def __init__(self, embedding_dim: int = 512, model_id: str = "openai/clip-vit-base-patch32") -> None:
        self.dim = embedding_dim
        self.model_id = model_id
        self._device = None
        self._model = None
        self._processor = None

    def _ensure_loaded(self) -> bool:
        """Lazily load the CLIP model and processor on first use."""
        if not _CLIP_AVAILABLE:
            return False

        if VisualEmbeddingEngine._shared_model is not None:
            self._model = VisualEmbeddingEngine._shared_model
            self._processor = VisualEmbeddingEngine._shared_processor
            self._device = VisualEmbeddingEngine._shared_device
            return True

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            processor = CLIPProcessor.from_pretrained(self.model_id)
            model = CLIPModel.from_pretrained(self.model_id).to(device)
            model.eval()

            VisualEmbeddingEngine._shared_device = device
            VisualEmbeddingEngine._shared_processor = processor
            VisualEmbeddingEngine._shared_model = model

            self._device = device
            self._processor = processor
            self._model = model
            return True
        except Exception as err:
            print(f"[VisualEmbeddingEngine] Warning: Could not load Hugging Face CLIP model: {err}")
            return False

    # Color definitions for hybrid color-semantic alignment
    _COLOR_RANGES = {
        "red": [(0, 10), (170, 180)],
        "orange": [(11, 25)],
        "yellow": [(26, 35)],
        "green": [(36, 85)],
        "cyan": [(86, 100)],
        "blue": [(101, 130)],
        "purple": [(131, 155)],
    }

    def _extract_tensor(self, out) -> torch.Tensor:
        if hasattr(out, "pooler_output") and out.pooler_output is not None:
            feat = out.pooler_output
        elif hasattr(out, "last_hidden_state") and out.last_hidden_state is not None:
            feat = out.last_hidden_state[:, 0, :]
        elif isinstance(out, (tuple, list)):
            feat = out[0]
        else:
            feat = out

        if self.dim != feat.shape[-1]:
            feat = torch.nn.functional.adaptive_avg_pool1d(feat.unsqueeze(1), self.dim).squeeze(1)

        feat = feat / feat.norm(p=2, dim=-1, keepdim=True)
        return feat

    def _get_dominant_color_name(self, crop_bgr: np.ndarray) -> str | None:
        """Helper to find dominant color from HSV."""
        crop_hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        s_ch = crop_hsv[:, :, 1]
        v_ch = crop_hsv[:, :, 2]
        mean_v = float(np.mean(v_ch))
        mean_s = float(np.mean(s_ch))

        if mean_v < 45:
            return "black"
        if mean_v > 200 and mean_s < 55:
            return "white"
        if mean_s < 45:
            return "gray"

        hist_h = cv2.calcHist([crop_hsv], [0], None, [18], [0, 180]).flatten()
        peak_hue = int(np.argmax(hist_h) * 10)
        for cname, ranges in self._COLOR_RANGES.items():
            if any(r_min <= peak_hue <= r_max for r_min, r_max in ranges):
                return cname
        return None

    def embed_image(self, crop_bgr: np.ndarray | None) -> list[float]:
        """Compute a normalized visual embedding vector from a BGR image crop."""
        if crop_bgr is None or crop_bgr.size == 0:
            return [0.0] * self.dim

        h, w = crop_bgr.shape[:2]
        if h < 2 or w < 2:
            return [0.0] * self.dim

        if self._ensure_loaded() and self._model is not None and self._processor is not None:
            try:
                crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(crop_rgb)
                inputs = self._processor(images=pil_img, return_tensors="pt").to(self._device)
                with torch.no_grad():
                    out = self._model.get_image_features(**inputs)
                    feat = self._extract_tensor(out)
                    vec = feat[0].cpu().numpy()

                norm = float(np.linalg.norm(vec))
                if norm > 1e-6:
                    vec = vec / norm
                return [round(float(x), 5) for x in vec]
            except Exception as err:
                print(f"[VisualEmbeddingEngine] Image embedding error: {err}")

        # Fallback pseudo-vector if model fails
        return [0.0] * self.dim

    def embed_text(self, text: str) -> list[float]:
        """Compute a normalized semantic embedding vector from a text query."""
        if not text:
            return [0.0] * self.dim

        if self._ensure_loaded() and self._model is not None and self._processor is not None:
            try:
                inputs = self._processor(
                    text=[text],
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                ).to(self._device)
                with torch.no_grad():
                    out = self._model.get_text_features(**inputs)
                    feat = self._extract_tensor(out)
                    vec = feat[0].cpu().numpy()

                norm = float(np.linalg.norm(vec))
                if norm > 1e-6:
                    vec = vec / norm
                return [round(float(x), 5) for x in vec]
            except Exception as err:
                print(f"[VisualEmbeddingEngine] Text embedding error: {err}")

        # Fallback deterministic vector
        hash_val = abs(hash(text)) % 1000000
        np.random.seed(hash_val)
        fallback = np.random.randn(self.dim).astype(np.float32)
        norm = np.linalg.norm(fallback)
        return [round(float(x / norm), 5) for x in fallback]

    @staticmethod
    def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        """Compute cosine similarity between two float vectors, adapting dimensions if needed."""
        if not vec_a or not vec_b:
            return 0.0

        if len(vec_a) != len(vec_b):
            target_len = min(len(vec_a), len(vec_b))
            if target_len < 2:
                return 0.0
            if len(vec_a) != target_len:
                ta = torch.tensor(vec_a, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
                vec_a = torch.nn.functional.adaptive_avg_pool1d(ta, target_len).squeeze().tolist()
            if len(vec_b) != target_len:
                tb = torch.tensor(vec_b, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
                vec_b = torch.nn.functional.adaptive_avg_pool1d(tb, target_len).squeeze().tolist()

        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))
