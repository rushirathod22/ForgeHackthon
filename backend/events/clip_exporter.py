from __future__ import annotations

import os
from pathlib import Path
import cv2


class ClipExporter:
    """Extracts timestamped video clips from a source video file."""

    def __init__(self, padding_sec: float = 1.0) -> None:
        self.padding_sec = padding_sec

    def extract_clip(
        self,
        source_video_path: Path,
        start_time_sec: float,
        end_time_sec: float,
        output_clip_path: Path,
    ) -> Path:
        """Extract a clip between start_time_sec and end_time_sec from source video."""
        if not source_video_path.is_file():
            raise FileNotFoundError(f"Source video not found: '{source_video_path}'")

        capture = cv2.VideoCapture(str(source_video_path))
        if not capture.isOpened():
            raise RuntimeError(f"Could not open source video: '{source_video_path}'")

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        start_padded = max(0.0, start_time_sec - self.padding_sec)
        end_padded = end_time_sec + self.padding_sec

        start_frame = int(start_padded * fps)
        end_frame = min(total_frames, int(end_padded * fps)) if total_frames > 0 else int(end_padded * fps)

        output_clip_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_clip_path.with_name(f"{output_clip_path.stem}.part{output_clip_path.suffix}")

        writer = cv2.VideoWriter(
            str(temp_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )

        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        current_frame = start_frame

        try:
            while current_frame <= end_frame:
                success, frame = capture.read()
                if not success:
                    break
                writer.write(frame)
                current_frame += 1
        finally:
            capture.release()
            writer.release()

        if temp_path.is_file() and temp_path.stat().st_size > 0:
            os.replace(temp_path, output_clip_path)
        else:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to generate evidence clip at '{output_clip_path}'")

        return output_clip_path
