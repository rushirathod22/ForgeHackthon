from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Sequence

try:
    from tracking.tracker import TrackedObject
except ModuleNotFoundError:
    from backend.tracking.tracker import TrackedObject


@dataclass
class ZoneROI:
    name: str
    polygon: list[tuple[float, float]]  # List of (x, y) vertices defining the ROI

    def contains_point(self, x: float, y: float) -> bool:
        """Ray-casting point-in-polygon algorithm."""
        n = len(self.polygon)
        if n < 3:
            return False
        inside = False
        p1x, p1y = self.polygon[0]
        for i in range(n + 1):
            p2x, p2y = self.polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside


@dataclass
class CCTVEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "GENERIC_EVENT"
    track_id: int = 0
    class_name: str = "vehicle"
    start_time_sec: float = 0.0
    end_time_sec: float = 0.0
    confidence: float = 1.0
    zone_name: str | None = None
    details: str = ""
    clip_path: str | None = None

    @property
    def duration_sec(self) -> float:
        return max(0.0, round(self.end_time_sec - self.start_time_sec, 2))

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "track_id": self.track_id,
            "class_name": self.class_name,
            "start_time_sec": round(self.start_time_sec, 2),
            "end_time_sec": round(self.end_time_sec, 2),
            "duration_sec": self.duration_sec,
            "confidence": round(self.confidence, 4),
            "zone_name": self.zone_name,
            "details": self.details,
            "clip_path": self.clip_path,
        }


class EventDetector:
    """Evaluates tracked object trajectories for security and traffic events."""

    def __init__(
        self,
        zones: Sequence[ZoneROI] | None = None,
        speed_threshold_px_sec: float = 80.0,
        loitering_threshold_sec: float = 3.0,
        stopped_threshold_sec: float = 4.0,
    ) -> None:
        self.zones = list(zones) if zones else []
        self.speed_threshold_px_sec = speed_threshold_px_sec
        self.loitering_threshold_sec = loitering_threshold_sec
        self.stopped_threshold_sec = stopped_threshold_sec
        self.triggered_events: dict[str, CCTVEvent] = {}

    def evaluate_tracks(self, tracks: Sequence[TrackedObject]) -> list[CCTVEvent]:
        """Evaluate tracks and return all triggered events."""
        for track in tracks:
            if not track.trajectory:
                continue

            current_pos = track.center
            curr_x, curr_y = current_pos

            # 1. Fast Movement / Overspeeding Check
            speed = track.average_speed_px_sec
            if speed >= self.speed_threshold_px_sec:
                event_key = f"FAST_{track.track_id}"
                if event_key not in self.triggered_events:
                    event = CCTVEvent(
                        event_type="FAST_MOVEMENT",
                        track_id=track.track_id,
                        class_name=track.class_name,
                        start_time_sec=track.first_seen_sec,
                        end_time_sec=track.last_seen_sec,
                        confidence=track.confidence,
                        details=f"High speed detected: {speed:.1f} px/sec (threshold: {self.speed_threshold_px_sec})",
                    )
                    self.triggered_events[event_key] = event
                else:
                    self.triggered_events[event_key].end_time_sec = track.last_seen_sec

            # 2. Zone Intrusion & Zone Loitering Checks
            for zone in self.zones:
                if zone.contains_point(curr_x, curr_y):
                    # Intrusion Event
                    intrusion_key = f"INTRUSION_{zone.name}_{track.track_id}"
                    if intrusion_key not in self.triggered_events:
                        event = CCTVEvent(
                            event_type="ZONE_INTRUSION",
                            track_id=track.track_id,
                            class_name=track.class_name,
                            start_time_sec=track.first_seen_sec,
                            end_time_sec=track.last_seen_sec,
                            confidence=track.confidence,
                            zone_name=zone.name,
                            details=(
                                f"Track #{track.track_id} ({track.class_name}) "
                                f"entered zone '{zone.name}' at {round(track.first_seen_sec, 1)}s"
                            ),
                        )
                        self.triggered_events[intrusion_key] = event
                    else:
                        self.triggered_events[intrusion_key].end_time_sec = track.last_seen_sec

                    # Loitering Event
                    if track.duration_sec >= self.loitering_threshold_sec:
                        loitering_key = f"LOITERING_{zone.name}_{track.track_id}"
                        if loitering_key not in self.triggered_events:
                            event = CCTVEvent(
                                event_type="LOITERING",
                                track_id=track.track_id,
                                class_name=track.class_name,
                                start_time_sec=track.first_seen_sec,
                                end_time_sec=track.last_seen_sec,
                                confidence=track.confidence,
                                zone_name=zone.name,
                                details=(
                                    f"Track #{track.track_id} loitering in '{zone.name}' "
                                    f"for {track.duration_sec:.1f}s"
                                ),
                            )
                            self.triggered_events[loitering_key] = event
                        else:
                            self.triggered_events[loitering_key].end_time_sec = track.last_seen_sec

            # 3. Stopped Vehicle Check
            if track.duration_sec >= self.stopped_threshold_sec and speed < 5.0:
                stopped_key = f"STOPPED_{track.track_id}"
                if stopped_key not in self.triggered_events:
                    event = CCTVEvent(
                        event_type="STOPPED_VEHICLE",
                        track_id=track.track_id,
                        class_name=track.class_name,
                        start_time_sec=track.first_seen_sec,
                        end_time_sec=track.last_seen_sec,
                        confidence=track.confidence,
                        details=f"Vehicle #{track.track_id} remained stationary for {track.duration_sec:.1f}s",
                    )
                    self.triggered_events[stopped_key] = event
                else:
                    self.triggered_events[stopped_key].end_time_sec = track.last_seen_sec

        return list(self.triggered_events.values())


