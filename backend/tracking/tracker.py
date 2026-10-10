from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


def compute_iou(boxA: list[float], boxB: list[float]) -> float:
    """Compute Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
    boxAArea = max(0.0, boxA[2] - boxA[0]) * max(0.0, boxA[3] - boxA[1])
    boxBArea = max(0.0, boxB[2] - boxB[0]) * max(0.0, boxB[3] - boxB[1])

    unionArea = boxAArea + boxBArea - interArea
    if unionArea <= 0.0:
        return 0.0
    return interArea / unionArea


@dataclass
class TrajectoryPoint:
    x: float
    y: float
    w: float = 0.0
    h: float = 0.0
    timestamp_sec: float = 0.0


@dataclass
class TrackedObject:
    track_id: int
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2]
    first_seen_sec: float
    last_seen_sec: float
    trajectory: list[TrajectoryPoint] = field(default_factory=list)
    velocity: tuple[float, float] = (0.0, 0.0)  # (vx, vy) in px/sec
    hits: int = 1
    lost_count: int = 0
    is_active: bool = True
    embedding: list[float] | None = None
    best_crop_bgr: np.ndarray | None = None
    visual_attributes: list[str] = field(default_factory=list)
    # Pose keypoints: list of (x, y) for each detected YOLO-pose keypoint.
    # Index 9 = left wrist, index 10 = right wrist (COCO ordering).
    wrist_keypoints: list[tuple[float, float]] = field(default_factory=list)

    @property
    def center(self) -> tuple[float, float]:
        return (
            (self.bbox[0] + self.bbox[2]) / 2.0,
            (self.bbox[1] + self.bbox[3]) / 2.0,
        )

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.last_seen_sec - self.first_seen_sec)

    @property
    def total_distance_px(self) -> float:
        if len(self.trajectory) < 2:
            return 0.0
        total = 0.0
        for i in range(1, len(self.trajectory)):
            p1 = self.trajectory[i - 1]
            p2 = self.trajectory[i]
            total += math.hypot(p2.x - p1.x, p2.y - p1.y)
        return round(total, 2)

    @property
    def average_speed_px_sec(self) -> float:
        dur = self.duration_sec
        if dur <= 0:
            return 0.0
        return round(self.total_distance_px / dur, 2)

    def update(
        self,
        bbox: list[float],
        confidence: float,
        timestamp_sec: float,
        fps: float = 30.0,
        crop_bgr: np.ndarray | None = None,
        keypoints: list[tuple[float, float]] | None = None,
    ) -> None:
        prev_center = self.center
        self.bbox = bbox
        if crop_bgr is not None and (self.best_crop_bgr is None or confidence >= self.confidence):
            self.best_crop_bgr = crop_bgr
        self.confidence = confidence
        self.last_seen_sec = timestamp_sec
        self.hits += 1
        self.lost_count = 0
        # Keep the most recent wrist keypoints for pose-based proximity checks
        if keypoints:
            self.wrist_keypoints = keypoints
        new_center = self.center
        box_w = round(abs(self.bbox[2] - self.bbox[0]), 2)
        box_h = round(abs(self.bbox[3] - self.bbox[1]), 2)

        self.trajectory.append(
            TrajectoryPoint(
                x=round(new_center[0], 2),
                y=round(new_center[1], 2),
                w=box_w,
                h=box_h,
                timestamp_sec=round(timestamp_sec, 3),
            )
        )

        dt = timestamp_sec - (self.trajectory[-2].timestamp_sec if len(self.trajectory) > 1 else timestamp_sec - (1.0 / fps))
        if dt > 0:
            vx = (new_center[0] - prev_center[0]) / dt
            vy = (new_center[1] - prev_center[1]) / dt
            self.velocity = (round(vx, 2), round(vy, 2))


@dataclass
class DetectionInput:
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]
    crop_bgr: np.ndarray | None = None
    # YOLO-Pose keypoints as list of (x, y) tuples (COCO 17-point skeleton).
    # Index 9 = left_wrist, index 10 = right_wrist.
    keypoints: list[tuple[float, float]] | None = None


class CCTVTracker:
    """IoU-based multi-object tracker for persistent object tracking in CCTV streams."""

    def __init__(
        self,
        iou_threshold: float = 0.30,
        max_lost_frames: int = 15,
        min_hits: int = 1,
    ) -> None:
        self.iou_threshold = iou_threshold
        self.max_lost_frames = max_lost_frames
        self.min_hits = min_hits
        self.next_track_id = 1
        self.tracks: list[TrackedObject] = []

    def update(
        self,
        detections: Sequence[DetectionInput],
        timestamp_sec: float,
        fps: float = 30.0,
    ) -> list[TrackedObject]:
        """Update tracker state with new frame detections and return active tracks for the frame."""
        # 1. Match active tracks with incoming detections using IoU matrix
        active_tracks = [t for t in self.tracks if t.is_active]
        unmatched_detections = list(range(len(detections)))
        unmatched_tracks = list(range(len(active_tracks)))
        matches: list[tuple[int, int]] = []

        if active_tracks and detections:
            # Build IoU matrix (len(active_tracks) x len(detections))
            iou_matrix = []
            for track in active_tracks:
                row = []
                for det in detections:
                    # Match class or allow match if class is same
                    if track.class_id == det.class_id:
                        row.append(compute_iou(track.bbox, det.bbox))
                    else:
                        row.append(0.0)
                iou_matrix.append(row)

            # Greedy matching for highest IoU above threshold
            candidates = []
            for t_idx, row in enumerate(iou_matrix):
                for d_idx, iou_val in enumerate(row):
                    if iou_val >= self.iou_threshold:
                        candidates.append((iou_val, t_idx, d_idx))
            
            candidates.sort(key=lambda x: x[0], reverse=True)

            assigned_tracks = set()
            assigned_dets = set()
            for iou_val, t_idx, d_idx in candidates:
                if t_idx not in assigned_tracks and d_idx not in assigned_dets:
                    matches.append((t_idx, d_idx))
                    assigned_tracks.add(t_idx)
                    assigned_dets.add(d_idx)

            unmatched_tracks = [t for t in range(len(active_tracks)) if t not in assigned_tracks]
            unmatched_detections = [d for d in range(len(detections)) if d not in assigned_dets]

        # 2. Update matched tracks
        for t_idx, d_idx in matches:
            track = active_tracks[t_idx]
            det = detections[d_idx]
            track.update(
                det.bbox, det.confidence, timestamp_sec, fps,
                crop_bgr=det.crop_bgr, keypoints=det.keypoints,
            )

        # 3. Mark lost count for unmatched tracks
        for t_idx in unmatched_tracks:
            track = active_tracks[t_idx]
            track.lost_count += 1
            if track.lost_count > self.max_lost_frames:
                track.is_active = False

        # 4. Create new tracks for unmatched detections
        for d_idx in unmatched_detections:
            det = detections[d_idx]
            new_track = TrackedObject(
                track_id=self.next_track_id,
                class_id=det.class_id,
                class_name=det.class_name,
                confidence=det.confidence,
                bbox=det.bbox,
                first_seen_sec=timestamp_sec,
                last_seen_sec=timestamp_sec,
                best_crop_bgr=det.crop_bgr,
                wrist_keypoints=list(det.keypoints) if det.keypoints else [],
            )
            center = new_track.center
            box_w = round(abs(det.bbox[2] - det.bbox[0]), 2)
            box_h = round(abs(det.bbox[3] - det.bbox[1]), 2)
            new_track.trajectory.append(
                TrajectoryPoint(
                    x=round(center[0], 2),
                    y=round(center[1], 2),
                    w=box_w,
                    h=box_h,
                    timestamp_sec=round(timestamp_sec, 3),
                )
            )
            self.tracks.append(new_track)
            self.next_track_id += 1

        # Return currently active matched & recently active tracks with hits >= min_hits
        frame_tracks = [
            t for t in self.tracks
            if t.is_active and t.lost_count == 0 and t.hits >= self.min_hits
        ]
        return frame_tracks

    def get_all_tracks_summary(self) -> list[dict]:
        """Return structured summary of all tracks recorded during processing."""
        summary = []
        for t in self.tracks:
            summary.append({
                "track_id": t.track_id,
                "class_id": t.class_id,
                "class_name": t.class_name,
                "confidence": t.confidence,
                "first_seen_sec": round(t.first_seen_sec, 2),
                "last_seen_sec": round(t.last_seen_sec, 2),
                "duration_sec": t.duration_sec,
                "total_distance_px": t.total_distance_px,
                "average_speed_px_sec": t.average_speed_px_sec,
                "trajectory_length": len(t.trajectory),
                "embedding": t.embedding,
                "visual_attributes": t.visual_attributes,
                "trajectory": [
                    {"x": p.x, "y": p.y, "w": p.w, "h": p.h, "t": p.timestamp_sec}
                    for p in t.trajectory
                ],
            })
        return summary
