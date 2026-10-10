from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Sequence
from sqlalchemy.orm import Session

try:
    from db.models import EventRecord, TrackRecord, VideoRecord
    from search.embeddings import VisualEmbeddingEngine
    from search.query_parser import HARD_FILTER_ATTRS, NLQueryParser, ParsedQuery
except ModuleNotFoundError:
    from backend.db.models import EventRecord, TrackRecord, VideoRecord
    from backend.search.embeddings import VisualEmbeddingEngine
    from backend.search.query_parser import HARD_FILTER_ATTRS, NLQueryParser, ParsedQuery

# Event types that are high-priority alerts — boosted heavily
HIGH_PRIORITY_EVENTS = {"GUARD_ABSENT", "SUSPICIOUS_ENTRY_UNGUARDED", "ZONE_INTRUSION", "LOITERING"}
# HARD_FILTER_ATTRS is imported from query_parser (single source of truth).


@dataclass
class SearchResult:
    event_id: str
    video_id: str
    video_filename: str
    track_id: int
    class_name: str
    event_type: str
    start_time_sec: float
    end_time_sec: float
    confidence: float
    details: str
    score: float
    similarity: float = 0.0
    clip_url: str | None = None
    video_url: str | None = None
    video_width: int = 1920
    video_height: int = 1080
    visual_attributes: list[str] = field(default_factory=list)
    trajectory: list[dict] = field(default_factory=list)
    # Attributes that directly matched the user's query (used for UI chips)
    matched_attrs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "video_id": self.video_id,
            "video_filename": self.video_filename,
            "track_id": self.track_id,
            "class_name": self.class_name,
            "event_type": self.event_type,
            "start_time_sec": round(self.start_time_sec, 2),
            "end_time_sec": round(self.end_time_sec, 2),
            "duration_sec": round(max(0.0, self.end_time_sec - self.start_time_sec), 2),
            "confidence": round(self.confidence, 4),
            "details": self.details,
            "score": round(self.score, 4),
            "similarity": round(self.similarity, 4),
            "clip_url": self.clip_url,
            "video_url": self.video_url or f"/api/v1/videos/{self.video_id}/stream",
            "video_width": self.video_width,
            "video_height": self.video_height,
            "visual_attributes": self.visual_attributes,
            "matched_attrs": self.matched_attrs,
            "trajectory": self.trajectory,
        }


