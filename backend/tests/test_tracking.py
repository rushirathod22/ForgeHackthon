from __future__ import annotations

import pytest
try:
    from tracking.tracker import (
        CCTVTracker,
        DetectionInput,
        TrackedObject,
        compute_iou,
    )
except ModuleNotFoundError:
    from backend.tracking.tracker import (
        CCTVTracker,
        DetectionInput,
        TrackedObject,
        compute_iou,
    )


def test_compute_iou_exact() -> None:
    boxA = [0.0, 0.0, 100.0, 100.0]
    boxB = [50.0, 0.0, 150.0, 100.0]
    assert round(compute_iou(boxA, boxB), 4) == 0.3333

    boxC = [200.0, 200.0, 300.0, 300.0]
    assert compute_iou(boxA, boxC) == 0.0


def test_tracker_single_object_moving() -> None:
    tracker = CCTVTracker(iou_threshold=0.3)
    
    det0 = [DetectionInput(class_id=2, class_name="car", confidence=0.9, bbox=[10.0, 10.0, 50.0, 50.0])]
    tracks0 = tracker.update(det0, timestamp_sec=0.0)
    assert len(tracks0) == 1
    assert tracks0[0].track_id == 1
    assert tracks0[0].hits == 1

    det1 = [DetectionInput(class_id=2, class_name="car", confidence=0.92, bbox=[20.0, 10.0, 60.0, 50.0])]
    tracks1 = tracker.update(det1, timestamp_sec=1.0)
    assert len(tracks1) == 1
    assert tracks1[0].track_id == 1
    assert tracks1[0].hits == 2
    assert len(tracks1[0].trajectory) == 2
    assert tracks1[0].total_distance_px == 10.0
    assert tracks1[0].average_speed_px_sec == 10.0


def test_tracker_multiple_objects() -> None:
    tracker = CCTVTracker(iou_threshold=0.3)

    dets = [
        DetectionInput(class_id=2, class_name="car", confidence=0.88, bbox=[10.0, 10.0, 40.0, 40.0]),
        DetectionInput(class_id=2, class_name="car", confidence=0.91, bbox=[200.0, 200.0, 250.0, 250.0]),
    ]
    tracks = tracker.update(dets, timestamp_sec=0.0)
    assert len(tracks) == 2
    track_ids = {t.track_id for t in tracks}
    assert track_ids == {1, 2}


def test_tracker_occlusion_and_lost() -> None:
    tracker = CCTVTracker(iou_threshold=0.3, max_lost_frames=2)

    det0 = [DetectionInput(class_id=7, class_name="truck", confidence=0.95, bbox=[50.0, 50.0, 150.0, 150.0])]
    tracker.update(det0, timestamp_sec=0.0)

    tracks1 = tracker.update([], timestamp_sec=0.1)
    assert len(tracks1) == 0

    tracks2 = tracker.update([], timestamp_sec=0.2)
    assert len(tracks2) == 0

    tracker.update([], timestamp_sec=0.3)
    assert tracker.tracks[0].is_active is False


def test_tracker_summary_serialization() -> None:
    tracker = CCTVTracker()
    det = [DetectionInput(class_id=2, class_name="car", confidence=0.9, bbox=[10.0, 10.0, 50.0, 50.0])]
    tracker.update(det, timestamp_sec=0.0)

    summary = tracker.get_all_tracks_summary()
    assert len(summary) == 1
    assert summary[0]["track_id"] == 1
    assert summary[0]["class_name"] == "car"
    assert "trajectory" in summary[0]
