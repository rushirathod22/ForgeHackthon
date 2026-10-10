"""
RetailS Shoplifting Action Classifier Trainer
Trains a lightweight Temporal Pose GRU on RetailS 17-keypoint sequences.
Uses BCEWithLogitsLoss for numerical stability + balanced Train/Val Split.
Output: backend/shoplifting_model.pt
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset, random_split

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent
ZIP_PATH = ROOT_DIR / "RetailS.zip"
OUTPUT_MODEL_PATH = BACKEND_DIR / "shoplifting_model.pt"

WINDOW_SIZE = 30    # 30 frames (~1.0 - 1.2 sec of movement)
NUM_KEYPOINTS = 17  # COCO 17 keypoints
INPUT_DIM = 17 * 3  # (x, y, confidence) = 51 Cols


# -- Model Definition ---------------------------------------------------------
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
        last_step = out[:, -1, :]
        logits = self.fc(last_step).squeeze(-1)
        return logits


# -- Balanced Dataset Parser --------------------------------------------------
class BalancedRetailSDataset(Dataset):
    def __init__(self, zip_path: Path, max_per_class: int = 1500):
        pos_samples = []
        neg_samples = []

        print(f"Reading RetailS ground-truth masks from {zip_path.name}...")
        with zipfile.ZipFile(zip_path, "r") as z:
            labeled_subsets = [
                ("RetailS/RetailS_test_staged/pose/test/", "RetailS/RetailS_test_staged/gt/test_frame_mask/"),
                ("RetailS/RetailS_test_realworld/pose/test/", "RetailS/RetailS_test_realworld/gt/test_frame_mask/"),
            ]

            for json_dir, gt_dir in labeled_subsets:
                json_files = [f for f in z.namelist() if f.startswith(json_dir) and f.endswith(".json")]

                for jf in json_files:
                    stem = Path(jf).stem
                    npy_path = f"{gt_dir}{stem}.npy"
                    if npy_path not in z.namelist():
                        continue

                    try:
                        mask = np.load(io.BytesIO(z.read(npy_path)))
                        data = json.loads(z.read(jf).decode("utf-8"))

                        for track_id, frames_dict in data.items():
                            fkeys = sorted(frames_dict.keys(), key=lambda k: int(k))
                            seq = []
                            for fk in fkeys:
                                kps = frames_dict[fk].get("keypoints", [])
                                if len(kps) == 51:
                                    seq.append(np.array(kps, dtype=np.float32))

                            if len(seq) >= WINDOW_SIZE:
                                for s in range(0, len(seq) - WINDOW_SIZE, 6):
                                    window = seq[s : s + WINDOW_SIZE]
                                    w_mask = mask[s : s + WINDOW_SIZE]
                                    if len(w_mask) == WINDOW_SIZE:
                                        theft_ratio = float(np.mean(w_mask))
                                        win_arr = np.array(window, dtype=np.float32)

                                        # Normalize coordinates relative to person root (hips: 11 & 12)
                                        root_x = (win_arr[:, 11*3] + win_arr[:, 12*3]) / 2.0
                                        root_y = (win_arr[:, 11*3 + 1] + win_arr[:, 12*3 + 1]) / 2.0
                                        for i in range(17):
                                            win_arr[:, i*3] = (win_arr[:, i*3] - root_x) / 500.0
                                            win_arr[:, i*3 + 1] = (win_arr[:, i*3 + 1] - root_y) / 500.0

                                        # Replace any NaN with 0.0
                                        win_arr = np.nan_to_num(win_arr, nan=0.0, posinf=1.0, neginf=-1.0)

                                        if theft_ratio > 0.35 and len(pos_samples) < max_per_class:
                                            pos_samples.append(win_arr)
                                        elif theft_ratio == 0.0 and len(neg_samples) < max_per_class:
                                            neg_samples.append(win_arr)
                    except Exception:
                        continue

                    if len(pos_samples) >= max_per_class and len(neg_samples) >= max_per_class:
                        break

        # Balance classes equally
        min_count = min(len(pos_samples), len(neg_samples))
        print(f"Extracted {min_count} Theft (positive) and {min_count} Normal (negative) windows.")

        self.samples = pos_samples[:min_count] + neg_samples[:min_count]
        self.labels = [1.0] * min_count + [0.0] * min_count

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return torch.tensor(self.samples[idx]), torch.tensor(self.labels[idx], dtype=torch.float32)


# -- Training & Evaluation Loop -----------------------------------------------
def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using compute device: {device}")

    full_dataset = BalancedRetailSDataset(ZIP_PATH, max_per_class=1200)
    if len(full_dataset) == 0:
        print("Error: Could not extract balanced samples. Check zip structure.")
        return

    # 80% Train, 20% Validation split
    val_size = int(len(full_dataset) * 0.20)
    train_size = len(full_dataset) - val_size
    train_set, val_set = random_split(full_dataset, [train_size, val_size])

    train_loader = DataLoader(train_set, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=32, shuffle=False)

    print(f"Dataset split: {train_size} training samples, {val_size} validation samples.")

    model = ShopliftingActionGRU(input_dim=INPUT_DIM, hidden_dim=64, num_layers=2).to(device)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=1e-4)

    print("\nStarting Training & Validation...")
    best_val_loss = float("inf")

    for epoch in range(1, 11):
        # 1. Train Phase
        model.train()
        train_loss = 0.0
        train_correct = 0
        total_train = 0

        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()

            train_loss += loss.item() * len(y)
            preds = torch.sigmoid(logits)
            train_correct += ((preds > 0.5).float() == y).sum().item()
            total_train += len(y)

        train_acc = (train_correct / total_train) * 100 if total_train > 0 else 0
        avg_train_loss = train_loss / total_train if total_train > 0 else 0

        # 2. Validation Phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        total_val = 0

        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                loss = criterion(logits, y)
                val_loss += loss.item() * len(y)
                preds = torch.sigmoid(logits)
                val_correct += ((preds > 0.5).float() == y).sum().item()
                total_val += len(y)

        val_acc = (val_correct / total_val) * 100 if total_val > 0 else 0
        avg_val_loss = val_loss / total_val if total_val > 0 else 0

        marker = ""
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            torch.save(model.state_dict(), OUTPUT_MODEL_PATH)
            marker = "  [Best Weights Saved]"

        print(
            f"Epoch [{epoch:02d}/10] "
            f"Train Loss: {avg_train_loss:.4f} | Train Acc: {train_acc:.1f}% || "
            f"Val Loss: {avg_val_loss:.4f} | Val Acc: {val_acc:.1f}%{marker}"
        )

    print(f"\n[Success] Best trained shoplifting model saved to: {OUTPUT_MODEL_PATH}")


if __name__ == "__main__":
    train()