class HybridRetriever:
    """
    Combines:
    - Relational SQL filters (class, event type, time range, zone)
    - Absolute wall-clock time filtering (e.g. "after 9 PM")
    - Clothing-color attribute matching (e.g. "black_shirt")
    - Visual embedding cosine similarity
    to produce ranked CCTV video evidence.
    """

    def __init__(
        self,
        parser: NLQueryParser | None = None,
        embedder: VisualEmbeddingEngine | None = None,
    ) -> None:
        self.parser = parser or NLQueryParser()
        self.embedder = embedder or VisualEmbeddingEngine()

    def search(self, db: Session, query_text: str, video_id: str | None = None) -> list[SearchResult]:
        parsed = self.parser.parse(query_text)
        query_vector = self.embedder.embed_text(query_text)

        db_query = (
            db.query(EventRecord, VideoRecord)
            .join(VideoRecord, EventRecord.video_id == VideoRecord.id)
        )
        if video_id:
            db_query = db_query.filter(EventRecord.video_id == video_id)

        # ── Relational Filters ────────────────────────────────────────────────
        if parsed.target_classes:
            db_query = db_query.filter(EventRecord.class_name.in_(parsed.target_classes))

        if parsed.event_types:
            allowed_events = list(parsed.event_types)
            if parsed.target_classes or parsed.visual_attributes or parsed.clothing_colors or parsed.movement_tags:
                if "OBJECT_TRACKED" not in allowed_events:
                    allowed_events.append("OBJECT_TRACKED")
            db_query = db_query.filter(EventRecord.event_type.in_(allowed_events))

        # Relative time (seconds from video start)
        if parsed.time_start_sec is not None:
            db_query = db_query.filter(EventRecord.end_time_sec >= parsed.time_start_sec)
        if parsed.time_end_sec is not None:
            db_query = db_query.filter(EventRecord.start_time_sec <= parsed.time_end_sec)

        records = db_query.all()

        # ── Cache track embeddings, trajectories, visual attrs ────────────────
        track_ids = [event.track_id for event, _ in records]
        video_ids = list({event.video_id for event, _ in records})
        track_embeddings: dict[tuple[str, int], list[float]] = {}
        track_trajectories: dict[tuple[str, int], list[dict]] = {}
        track_visual_attrs: dict[tuple[str, int], list[str]] = {}

        if track_ids and video_ids:
            tracks = (
                db.query(TrackRecord)
                .filter(TrackRecord.video_id.in_(video_ids), TrackRecord.track_id.in_(track_ids))
                .all()
            )
            for tr in tracks:
                key = (tr.video_id, tr.track_id)
                if tr.embedding_json:
                    try:
                        track_embeddings[key] = json.loads(tr.embedding_json)
                    except Exception:
                        pass
                if tr.trajectory_json:
                    try:
                        track_trajectories[key] = json.loads(tr.trajectory_json)
                    except Exception:
                        pass
                if tr.visual_attributes_json:
                    try:
                        track_visual_attrs[key] = json.loads(tr.visual_attributes_json)
                    except Exception:
                        pass

        results: list[SearchResult] = []

        for event, video in records:
            duration = max(0.0, event.end_time_sec - event.start_time_sec)
            traj = track_trajectories.get((video.id, event.track_id), [])

            # ── Duration filter ───────────────────────────────────────────────
            if parsed.min_duration is not None and duration < parsed.min_duration:
                continue

            # ── Absolute wall-clock time filter ───────────────────────────────
            # The video has a recorded timestamp — filter by seconds-of-day using
            # video.processed_at as the reference anchor time.
            if parsed.abs_time_start_sec is not None or parsed.abs_time_end_sec is not None:
                anchor_secs = 0.0
                if video.processed_at:
                    t = video.processed_at
                    anchor_secs = float(t.hour * 3600 + t.minute * 60 + t.second)

                event_wall_start = (anchor_secs + event.start_time_sec) % 86400
                event_wall_end = (anchor_secs + event.end_time_sec) % 86400

                if parsed.abs_time_start_sec is not None:
                    if event_wall_end < parsed.abs_time_start_sec % 86400:
                        continue
                if parsed.abs_time_end_sec is not None:
                    if event_wall_start > parsed.abs_time_end_sec % 86400:
                        continue

            # ── Base score ────────────────────────────────────────────────────
            score = 1.0

            # High-priority alert events get a major boost ONLY when alerts are queried
            if event.event_type in HIGH_PRIORITY_EVENTS:
                if parsed.event_types and set(parsed.event_types).intersection(HIGH_PRIORITY_EVENTS):
                    score += 1.8
                elif not parsed.target_classes and not parsed.movement_tags and not parsed.visual_attributes:
                    score += 0.5

            if parsed.target_classes and event.class_name in parsed.target_classes:
                score += 1.0
            if parsed.event_types and event.event_type in parsed.event_types:
                score += 1.2
            if parsed.zone_name and event.zone_name == parsed.zone_name:
                score += 1.0
            if (parsed.movement_tags or parsed.target_classes) and event.event_type == "OBJECT_TRACKED":
                score += 0.8

            # ── Semantic cosine similarity ────────────────────────────────────
            candidate_vec = None
            if event.embedding_json:
                try:
                    candidate_vec = json.loads(event.embedding_json)
                except Exception:
                    pass
            if candidate_vec is None:
                candidate_vec = track_embeddings.get((video.id, event.track_id))

            similarity = 0.0
            if candidate_vec and query_vector:
                similarity = self.embedder.cosine_similarity(query_vector, candidate_vec)
                score += max(0.0, similarity) * 2.0

            # ── Visual attribute matching ─────────────────────────────────────
            event_attrs: list[str] = []
            if getattr(event, "visual_attributes_json", None):
                try:
                    event_attrs = json.loads(event.visual_attributes_json)
                except Exception:
                    event_attrs = []
            if not event_attrs:
                event_attrs = track_visual_attrs.get((video.id, event.track_id), [])

            matched_attrs_set: set[str] = set()

            # ── Carried-item tags (holding_phone / holding_bag / wearing_backpack) ─────
            # Soft fallback: boost if tag matches; if tag is missing but visual similarity or class matches, keep candidate!
            if parsed.visual_attributes:
                queried_hard = HARD_FILTER_ATTRS.intersection(parsed.visual_attributes)
                if queried_hard:
                    if queried_hard.issubset(event_attrs):
                        score += 2.0
                        matched_attrs_set.update(queried_hard)
                    elif similarity > 0.18 or (parsed.target_classes and event.class_name in parsed.target_classes):
                        # Candidate visual embedding or class matches — give soft boost instead of dropping
                        score += 0.5
                    else:
                        continue

            # ── Soft scoring: plain color / non-hard attributes ──────────────
            if parsed.visual_attributes:
                plain_soft = set(parsed.visual_attributes) - HARD_FILTER_ATTRS
                plain_matched = plain_soft.intersection(event_attrs)
                if plain_matched:
                    score += 0.7 + (0.15 * len(plain_matched))
                    matched_attrs_set.update(plain_matched)
                elif plain_soft and event_attrs and not parsed.clothing_colors and similarity < 0.15:
                    # Neither tags nor visual similarity matched
                    continue

            # Match clothing-color tags ("black_shirt", "blue_pants")
            if parsed.clothing_colors:
                clothing_matched = set(parsed.clothing_colors).intersection(event_attrs)
                if clothing_matched:
                    score += 1.2 + (0.25 * len(clothing_matched))
                    matched_attrs_set.update(clothing_matched)
                elif event_attrs and similarity < 0.15:
                    # Candidate has visual attributes, but neither tags nor visual embedding matched
                    continue

            # ── Group / count filter ─────────────────────────────────────────────────────────
            # "two persons" → HARD filter: skip tracks that were never near a companion
            if parsed.min_group_size is not None:
                has_group_tag = (
                    "moving_with_others" in event_attrs
                    or any(f"in_group_of_{n}" in event_attrs
                           for n in range(parsed.min_group_size, 7))
                )
                if not has_group_tag:
                    continue
                # Extra boost for exact group size match
                exact_tag = f"in_group_of_{parsed.min_group_size}"
                if exact_tag in event_attrs:
                    score += 2.0
                elif "moving_with_others" in event_attrs:
                    score += 1.0

            # ── Movement direction scoring ───────────────────────────────────────────────────
            # "going toward stair" / "toward exit" → boost tracks matching direction tags or trajectory
            if parsed.movement_tags:
                matched_dirs = set(parsed.movement_tags).intersection(event_attrs)
                if matched_dirs:
                    score += 1.5 * len(matched_dirs)  # big boost per matched direction
                elif traj and len(traj) >= 2:
                    p_start = traj[0]
                    p_end = traj[-1]
                    dx = p_end.get("x", 0) - p_start.get("x", 0)
                    dy = p_end.get("y", 0) - p_start.get("y", 0)
                    end_y = p_end.get("y", 0)
                    # toward_exit: track moves downward/rightward or ends in lower retail checkout area
                    if "toward_exit" in parsed.movement_tags and (dy > 25 or end_y > 450 or "going_down" in event_attrs or "going_right" in event_attrs):
                        score += 1.5
                    elif "going_down" in parsed.movement_tags and dy > 20:
                        score += 1.2
                    elif "going_up" in parsed.movement_tags and dy < -20:
                        score += 1.2
                    elif "going_right" in parsed.movement_tags and dx > 20:
                        score += 1.2
                    elif "going_left" in parsed.movement_tags and dx < -20:
                        score += 1.2
                # Stationary tracks are penalised when motion is queried
                if "stationary" in event_attrs and parsed.movement_tags:
                    score -= 0.8

            # ── Keyword text matching ─────────────────────────────────────────
            searchable_text = " ".join(
                str(part or "").lower()
                for part in [
                    event.details,
                    event.event_type,
                    event.class_name,
                    event.zone_name,
                    video.filename,
                    " ".join(event_attrs),
                ]
            )
            for keyword in parsed.keywords:
                if keyword in searchable_text:
                    score += 0.08

            # ── Build clip URL only if clip actually exists on disk ───────────
            clip_url: str | None = None
            if event.clip_path:
                from pathlib import Path as _Path
                clip_file = _Path(event.clip_path)
                if clip_file.is_file() and clip_file.stat().st_size > 1024:
                    clip_url = f"/api/v1/videos/{video.id}/clips/{event.id}"

            video_stream_url = f"/api/v1/videos/{video.id}/stream"
            traj = track_trajectories.get((video.id, event.track_id), [])

            results.append(
                SearchResult(
                    event_id=event.id,
                    video_id=video.id,
                    video_filename=video.filename,
                    track_id=event.track_id,
                    class_name=event.class_name,
                    event_type=event.event_type,
                    start_time_sec=event.start_time_sec,
                    end_time_sec=event.end_time_sec,
                    confidence=event.confidence,
                    details=event.details or "",
                    score=score,
                    similarity=similarity,
                    clip_url=clip_url,
                    video_url=video_stream_url,
                    video_width=video.width or 1920,
                    video_height=video.height or 1080,
                    visual_attributes=event_attrs,
                    trajectory=traj,
                    matched_attrs=sorted(matched_attrs_set),
                )
            )

        # Return top 25 results — enough for investigation without flooding the canvas
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:25]
