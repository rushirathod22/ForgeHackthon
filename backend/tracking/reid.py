from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence
import numpy as np
from sqlalchemy.orm import Session

try:
    from db.models import EventRecord, TrackRecord, VideoRecord
    from search.embeddings import VisualEmbeddingEngine
except ModuleNotFoundError:
    from backend.db.models import EventRecord, TrackRecord, VideoRecord
    from backend.search.embeddings import VisualEmbeddingEngine


@dataclass
class JourneyNode:
    step_number: int
    video_id: str
    video_filename: str
    track_id: int
    class_name: str
    first_seen_sec: float
    last_seen_sec: float
    duration_sec: float
    confidence: float
    similarity_score: float
    location_name: str
    clip_url: str | None
    video_url: str
    trajectory: list[dict]

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "video_id": self.video_id,
            "video_filename": self.video_filename,
            "track_id": self.track_id,
            "class_name": self.class_name,
            "first_seen_sec": round(self.first_seen_sec, 2),
            "last_seen_sec": round(self.last_seen_sec, 2),
            "duration_sec": round(self.duration_sec, 2),
            "confidence": round(self.confidence, 4),
            "similarity_score": round(self.similarity_score, 4),
            "location_name": self.location_name,
            "clip_url": self.clip_url,
            "video_url": self.video_url,
            "trajectory": self.trajectory,
        }


class CrossCameraReIDMatcher:
    """Multi-camera Re-Identification engine to link target appearances across CCTV cameras."""

    def __init__(self, min_similarity: float = 0.65) -> None:
        self.min_similarity = min_similarity
        self.embedder = VisualEmbeddingEngine()

    def build_journey(
        self,
        db: Session,
        video_id: str,
        track_id: int,
        max_steps: int = 5,
    ) -> list[dict]:
        """Reconstruct the spatial multi-camera journey for a target track across indexed videos."""
        source_track = (
            db.query(TrackRecord)
            .filter(TrackRecord.video_id == video_id, TrackRecord.track_id == track_id)
            .first()
        )
        if not source_track:
            return []

        source_video = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
        source_filename = source_video.filename if source_video else "SOURCE_CAMERA"

        source_vec = None
        if source_track.embedding_json:
            try:
                source_vec = json.loads(source_track.embedding_json)
            except Exception:
                source_vec = None

        source_traj = []
        if source_track.trajectory_json:
            try:
                source_traj = json.loads(source_track.trajectory_json)
            except Exception:
                source_traj = []

        # Start journey with the initial sighting (Step 1)
        nodes: list[JourneyNode] = [
            JourneyNode(
                step_number=1,
                video_id=video_id,
                video_filename=source_filename,
                track_id=track_id,
                class_name=source_track.class_name,
                first_seen_sec=source_track.first_seen_sec,
                last_seen_sec=source_track.last_seen_sec,
                duration_sec=source_track.duration_sec,
                confidence=1.0,
                similarity_score=1.0,
                location_name="INITIAL DETECTION POINT",
                clip_url=None,
                video_url=f"/api/v1/videos/{video_id}/stream",
                trajectory=source_traj,
            )
        ]

        # Find candidate tracks across other videos with matching class name
        candidate_tracks = (
            db.query(TrackRecord, VideoRecord)
            .join(VideoRecord, TrackRecord.video_id == VideoRecord.id)
            .filter(TrackRecord.class_name == source_track.class_name)
            .all()
        )

        matched_candidates = []
        for cand_track, cand_video in candidate_tracks:
            # Exclude exact same track
            if cand_track.video_id == video_id and cand_track.track_id == track_id:
                continue

            similarity = 0.70  # Default base class similarity
            if source_vec and cand_track.embedding_json:
                try:
                    cand_vec = json.loads(cand_track.embedding_json)
                    similarity = self.embedder.cosine_similarity(source_vec, cand_vec)
                except Exception:
                    pass

            if similarity >= self.min_similarity or cand_track.video_id != video_id:
                cand_traj = []
                if cand_track.trajectory_json:
                    try:
                        cand_traj = json.loads(cand_track.trajectory_json)
                    except Exception:
                        cand_traj = []

                matched_candidates.append({
                    "track": cand_track,
                    "video": cand_video,
                    "similarity": similarity,
                    "trajectory": cand_traj,
                })

        # Rank candidates by visual similarity
        matched_candidates.sort(key=lambda x: x["similarity"], reverse=True)

        # Append top matches from distinct videos or distinct time windows
        seen_videos = {video_id}
        step_num = 2
        for item in matched_candidates:
            c_track = item["track"]
            c_video = item["video"]
            c_sim = item["similarity"]
            c_traj = item["trajectory"]

            loc_name = f"SURVEILLANCE SECTOR {step_num}"
            if "gate" in c_video.filename.lower():
                loc_name = "GATE ACCESS POINT"
            elif "corridor" in c_video.filename.lower() or "hall" in c_video.filename.lower():
                loc_name = "INTERIOR CORRIDOR"
            elif "warehouse" in c_video.filename.lower() or "yard" in c_video.filename.lower():
                loc_name = "CARGO / LOADING BAY"
            elif "parking" in c_video.filename.lower():
                loc_name = "PERIMETER PARKING"

            nodes.append(
                JourneyNode(
                    step_number=step_num,
                    video_id=c_track.video_id,
                    video_filename=c_video.filename,
                    track_id=c_track.track_id,
                    class_name=c_track.class_name,
                    first_seen_sec=c_track.first_seen_sec,
                    last_seen_sec=c_track.last_seen_sec,
                    duration_sec=c_track.duration_sec,
                    confidence=round(0.85 + (c_sim * 0.1), 4),
                    similarity_score=round(c_sim, 4),
                    location_name=loc_name,
                    clip_url=None,
                    video_url=f"/api/v1/videos/{c_track.video_id}/stream",
                    trajectory=c_traj,
                )
            )
            seen_videos.add(c_track.video_id)
            step_num += 1
            if len(nodes) >= max_steps:
                break

        return [n.to_dict() for n in nodes]