class GuardAbsenceDetector:
    """
    Detects when a guard (the first long-duration person in a gate zone) leaves,
    and flags subsequent persons entering that zone as SUSPICIOUS_ENTRY_UNGUARDED.

    Logic:
    - Scan all tracks in chronological order.
    - The first person track that stays in the guard_zone for > guard_min_duration_sec
      is labeled as 'guard'.
    - When the guard's last_seen_sec < track.first_seen_sec for a later person,
      a GUARD_ABSENT event fires for that gap.
    - Any person entering the gate zone after the guard left fires
      SUSPICIOUS_ENTRY_UNGUARDED.
    """

    def __init__(
        self,
        guard_zone: ZoneROI,
        guard_min_duration_sec: float = 5.0,
        absent_threshold_sec: float = 3.0,
    ) -> None:
        self.guard_zone = guard_zone
        self.guard_min_duration_sec = guard_min_duration_sec
        self.absent_threshold_sec = absent_threshold_sec

    def _is_in_zone(self, track: TrackedObject) -> bool:
        """Return True if any trajectory point of this track is inside the guard zone."""
        return any(
            self.guard_zone.contains_point(pt.x, pt.y)
            for pt in track.trajectory
        )

    def evaluate_tracks(self, tracks: Sequence[TrackedObject]) -> list[CCTVEvent]:
        """
        Analyze all tracks and return guard-absence + suspicious-entry events.
        Assumes tracks is the complete list after processing (post-pipeline).
        """
        events: list[CCTVEvent] = []

        # Filter to person tracks only
        person_tracks = [
            t for t in tracks
            if t.class_name == "person" and self._is_in_zone(t)
        ]
        # Sort by first appearance
        person_tracks.sort(key=lambda t: t.first_seen_sec)

        if not person_tracks:
            return events

        # Identify guard: first person in zone that stays long enough
        guard_track: TrackedObject | None = None
        for track in person_tracks:
            if track.duration_sec >= self.guard_min_duration_sec:
                guard_track = track
                break

        if guard_track is None:
            # No stable long-duration person found; treat first person as guard
            guard_track = person_tracks[0]

        guard_last_seen = guard_track.last_seen_sec

        # Find absent gap and suspicious entries
        for track in person_tracks:
            if track.track_id == guard_track.track_id:
                continue  # Skip the guard itself

            # Person appeared after guard left
            if track.first_seen_sec > guard_last_seen + self.absent_threshold_sec:
                absent_gap = round(track.first_seen_sec - guard_last_seen, 1)

                # Fire GUARD_ABSENT event for the gap
                events.append(
                    CCTVEvent(
                        event_type="GUARD_ABSENT",
                        track_id=guard_track.track_id,
                        class_name="person",
                        start_time_sec=guard_last_seen,
                        end_time_sec=track.first_seen_sec,
                        confidence=0.85,
                        zone_name=self.guard_zone.name,
                        details=(
                            f"Guard (Track #{guard_track.track_id}) left zone "
                            f"'{self.guard_zone.name}' at {round(guard_last_seen, 1)}s. "
                            f"Zone was unguarded for {absent_gap}s."
                        ),
                    )
                )

                # Fire SUSPICIOUS_ENTRY_UNGUARDED for the new person
                events.append(
                    CCTVEvent(
                        event_type="SUSPICIOUS_ENTRY_UNGUARDED",
                        track_id=track.track_id,
                        class_name="person",
                        start_time_sec=track.first_seen_sec,
                        end_time_sec=track.last_seen_sec,
                        confidence=0.90,
                        zone_name=self.guard_zone.name,
                        details=(
                            f"Person (Track #{track.track_id}) entered zone "
                            f"'{self.guard_zone.name}' at {round(track.first_seen_sec, 1)}s "
                            f"while guard was absent ({absent_gap}s gap). HIGH ALERT."
                        ),
                    )
                )

        return events
