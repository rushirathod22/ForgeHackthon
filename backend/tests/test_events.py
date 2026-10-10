from __future__ import annotations

from pathlib import Path
import cv2
import numpy as np
import pytest

try:
    from events.clip_exporter import ClipExporter
    from events.detector import CCTVEvent, EventDetector, ZoneROI
    from tracking.tracker import TrackedObject, TrajectoryPoint
except ModuleNotFoundError:
    from backend.events.clip_exporter import ClipExporter
    from backend.events.detector import CCTVEvent, EventDetector, ZoneROI
    from backend.tracking.tracker import TrackedObject, TrajectoryPoint


def test_zone_roi_contains_point() -> None:
    # Square ROI from (0,0) to (100,100)
    zone = ZoneROI(name="MainGate", polygon=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])
    assert zone.contains_point(50.0, 50.0) is True
    assert zone.contains_point(150.0, 50.0) is False


def test_event_detector_fast_movement() -> None:
    detector = EventDetector(speed_threshold_px_sec=50.0)
    
    # Track moving fast: 100px in 1 second = 100 px/sec
    track = TrackedObject(
        track_id=10,
        class_id=2,
        class_name="car",
        confidence=0.95,
        bbox=[100.0, 100.0, 150.0, 150.0],
        first_seen_sec=0.0,
        last_seen_sec=1.0,
        trajectory=[
            TrajectoryPoint(0.0, 0.0, 0.0),
            TrajectoryPoint(100.0, 0.0, 1.0),
        ],
    )

    events = detector.evaluate_tracks([track])
    assert len(events) == 1
    assert events[0].event_type == "FAST_MOVEMENT"
    assert events[0].track_id == 10


def test_event_detector_zone_intrusion_and_loitering() -> None:
    zone = ZoneROI(name="RestrictedArea", polygon=[(0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)])
    detector = EventDetector(zones=[zone], loitering_threshold_sec=2.0)

    track = TrackedObject(
        track_id=22,
        class_id=0,
        class_name="person",
        confidence=0.9,
        bbox=[50.0, 50.0, 80.0, 120.0],
        first_seen_sec=0.0,
        last_seen_sec=3.0,
        trajectory=[
            TrajectoryPoint(50.0, 50.0, 0.0),
            TrajectoryPoint(55.0, 55.0, 3.0),
        ],
    )

    events = detector.evaluate_tracks([track])
    event_types = {e.event_type for e in events}
    assert "ZONE_INTRUSION" in event_types
    assert "LOITERING" in event_types


def test_clip_exporter_synthetic(tmp_path: Path) -> None:
    video_path = tmp_path / "source.mp4"
    clip_path = tmp_path / "clip_out.mp4"

    # Create 3-second synthetic video at 10 fps
    width, height, fps = 160, 120, 10
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    for _ in range(30):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        writer.write(frame)
    writer.release()

    exporter = ClipExporter(padding_sec=0.5)
    extracted = exporter.extract_clip(video_path, start_time_sec=1.0, end_time_sec=2.0, output_clip_path=clip_path)

    assert extracted.is_file()
    assert extracted.stat().st_size > 0
