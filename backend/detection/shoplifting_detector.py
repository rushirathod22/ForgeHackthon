from __future__ import annotations

from pathlib import Path
import numpy as np
import torch
import torch.nn as nn

BACKEND_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BACKEND_DIR / "shoplifting_model.pt"


class ShopliftingActionGRU(nn.Module):
    def __init__(self, input_dim: int = 51, hidden_dim: int = 64, num_layers: int = 2):
        super().__init__()
        self.gru = nn.GRU(
            input_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2 if num_layers > 1 else 0.0,
            bidirectional=True
        )
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim * 2, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 1)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.gru(x)
        logits = self.fc(out[:, -1, :]).squeeze(-1)
        return logits


class ShopliftingDetector:
    """Evaluates 17-keypoint sequences extracted from yolo11n-pose to detect concealment/theft."""
    def __init__(self, threshold: float = 0.60):
        self.threshold = threshold
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None

        if MODEL_PATH.is_file():
            try:
                self.model = ShopliftingActionGRU().to(self.device)
                self.model.load_state_dict(torch.load(MODEL_PATH, map_location=self.device))
                self.model.eval()
                print(f"[ShopliftingDetector] Successfully loaded trained weights from {MODEL_PATH.name}")
            except Exception as e:
                print(f"[ShopliftingDetector] Warning: could not load model: {e}")

    @property
    def is_available(self) -> bool:
        return self.model is not None

    def evaluate_track(self, keypoints_history: list[list[float]]) -> tuple[bool, float]:
        """
        Takes list of 51-float keypoint vectors (length >= 30 frames).
        Returns (is_shoplifting: bool, confidence: float).
        """
        if not self.is_available or len(keypoints_history) < 30:
            return False, 0.0

        # Take last 30 frames and normalize relative to root (hips)
        win_arr = np.array(keypoints_history[-30:], dtype=np.float32)
        root_x = (win_arr[:, 11*3] + win_arr[:, 12*3]) / 2.0
        root_y = (win_arr[:, 11*3 + 1] + win_arr[:, 12*3 + 1]) / 2.0

        for i in range(17):
            win_arr[:, i*3] = (win_arr[:, i*3] - root_x) / 500.0
            win_arr[:, i*3 + 1] = (win_arr[:, i*3 + 1] - root_y) / 500.0

        win_arr = np.nan_to_num(win_arr, nan=0.0, posinf=1.0, neginf=-1.0)
        tensor = torch.tensor(win_arr).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(tensor)
            prob = float(torch.sigmoid(logits).item())

        return (prob >= self.threshold), round(prob, 3)
