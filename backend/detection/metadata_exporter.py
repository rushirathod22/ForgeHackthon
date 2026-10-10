from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class DetectionItem:
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2]
    track_id: int | None = None


@dataclass
class FrameMetadata:
    frame_index: int
    timestamp_sec: float
    detections: list[DetectionItem] = field(default_factory=list)


@dataclass
class VideoMetadata:
    video_name: str
    fps: float
    width: int
    height: int
    total_frames: int
    model_name: str
    confidence_threshold: float
    processed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class DetectionMetadataExporter:
    """Collects and serializes frame-by-frame detection & tracking metadata into structured JSON."""

    def __init__(self, meta: VideoMetadata, output_json_path: Path) -> None:
        self.meta = meta
        self.output_json_path = output_json_path
        self.frames: list[FrameMetadata] = []
        self.tracks_summary: list[dict] = []

    def add_frame_detections(
        self, frame_index: int, timestamp_sec: float, detections: list[DetectionItem]
    ) -> None:
        self.frames.append(
            FrameMetadata(
                frame_index=frame_index,
                timestamp_sec=timestamp_sec,
                detections=detections,
            )
        )

    def set_tracks_summary(self, tracks_summary: list[dict]) -> None:
        self.tracks_summary = tracks_summary

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_metadata": asdict(self.meta),
            "frames_processed": len(self.frames),
            "total_tracks": len(self.tracks_summary),
            "tracks": self.tracks_summary,
            "frames": [asdict(f) for f in self.frames],
        }

    def save(self) -> None:
        self.output_json_path.parent.mkdir(parents=True, exist_ok=True)
        temp_json_path = self.output_json_path.with_name(
            f"{self.output_json_path.stem}.part{self.output_json_path.suffix}"
        )
        data = self.to_dict()
        with open(temp_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_json_path, self.output_json_path)

