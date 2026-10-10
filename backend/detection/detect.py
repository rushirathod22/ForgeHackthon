from __future__ import annotations

import argparse
import math
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

# Ensure backend root directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    import dotenv
    dotenv.load_dotenv(BACKEND_DIR / ".env")
except ImportError:
    pass

import cv2
import numpy as np
from ultralytics import YOLO

from detection.metadata_exporter import (
    DetectionItem,
    DetectionMetadataExporter,
    VideoMetadata,
)
from tracking.tracker import CCTVTracker, DetectionInput

try:
    from detection.gemini_tagger import GeminiVisionTagger
except ImportError:
    GeminiVisionTagger = None  # type: ignore[assignment,misc]

try:
    from search.embeddings import VisualEmbeddingEngine
except ModuleNotFoundError:
    from backend.search.embeddings import VisualEmbeddingEngine


# Default CCTV COCO class IDs:
#   0=person, 1=bicycle, 2=car, 3=motorcycle, 5=bus, 7=truck
#   24=backpack, 26=handbag, 67=cell phone
DEFAULT_VEHICLE_CLASS_IDS = (0, 1, 2, 3, 5, 7, 24, 26, 67)

# Accessory / carried-item classes that should be associated with a nearby person
# rather than tracked as standalone objects in the UI.
ACCESSORY_CLASS_IDS = {24, 26, 67}  # backpack, handbag, cell phone
ACCESSORY_CLASS_NAMES = {"backpack", "handbag", "cell phone"}

# COCO class-name → searchable attribute tag injected into the person track
ACCESSORY_ATTR_MAP = {
    "cell phone": "holding_phone",
    "handbag":    "holding_bag",
    "backpack":   "wearing_backpack",
}


@dataclass(frozen=True)
class DetectorConfig:
    model_path: Path
    input_path: Path
    output_path: Path
    json_output_path: Path | None = None
    confidence: float = 0.50
    target_classes: tuple[int, ...] | None = DEFAULT_VEHICLE_CLASS_IDS
    # Process only 1 out of every N frames (e.g. 6 → ~5 FPS from 30 FPS source).
    # Non-sampled frames are written to output unchanged (no inference overhead).
    sample_every_n_frames: int = 6
    # Optional YOLO-Pose model path for wrist keypoint extraction.
    # When set, person crops are run through this model and wrist (x,y) pairs
    # are injected into DetectionInput.keypoints for more accurate phone-holding detection.
    pose_model_path: Path | None = None
    # Optional Google Gemini API key for Vision-based attribute tagging.
    # When set, person crops are sent to Gemini 1.5 Flash for accurate shirt-color,
    # pants-color, phone-holding, backpack detection instead of simple HSV analysis.
    # Falls back to HSV automatically if not set or on any API error.
    gemini_api_key: str | None = field(default=None, compare=False, hash=False)
    # Optional callback called every PROGRESS_INTERVAL frames:
    # callback(frame_idx, total_frames, detections_this_frame, active_tracks)
    progress_callback: Callable[[int, int, int, int], None] | None = field(
        default=None, compare=False, hash=False
    )


@dataclass
class DetectionStats:
    frames_processed: int = 0
    frames_with_detections: int = 0
    total_detections: int = 0
    total_unique_tracks: int = 0
    detections_by_class: Counter[str] | None = None
    processing_time_sec: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    source_total_frames: int = 0
    duration_sec: float = 0.0

    def __post_init__(self) -> None:
        if self.detections_by_class is None:
            self.detections_by_class = Counter()


class CCTVDetector:
    """Process CCTV video frames with a pretrained YOLO model, persistent object tracking, exporting video & JSON metadata."""

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        try:
            import torch
            self.device = 0 if torch.cuda.is_available() else "cpu"
        except Exception:
            self.device = "cpu"

        if not self.config.model_path.is_file():
            raise FileNotFoundError(
                f"YOLO model file not found: '{self.config.model_path}'"
            )
        try:
            self.model = YOLO(str(config.model_path))
            print(f"[CCTVDetector] Loaded YOLO model on device: {self.device}")
        except Exception as error:
            raise RuntimeError(
                f"Could not load YOLO model at '{config.model_path}': {error}"
            ) from error
        self.tracker = CCTVTracker()
        self.embedder = VisualEmbeddingEngine()

        # Optional pose model — loaded lazily only when path is configured
        self._pose_model: YOLO | None = None
        if config.pose_model_path and config.pose_model_path.is_file():
            try:
                self._pose_model = YOLO(str(config.pose_model_path))
            except Exception as err:
                print(f"[CCTVDetector] Warning: could not load pose model: {err}")

        # Optional Gemini Vision tagger for accurate person attribute extraction
        self._gemini: GeminiVisionTagger | None = None
        if GeminiVisionTagger is not None:
            api_key = config.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
            if api_key:
                self._gemini = GeminiVisionTagger(api_key=api_key)
                print(f"[CCTVDetector] Gemini Vision tagger enabled (model: {self._gemini._model_name})")
            else:
                print("[CCTVDetector] No GEMINI_API_KEY set — using HSV colour analysis for attributes")

    # Interval (frames) between progress_callback invocations
    PROGRESS_INTERVAL = 6

    @staticmethod
    def _dominant_color(region_hsv: np.ndarray) -> str | None:
        """
        Return the dominant color name for an HSV image region.
        Returns None if the region is too small.
        """
        if region_hsv is None or region_hsv.size == 0:
            return None
        h_ch = region_hsv[:, :, 0]
        s_ch = region_hsv[:, :, 1]
        v_ch = region_hsv[:, :, 2]
        mean_v = float(np.mean(v_ch))
        mean_s = float(np.mean(s_ch))

        if mean_v < 45:
            return "black"
        if mean_v > 200 and mean_s < 55:
            return "white"
        if mean_s < 50:
            return "gray"

        colorful = s_ch > 45
        if not np.any(colorful):
            return "gray"

        hist = cv2.calcHist([h_ch[colorful]], [0], None, [18], [0, 180]).flatten()
        peak_hue = int(np.argmax(hist) * 10)
        color_ranges = {
            "red": [(0, 10), (170, 180)],
            "orange": [(11, 25)],
            "yellow": [(26, 35)],
            "green": [(36, 85)],
            "cyan": [(86, 100)],
            "blue": [(101, 130)],
            "purple": [(131, 155)],
        }
        for color_name, ranges in color_ranges.items():
            if any(r_min <= peak_hue <= r_max for r_min, r_max in ranges):
                return color_name
        return None

    @staticmethod
    def infer_visual_attributes(crop_bgr: np.ndarray | None) -> list[str]:
        """
        Infer searchable visual color attributes from the best object crop.
        For person crops, splits into upper body (shirt region) and lower body
        (pants region) to generate tagged attributes like 'black_shirt', 'blue_pants'.
        Plain color tags are always included for backward-compat search.
        """
        if crop_bgr is None or crop_bgr.size == 0:
            return []

        h, w = crop_bgr.shape[:2]
        if h < 10 or w < 4:
            return []

        crop_hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
        attrs: list[str] = []

        # Crop central torso (trim 20% left/right margins & 15% top head)
        # to focus strictly on actual clothing and eliminate background store shelves (red stands, blue racks)
        margin_x = int(w * 0.20)
        w_start = margin_x
        w_end = max(margin_x + 1, w - margin_x)

        top_head = int(h * 0.12)
        split = max(top_head + 1, int(h * 0.55))
        bottom_feet = max(split + 1, int(h * 0.90))

        upper_hsv = crop_hsv[top_head:split, w_start:w_end, :]
        lower_hsv = crop_hsv[split:bottom_feet, w_start:w_end, :]

        upper_color = CCTVDetector._dominant_color(upper_hsv)
        lower_color = CCTVDetector._dominant_color(lower_hsv)

        if upper_color:
            attrs.append(upper_color)            # plain tag: "black"
            attrs.append(f"{upper_color}_shirt") # tagged: "black_shirt"
        if lower_color and lower_color != upper_color:
            attrs.append(lower_color)
            attrs.append(f"{lower_color}_pants")
        elif lower_color:
            attrs.append(f"{lower_color}_pants")

        return list(dict.fromkeys(attrs))

    def process(self) -> tuple[DetectionStats, Path | None]:
        if not self.config.input_path.is_file():
            raise FileNotFoundError(
                f"Input video was not found: '{self.config.input_path}'"
            )

        capture = cv2.VideoCapture(str(self.config.input_path))
        if not capture.isOpened():
            raise RuntimeError(f"Could not open input video: '{self.config.input_path}'")

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        if frame_width <= 0 or frame_height <= 0:
            capture.release()
            raise RuntimeError("Input video has invalid frame dimensions")

        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_output_path = self.config.output_path.with_name(
            f"{self.config.output_path.stem}.part{self.config.output_path.suffix}"
        )
        if temporary_output_path.exists():
            temporary_output_path.unlink()

        writer = cv2.VideoWriter(
            str(temporary_output_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (frame_width, frame_height),
        )
        if not writer.isOpened():
            capture.release()
            raise RuntimeError(
                f"Could not create output video: '{self.config.output_path}'"
            )

        json_path = self.config.json_output_path or self.config.output_path.with_suffix(".json")
        meta_info = VideoMetadata(
            video_name=self.config.input_path.name,
            fps=round(fps, 2),
            width=frame_width,
            height=frame_height,
            total_frames=total_frames,
            model_name=self.config.model_path.name,
            confidence_threshold=self.config.confidence,
        )
        exporter = DetectionMetadataExporter(meta_info, json_path)
        stats = DetectionStats()
        stats.fps = round(float(fps), 2)
        stats.width = frame_width
        stats.height = frame_height
        stats.source_total_frames = total_frames
        stats.duration_sec = round(total_frames / fps, 2) if total_frames > 0 and fps > 0 else 0.0

        start_time = time.time()
        frame_idx = 0
        sample_n = max(1, self.config.sample_every_n_frames)

        if self.config.progress_callback is not None and total_frames > 0:
            try:
                self.config.progress_callback(0, total_frames, 0, 0)
            except Exception:
                pass

        try:
            while True:
                success, frame = capture.read()
                if not success:
                    break

                timestamp_sec = round(frame_idx / fps, 3)

                # ── Frame sampling: skip inference on non-sampled frames ────
                if frame_idx % sample_n != 0:
                    writer.write(frame)  # write original frame without annotation
                    frame_idx += 1
                    stats.frames_processed = frame_idx
                    if self.config.progress_callback is not None and frame_idx % 24 == 0:
                        try:
                            self.config.progress_callback(
                                frame_idx,
                                total_frames,
                                stats.total_detections,
                                len(self.tracker.tracks),
                            )
                        except Exception:
                            pass
                    continue

                predict_kwargs = {
                    "source": frame,
                    "conf": self.config.confidence,
                    "verbose": False,
                    "device": self.device,
                }
                if self.device != "cpu":
                    predict_kwargs["half"] = True
                if self.config.target_classes is not None:
                    predict_kwargs["classes"] = list(self.config.target_classes)

                results = self.model.predict(**predict_kwargs)
                result = results[0]
                annotated_frame = result.plot()

                frame_detections_input: list[DetectionInput] = []
                if result.boxes is not None and len(result.boxes) > 0:
                    stats.frames_with_detections += 1
                    for box in result.boxes:
                        class_id = int(box.cls.item())
                        class_name = str(self.model.names[class_id])
                        conf = float(box.conf.item())
                        xyxy = box.xyxy[0].tolist()
                        rounded_bbox = [round(v, 2) for v in xyxy]

                        # Extract bounding box crop safely for visual embeddings
                        x1 = max(0, int(rounded_bbox[0]))
                        y1 = max(0, int(rounded_bbox[1]))
                        x2 = min(frame.shape[1], int(rounded_bbox[2]))
                        y2 = min(frame.shape[0], int(rounded_bbox[3]))
                        crop_bgr = frame[y1:y2, x1:x2].copy() if (x2 > x1 and y2 > y1) else None

                        # ── Pose keypoint extraction for prominent person detections ──
                        wrist_kps: list[tuple[float, float]] | None = None
                        if class_name == "person" and self._pose_model is not None and crop_bgr is not None:
                            # Optimize: Only run pose on significant persons (>60px high) to avoid CPU thrashing
                            if crop_bgr.shape[0] >= 60 and crop_bgr.shape[1] >= 25:
                                try:
                                    pose_kwargs = {
                                        "source": crop_bgr,
                                        "conf": 0.35,
                                        "verbose": False,
                                        "device": self.device,
                                    }
                                    if self.device != "cpu":
                                        pose_kwargs["half"] = True
                                    pose_results = self._pose_model.predict(**pose_kwargs)
                                    if pose_results and pose_results[0].keypoints is not None:
                                        kp_xy = pose_results[0].keypoints.xy
                                        if kp_xy is not None and len(kp_xy) > 0:
                                            # kp_xy shape: (num_persons, 17, 2)
                                            kps_np = kp_xy[0].tolist()
                                            wrist_kps = [
                                                (float(kx) + x1, float(ky) + y1)
                                                for kx, ky in kps_np
                                            ]
                                except Exception:
                                    wrist_kps = None

                        frame_detections_input.append(
                            DetectionInput(
                                class_id=class_id,
                                class_name=class_name,
                                confidence=round(conf, 4),
                                bbox=rounded_bbox,
                                crop_bgr=crop_bgr,
                                keypoints=wrist_kps,
                            )
                        )
                        stats.total_detections += 1
                        stats.detections_by_class[class_name] += 1

                # Update multi-object tracker
                active_tracks = self.tracker.update(
                    frame_detections_input, timestamp_sec, fps
                )

                frame_detections: list[DetectionItem] = []
                for track in active_tracks:
                    frame_detections.append(
                        DetectionItem(
                            class_id=track.class_id,
                            class_name=track.class_name,
                            confidence=track.confidence,
                            bbox=track.bbox,
                            track_id=track.track_id,
                        )
                    )
                    # Render Track ID badge on frame
                    x1, y1 = int(track.bbox[0]), int(track.bbox[1])
                    label = f"Track #{track.track_id} ({track.class_name})"
                    cv2.putText(
                        annotated_frame,
                        label,
                        (x1, max(15, y1 - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        2,
                    )
                    # Render motion trail
                    if len(track.trajectory) > 1:
                        pts = [
                            (int(pt.x), int(pt.y))
                            for pt in track.trajectory[-15:]
                        ]
                        for i in range(1, len(pts)):
                            cv2.line(
                                annotated_frame,
                                pts[i - 1],
                                pts[i],
                                (0, 255, 255),
                                2,
                            )

                writer.write(annotated_frame)

                exporter.add_frame_detections(
                    frame_index=frame_idx,
                    timestamp_sec=timestamp_sec,
                    detections=frame_detections,
                )

                frame_idx += 1
                stats.frames_processed = frame_idx

                if total_frames > 0 and (frame_idx % 100 == 0 or frame_idx == total_frames):
                    elapsed = time.time() - start_time
                    processing_fps = frame_idx / elapsed if elapsed > 0 else 0
                    pct = (frame_idx / total_frames) * 100
                    print(
                        f"Processed {frame_idx}/{total_frames} frames ({pct:.1f}%) | "
                        f"Speed: {processing_fps:.1f} FPS",
                        flush=True,
                    )

                # Fire progress callback smoothly to update the frontend
                if self.config.progress_callback is not None and (
                    frame_idx % (sample_n * 2) == 0 or frame_idx >= total_frames
                ):
                    try:
                        self.config.progress_callback(
                            frame_idx,
                            total_frames,
                            stats.total_detections,
                            len(active_tracks),
                        )
                    except Exception:
                        pass  # Never let a broken callback kill the pipeline
        finally:
            capture.release()
            writer.release()

        stats.processing_time_sec = round(time.time() - start_time, 2)

        # ── Attribute inference: Gemini Vision first, HSV fallback ─────────────
        for track in self.tracker.tracks:
            if track.embedding is None and track.best_crop_bgr is not None:
                track.embedding = self.embedder.embed_image(track.best_crop_bgr)

            # Only run Gemini on person crops (most useful for NL person search)
            gemini_tags: list[str] = []
            if (
                track.class_name == "person"
                and self._gemini is not None
                and self._gemini.is_available
                and track.best_crop_bgr is not None
            ):
                gemini_tags = self._gemini.tag(track.best_crop_bgr)

            if gemini_tags:
                # Gemini succeeded — use its richer tags; HSV skipped
                track.visual_attributes = gemini_tags
            else:
                # HSV fallback (always works, less accurate on clothing color)
                track.visual_attributes = self.infer_visual_attributes(track.best_crop_bgr)

        # ── Accessory co-location tagging ─────────────────────────────────────
        # For every accessory track (phone/bag/backpack), find person tracks that
        # were spatially close at the same time and inject attribute tags such as
        # "holding_phone" so natural-language queries like "person with phone" work.
        #
        # Priority order:
        #   1. Wrist-keypoint distance  (most accurate — requires pose model)
        #   2. Centre-to-centre distance (fallback when pose is unavailable)
        PROXIMITY_PX   = 120  # max centre-to-centre distance
        WRIST_PROX_PX  = 80   # max phone-centre to wrist distance (tighter threshold)
        # COCO keypoint indices for wrists
        LEFT_WRIST_IDX  = 9
        RIGHT_WRIST_IDX = 10

        accessory_tracks = [
            t for t in self.tracker.tracks
            if t.class_name in ACCESSORY_CLASS_NAMES and t.trajectory
        ]
        person_tracks = [
            t for t in self.tracker.tracks
            if t.class_name == "person" and t.trajectory
        ]

        for acc_track in accessory_tracks:
            attr_tag = ACCESSORY_ATTR_MAP.get(acc_track.class_name)
            if not attr_tag:
                continue

            # Build a quick lookup of (timestamp_sec → center) for this accessory
            acc_positions: dict[float, tuple[float, float]] = {
                pt.timestamp_sec: (pt.x, pt.y) for pt in acc_track.trajectory
            }

            for person_track in person_tracks:
                tagged = False
                for pt in person_track.trajectory:
                    # Find accessory position closest in time (within 0.5s)
                    acc_center = acc_positions.get(pt.timestamp_sec)
                    if acc_center is None:
                        # Try nearest timestamp within ±0.5 s
                        best_dt = 0.5
                        for acc_t, acc_c in acc_positions.items():
                            dt = abs(acc_t - pt.timestamp_sec)
                            if dt < best_dt:
                                best_dt = dt
                                acc_center = acc_c

                    if acc_center is None:
                        continue

                    # ── Method 1: wrist-keypoint distance (pose model only) ──
                    if person_track.wrist_keypoints and attr_tag == "holding_phone":
                        kps = person_track.wrist_keypoints
                        wrists: list[tuple[float, float]] = []
                        if len(kps) > LEFT_WRIST_IDX:
                            wx, wy = kps[LEFT_WRIST_IDX]
                            if wx > 0 and wy > 0:
                                wrists.append((wx, wy))
                        if len(kps) > RIGHT_WRIST_IDX:
                            wx, wy = kps[RIGHT_WRIST_IDX]
                            if wx > 0 and wy > 0:
                                wrists.append((wx, wy))
                        if wrists:
                            min_wrist_dist = min(
                                math.hypot(acc_center[0] - wx, acc_center[1] - wy)
                                for wx, wy in wrists
                            )
                            if min_wrist_dist <= WRIST_PROX_PX:
                                tagged = True
                                break
                            continue  # pose available but wrist too far — don't fall back

                    # ── Method 2: centre-to-centre fallback ──────────────────
                    dist = math.hypot(pt.x - acc_center[0], pt.y - acc_center[1])
                    if dist <= PROXIMITY_PX:
                        tagged = True
                        break

                if tagged and attr_tag not in person_track.visual_attributes:
                    person_track.visual_attributes.append(attr_tag)

        # ── Movement direction tagging ─────────────────────────────────────────
        # Compute net displacement vector of each track and classify into a
        # searchable direction tag (going_right, going_left, going_up, going_down).
        # Also add toward_stair heuristic based on video quadrant.
        for track in self.tracker.tracks:
            if len(track.trajectory) < 3:
                continue
            first_pt = track.trajectory[0]
            last_pt  = track.trajectory[-1]
            dx = last_pt.x - first_pt.x
            dy = last_pt.y - first_pt.y
            dist_moved = math.hypot(dx, dy)

            # Only tag tracks that actually moved (>30px net displacement)
            if dist_moved < 30:
                if "stationary" not in track.visual_attributes:
                    track.visual_attributes.append("stationary")
                continue

            # Primary direction: whichever axis has larger displacement
            if abs(dx) >= abs(dy):
                direction = "going_right" if dx > 0 else "going_left"
            else:
                direction = "going_down" if dy > 0 else "going_up"

            if direction not in track.visual_attributes:
                track.visual_attributes.append(direction)

            # toward_stair heuristic: track ends in upper portion of frame
            # (stairs in surveillance typically go up = negative dy in image coords)
            # Also tag if final position is in the right side of the frame
            end_x_frac = last_pt.x / max(stats.width, 1)
            end_y_frac = last_pt.y / max(stats.height, 1)
            if dy < -40 or end_y_frac < 0.35:  # moving upward in frame
                if "toward_stair" not in track.visual_attributes:
                    track.visual_attributes.append("toward_stair")
            if end_x_frac > 0.65 and dy < 20:  # ending on right side, not moving down
                if "toward_stair" not in track.visual_attributes:
                    track.visual_attributes.append("toward_stair")

            # toward_exit heuristic: moving toward bottom or doorway area (positive dy or bottom of frame)
            if dy > 30 or end_y_frac > 0.60:
                if "toward_exit" not in track.visual_attributes:
                    track.visual_attributes.append("toward_exit")

        # ── Group / proximity tagging ──────────────────────────────────────────
        # For every pair of person tracks, measure how long they co-existed within
        # 200px of each other. ≥2 seconds → tag both as "moving_with_others" and
        # "in_group_of_N" so "two persons together" queries work correctly.
        GROUP_DIST_PX    = 200   # max centre distance to be "together"
        GROUP_MIN_SEC    = 2.0   # minimum co-located duration
        frame_dt         = 1.0 / max(fps, 1.0)

        # Build per-track position dicts once (timestamp → (x,y))
        pos_by_id: dict[int, dict[float, tuple[float, float]]] = {}
        for t in person_tracks:
            pos_by_id[t.track_id] = {pt.timestamp_sec: (pt.x, pt.y)
                                      for pt in t.trajectory}

        # Count companions for each person track
        companion_counts: dict[int, int] = {t.track_id: 0 for t in person_tracks}

        for i in range(len(person_tracks)):
            for j in range(i + 1, len(person_tracks)):
                p1 = person_tracks[i]
                p2 = person_tracks[j]
                pos1 = pos_by_id[p1.track_id]
                pos2 = pos_by_id[p2.track_id]

                # Count overlapping timestamps where they are close
                close_frames = 0
                for ts, c1 in pos1.items():
                    c2 = pos2.get(ts)
                    if c2 is None:
                        continue
                    if math.hypot(c1[0] - c2[0], c1[1] - c2[1]) <= GROUP_DIST_PX:
                        close_frames += 1

                close_sec = close_frames * frame_dt
                if close_sec >= GROUP_MIN_SEC:
                    companion_counts[p1.track_id] = companion_counts.get(p1.track_id, 0) + 1
                    companion_counts[p2.track_id] = companion_counts.get(p2.track_id, 0) + 1

        # Inject group tags
        for track in person_tracks:
            companions = companion_counts.get(track.track_id, 0)
            if companions >= 1:
                group_size = companions + 1  # include self
                group_tag  = f"in_group_of_{min(group_size, 6)}"
                if "moving_with_others" not in track.visual_attributes:
                    track.visual_attributes.append("moving_with_others")
                if group_tag not in track.visual_attributes:
                    track.visual_attributes.append(group_tag)

        tracks_summary = self.tracker.get_all_tracks_summary()


        stats.total_unique_tracks = len(tracks_summary)
        exporter.set_tracks_summary(tracks_summary)

        if not temporary_output_path.is_file() or temporary_output_path.stat().st_size == 0:
            raise RuntimeError("The processed video file was not created properly")
        os.replace(temporary_output_path, self.config.output_path)

        exporter.save()
        return stats, json_path


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_args(args: Sequence[str] | None = None) -> DetectorConfig:
    root = repository_root()
    parser = argparse.ArgumentParser(description="Run YOLO detection on a CCTV video")
    parser.add_argument(
        "--model",
        type=Path,
        default=root / "backend" / "yolo11n.pt",
        help="Path to a YOLO11 model file",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "videos" / "input" / "test_cctv.mp4",
        help="Path to the input CCTV video",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "videos" / "processed" / "test_cctv_detected.mp4",
        help="Path for the annotated output video",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Path for saving frame metadata in JSON format (defaults to <output>.json)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.50,
        help="Minimum detection confidence from 0.0 to 1.0",
    )
    parser.add_argument(
        "--all-classes",
        action="store_true",
        help="Detect all COCO object classes instead of only vehicles",
    )

    parsed = parser.parse_args(args)
    if not 0.0 <= parsed.confidence <= 1.0:
        parser.error("--confidence must be between 0.0 and 1.0")

    target_classes = None if parsed.all_classes else DEFAULT_VEHICLE_CLASS_IDS
    return DetectorConfig(
        model_path=parsed.model,
        input_path=parsed.input,
        output_path=parsed.output,
        json_output_path=parsed.json_output,
        confidence=parsed.confidence,
        target_classes=target_classes,
    )


def main() -> None:
    config = parse_args()
    try:
        stats, json_path = CCTVDetector(config).process()
    except (FileNotFoundError, RuntimeError) as error:
        raise SystemExit(f"Detection failed: {error}") from error

    print("\n--- Detection Summary ---")
    print(f"Annotated Video Output : {config.output_path}")
    print(f"JSON Metadata Output   : {json_path}")
    print(f"Total Frames Processed : {stats.frames_processed}")
    print(f"Frames with Detections : {stats.frames_with_detections}")
    print(f"Total Detections       : {stats.total_detections}")
    print(f"Processing Time        : {stats.processing_time_sec}s")
    print("Detections by Class:")
    if stats.detections_by_class:
        for class_name, count in sorted(stats.detections_by_class.items()):
            print(f"  - {class_name}: {count}")
    else:
        print("  - None")


if __name__ == "__main__":
    main()
