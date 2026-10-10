from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from db.models import EventRecord, TrackRecord, VideoRecord
    from db.session import SessionLocal, get_db
    from detection.detect import CCTVDetector, DetectorConfig
    from events.clip_exporter import ClipExporter
    from events.detector import EventDetector, GuardAbsenceDetector, ZoneROI
except ModuleNotFoundError:
    from backend.db.models import EventRecord, TrackRecord, VideoRecord
    from backend.db.session import SessionLocal, get_db
    from backend.detection.detect import CCTVDetector, DetectorConfig
    from backend.events.clip_exporter import ClipExporter
    from backend.events.detector import EventDetector, GuardAbsenceDetector, ZoneROI

router = APIRouter(prefix="/api/v1", tags=["videos"])

ROOT_DIR = Path(__file__).resolve().parents[3]
INPUT_DIR = ROOT_DIR / "videos" / "input"
PROCESSED_DIR = ROOT_DIR / "videos" / "processed"
CLIPS_DIR = ROOT_DIR / "videos" / "clips"
MODEL_PATH = ROOT_DIR / "backend" / "yolo11n.pt"

# ── In-memory progress store: job_id → latest progress dict ──────────────────
# Written from background thread, read by SSE endpoint.
_progress_store: dict[str, dict] = {}


def _make_progress_callback(job_id: str, total_frames: int):
    """Return a closure that writes frame progress to the in-memory store."""
    def callback(frame: int, total: int, detections: int, tracks: int) -> None:
        eff_total = total if total > 0 else (total_frames or 1)
        raw_pct = (frame / eff_total) * 100 if eff_total > 0 else 0.0
        # Cap at 95% during detection phase to leave room for clip indexing
        pct = round(min(95.0, raw_pct), 1)
        _progress_store[job_id] = {
            "frame": frame,
            "total": eff_total,
            "pct": pct,
            "detections": detections,
            "tracks": tracks,
            "status": "PROCESSING",
            "stage": "DETECTING",
            "detail": f"Frame {frame} of {eff_total} finished ({pct}%) • {tracks} tracks • {detections} detections",
        }
    return callback


def run_video_pipeline(video_id: str) -> None:
    """Background worker pipeline: Detection → Tracking → Event Engine → Persistence → Clip Exporter."""
    db = SessionLocal()
    video = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
    if not video:
        db.close()
        return

    try:
        video.status = "PROCESSING"
        db.commit()

        input_path = Path(video.filepath)
        output_path = PROCESSED_DIR / f"{video_id}_annotated.mp4"
        json_path = PROCESSED_DIR / f"{video_id}_metadata.json"
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        CLIPS_DIR.mkdir(parents=True, exist_ok=True)

        # Get total frames for progress callback (quick open)
        import cv2 as _cv2
        _cap = _cv2.VideoCapture(str(input_path))
        total_frames_hint = int(_cap.get(_cv2.CAP_PROP_FRAME_COUNT)) or 0
        _cap.release()

        _progress_store[video_id] = {
            "frame": 0,
            "total": total_frames_hint or 1,
            "pct": 0.0,
            "detections": 0,
            "tracks": 0,
            "status": "PROCESSING",
        }

        POSE_MODEL_PATH = ROOT_DIR / "backend" / "yolo11n-pose.pt"

        # Adaptive dynamic frame subsampling based on video length (for ultra-fast 1-2 hour video processing)
        if total_frames_hint > 90000:       # > 50 mins (~1 to 2+ hours)
            sample_rate = 18                 # ~1.6 FPS sampling
        elif total_frames_hint > 30000:     # 15 to 50 mins
            sample_rate = 12                 # ~2.5 FPS sampling
        elif total_frames_hint > 5000:      # 3 to 15 mins
            sample_rate = 8                  # ~3.75 FPS sampling
        else:
            sample_rate = 5                  # ~6.0 FPS sampling

        config = DetectorConfig(
            model_path=MODEL_PATH,
            input_path=input_path,
            output_path=output_path,
            json_output_path=json_path,
            confidence=0.40,
            sample_every_n_frames=sample_rate,
            pose_model_path=POSE_MODEL_PATH if POSE_MODEL_PATH.is_file() else None,
            progress_callback=_make_progress_callback(video_id, total_frames_hint),
        )

        detector = CCTVDetector(config)
        stats, _ = detector.process()

        # ── Event Engine (rule-based) ─────────────────────────────────────────
        # Main gate zone: full-width top 40% of frame (normalized to actual px)
        frame_w = stats.width or 1920
        frame_h = stats.height or 1080
        gate_polygon = [
            (0.0, 0.0),
            (float(frame_w), 0.0),
            (float(frame_w), float(frame_h * 0.4)),
            (0.0, float(frame_h * 0.4)),
        ]
        zones = [ZoneROI(name="MainGate", polygon=gate_polygon)]
        event_engine = EventDetector(zones=zones)
        rule_events = event_engine.evaluate_tracks(detector.tracker.tracks)

        # ── Guard Absence Engine ──────────────────────────────────────────────
        guard_zone = ZoneROI(name="MainGate", polygon=gate_polygon)
        guard_detector = GuardAbsenceDetector(
            guard_zone=guard_zone,
            guard_min_duration_sec=5.0,
            absent_threshold_sec=3.0,
        )
        guard_events = guard_detector.evaluate_tracks(detector.tracker.tracks)
        all_rule_events = rule_events + guard_events

        # ── Build lookup maps ─────────────────────────────────────────────────
        track_embedding_map = {
            t.track_id: json.dumps(t.embedding) if t.embedding else None
            for t in detector.tracker.tracks
        }
        track_visual_attr_map = {
            t.track_id: json.dumps(t.visual_attributes) if t.visual_attributes else None
            for t in detector.tracker.tracks
        }

        # ── Save Tracks to DB ─────────────────────────────────────────────────
        for t in detector.tracker.tracks:
            track_rec = TrackRecord(
                video_id=video_id,
                track_id=t.track_id,
                class_name=t.class_name,
                first_seen_sec=round(t.first_seen_sec, 2),
                last_seen_sec=round(t.last_seen_sec, 2),
                duration_sec=t.duration_sec,
                avg_speed_px_sec=t.average_speed_px_sec,
                trajectory_json=json.dumps(
                    [
                        {
                            "x": p.x,
                            "y": p.y,
                            "w": getattr(p, "w", 120.0),
                            "h": getattr(p, "h", 160.0),
                            "t": p.timestamp_sec,
                        }
                        for p in t.trajectory
                    ]
                ),
                embedding_json=json.dumps(t.embedding) if t.embedding else None,
                visual_attributes_json=json.dumps(t.visual_attributes) if t.visual_attributes else None,
            )
            db.add(track_rec)

        # ── Object-tracked catch-all events (one per stable track) ───────────
        object_events = []
        for t in detector.tracker.tracks:
            attrs = f" Attributes: {', '.join(t.visual_attributes)}." if t.visual_attributes else ""
            object_events.append(
                {
                    "event_id": str(uuid.uuid4()),
                    "event_type": "OBJECT_TRACKED",
                    "track_id": t.track_id,
                    "class_name": t.class_name,
                    "start_time_sec": t.first_seen_sec,
                    "end_time_sec": max(t.last_seen_sec, t.first_seen_sec + 0.1),
                    "confidence": t.confidence,
                    "zone_name": None,
                    "details": (
                        f"Track #{t.track_id} ({t.class_name}) observed from "
                        f"{round(t.first_seen_sec, 2)}s to {round(t.last_seen_sec, 2)}s.{attrs}"
                    ),
                }
            )

        rule_events_dicts = [
            {
                "event_id": ev.event_id,
                "event_type": ev.event_type,
                "track_id": ev.track_id,
                "class_name": ev.class_name,
                "start_time_sec": ev.start_time_sec,
                "end_time_sec": ev.end_time_sec,
                "confidence": ev.confidence,
                "zone_name": ev.zone_name,
                "details": ev.details,
            }
            for ev in all_rule_events
        ]

        # ── Save Events & Extract Clips ───────────────────────────────────────
        _progress_store[video_id] = {
            "frame": stats.frames_processed,
            "total": stats.source_total_frames or stats.frames_processed,
            "pct": 96.0,
            "detections": stats.total_detections,
            "tracks": stats.total_unique_tracks,
            "status": "PROCESSING",
            "stage": "INDEXING",
            "detail": f"All {stats.frames_processed} frames analyzed. Finalizing evidence clips & AI attributes...",
        }
        clip_exporter = ClipExporter(padding_sec=1.5)

        # Prioritize extracting clips for actual security rule events,
        # plus up to top 6 significant object tracks to avoid generating thousands of subclips
        events_to_clip_ids = set()
        for ev in rule_events_dicts:
            events_to_clip_ids.add(ev["event_id"])
        
        longest_objects = sorted(object_events, key=lambda x: x["end_time_sec"] - x["start_time_sec"], reverse=True)[:6]
        for ev in longest_objects:
            events_to_clip_ids.add(ev["event_id"])

        for ev in [*rule_events_dicts, *object_events]:
            clip_path = CLIPS_DIR / f"clip_{ev['event_id']}.mp4"
            extracted_clip: Path | None = None

            # Only extract clips for prioritized events with duration > 0.5s
            clip_duration = max(0.0, ev["end_time_sec"] - ev["start_time_sec"])
            if ev["event_id"] in events_to_clip_ids and clip_duration > 0.5:
                try:
                    extracted_clip = clip_exporter.extract_clip(
                        source_video_path=output_path,
                        start_time_sec=ev["start_time_sec"],
                        end_time_sec=ev["end_time_sec"],
                        output_clip_path=clip_path,
                    )
                    if extracted_clip and (not extracted_clip.is_file() or extracted_clip.stat().st_size < 1024):
                        extracted_clip = None
                except Exception as err:
                    print(f"Warning: could not extract clip for event {ev['event_id']}: {err}")
                    extracted_clip = None

            event_rec = EventRecord(
                id=ev["event_id"],
                video_id=video_id,
                track_id=ev["track_id"],
                event_type=ev["event_type"],
                class_name=ev["class_name"],
                start_time_sec=round(ev["start_time_sec"], 2),
                end_time_sec=round(ev["end_time_sec"], 2),
                confidence=ev["confidence"],
                zone_name=ev["zone_name"],
                details=ev["details"],
                clip_path=str(extracted_clip) if extracted_clip else None,
                embedding_json=track_embedding_map.get(ev["track_id"]),
                visual_attributes_json=track_visual_attr_map.get(ev["track_id"]),
            )
            db.add(event_rec)

        video.annotated_filepath = str(output_path)
        video.json_metadata_path = str(json_path)
        video.duration_sec = stats.duration_sec
        video.fps = stats.fps
        video.width = stats.width
        video.height = stats.height
        video.total_frames = stats.source_total_frames or stats.frames_processed
        video.status = "COMPLETED"
        db.commit()

        _progress_store[video_id] = {
            "frame": stats.frames_processed,
            "total": stats.source_total_frames or stats.frames_processed,
            "pct": 100.0,
            "detections": stats.total_detections,
            "tracks": stats.total_unique_tracks,
            "status": "COMPLETED",
            "stage": "COMPLETED",
            "detail": f"Complete! {stats.frames_processed} frames analyzed • {stats.total_unique_tracks} tracks indexed",
        }

    except Exception as exc:
        db.rollback()
        video.status = f"FAILED: {str(exc)}"
        db.commit()
        _progress_store[video_id] = {
            "frame": 0,
            "total": 0,
            "pct": 0.0,
            "status": f"FAILED: {str(exc)}",
        }
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────


class VideoRegisterRequest(BaseModel):
    filename: str
    filepath: str


@router.post("/videos/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a CCTV video MP4 file and start background detection & tracking."""
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    video_id = str(uuid.uuid4())
    save_path = INPUT_DIR / f"{video_id}_{file.filename}"

    with open(save_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):
            buffer.write(chunk)

    video = VideoRecord(
        id=video_id,
        filename=file.filename,
        filepath=str(save_path),
        status="QUEUED",
    )
    db.add(video)
    db.commit()

    background_tasks.add_task(run_video_pipeline, video_id)
    return {"video_id": video_id, "status": "QUEUED", "message": "Video uploaded and processing queued."}


@router.post("/videos/register")
def register_video(
    req: VideoRegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Register an existing local CCTV video path for processing."""
    video_path = Path(req.filepath)
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found at '{req.filepath}'")

    video_id = str(uuid.uuid4())
    video = VideoRecord(
        id=video_id,
        filename=req.filename,
        filepath=str(video_path),
        status="QUEUED",
    )
    db.add(video)
    db.commit()

    background_tasks.add_task(run_video_pipeline, video_id)
    return {"video_id": video_id, "status": "QUEUED", "message": "Video registered and processing queued."}


@router.post("/videos/{video_id}/reprocess")
def reprocess_video(
    video_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Re-queue a FAILED or stuck PROCESSING video for re-processing.
    Useful after a server restart that killed an in-progress job.
    The original uploaded file is still on disk and will be re-processed.
    """
    video = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.status == "PROCESSING":
        # Force-reset stuck job
        video.status = "QUEUED"
        db.commit()
    elif video.status not in ("FAILED", "QUEUED") and not video.status.startswith("FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Video is in status '{video.status}'. Only FAILED or PROCESSING videos can be reprocessed.",
        )

    if not Path(video.filepath).is_file():
        raise HTTPException(
            status_code=404,
            detail=f"Source video file no longer exists at '{video.filepath}'. Please re-upload.",
        )

    # Delete old tracks + events so they won't duplicate
    from db.models import TrackRecord, EventRecord  # noqa: F811
    db.query(EventRecord).filter(EventRecord.video_id == video_id).delete()
    db.query(TrackRecord).filter(TrackRecord.video_id == video_id).delete()
    video.status = "QUEUED"
    video.annotated_filepath = None
    video.json_metadata_path = None
    db.commit()

    background_tasks.add_task(run_video_pipeline, video_id)
    return {"video_id": video_id, "status": "QUEUED", "message": "Video requeued for re-processing."}


def reset_stuck_processing_jobs() -> None:
    """
    Called at server startup: mark any videos stuck in PROCESSING as FAILED.
    They were interrupted by a previous server restart and need to be reprocessed.
    """
    db = SessionLocal()
    try:
        stuck = db.query(VideoRecord).filter(VideoRecord.status == "PROCESSING").all()
        for v in stuck:
            v.status = "FAILED: interrupted_by_restart"
            _progress_store[v.id] = {"status": "FAILED: interrupted_by_restart", "frame": 0, "total": 0, "pct": 0}
        if stuck:
            db.commit()
            print(f"[startup] Reset {len(stuck)} stuck PROCESSING video(s) to FAILED.")
    except Exception as e:
        print(f"[startup] Warning: could not reset stuck jobs: {e}")
    finally:
        db.close()


@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Get status of a video processing job with live frame and detection counters."""
    video = db.query(VideoRecord).filter(VideoRecord.id == job_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Job not found")

    prog = _progress_store.get(job_id, {})
    eff_status = prog.get("status", video.status)
    is_done = video.status == "COMPLETED" or eff_status == "COMPLETED"
    
    frame = prog.get("frame", video.total_frames if is_done else 0)
    total = prog.get("total", video.total_frames or 1)
    pct = 100.0 if is_done else prog.get("pct", 0.0)
    detections = prog.get("detections", 0)
    tracks = prog.get("tracks", len(video.tracks))
    stage = prog.get("stage", "COMPLETED" if is_done else "PROCESSING")
    detail = prog.get("detail", f"Frame {frame} of {total} finished" if not is_done else f"Ready! {total} frames indexed")

    return {
        "job_id": video.id,
        "filename": video.filename,
        "status": "COMPLETED" if is_done else eff_status,
        "stage": stage,
        "frame": frame,
        "total": total,
        "pct": pct,
        "detections": detections,
        "tracks": tracks,
        "detail": detail,
        "total_tracks": len(video.tracks),
        "total_events": len(video.events),
        "processed_at": video.processed_at.isoformat() if video.processed_at else None,
    }


@router.get("/jobs/{job_id}/progress")
async def stream_job_progress(job_id: str, db: Session = Depends(get_db)):
    """
    SSE endpoint that streams real-time processing progress for a video job.
    Clients connect with EventSource and receive frame-level progress events.
    Event format: data: {"frame": N, "total": M, "pct": 55.0, "detections": K, "tracks": J, "status": "PROCESSING"}
    """
    video = db.query(VideoRecord).filter(VideoRecord.id == job_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        last_frame = -1
        last_status = None
        timeout_secs = 600  # max stream duration
        elapsed = 0.0
        interval = 0.4  # check every 400ms

        while elapsed < timeout_secs:
            progress = _progress_store.get(job_id)
            if not progress:
                # Query DB to get ground-truth status
                v_db = db.query(VideoRecord).filter(VideoRecord.id == job_id).first()
                if v_db:
                    if v_db.status == "COMPLETED":
                        progress = {
                            "status": "COMPLETED",
                            "frame": v_db.total_frames or 1,
                            "total": v_db.total_frames or 1,
                            "pct": 100.0,
                            "detections": 0,
                            "tracks": len(v_db.tracks),
                        }
                    elif v_db.status.startswith("FAILED"):
                        progress = {
                            "status": v_db.status,
                            "frame": 0,
                            "total": v_db.total_frames or 1,
                            "pct": 0.0,
                        }
                    else:
                        progress = {
                            "status": v_db.status,
                            "frame": 0,
                            "total": v_db.total_frames or 1,
                            "pct": 0.0,
                        }
                else:
                    progress = {"status": "QUEUED", "frame": 0, "total": 1, "pct": 0.0}

            current_frame = progress.get("frame", 0)
            status = progress.get("status", "")

            # Emit when frame advances OR status changes
            if current_frame != last_frame or status != last_status:
                last_frame = current_frame
                last_status = status
                yield f"data: {json.dumps(progress)}\n\n"

            if status == "COMPLETED" or status.startswith("FAILED"):
                break

            await asyncio.sleep(interval)
            elapsed += interval

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/videos")
def list_videos(db: Session = Depends(get_db)):
    """List all CCTV video entries."""
    videos = db.query(VideoRecord).order_by(VideoRecord.processed_at.desc()).all()
    return [
        {
            "id": v.id,
            "filename": v.filename,
            "filepath": v.filepath,
            "annotated_filepath": v.annotated_filepath,
            "status": v.status,
            "duration_sec": v.duration_sec,
            "total_frames": v.total_frames,
            "processed_at": v.processed_at.isoformat() if v.processed_at else None,
            "total_tracks": len(v.tracks),
            "total_events": len(v.events),
        }
        for v in videos
    ]


@router.get("/videos/{video_id}/tracks")
def get_video_tracks(video_id: str, db: Session = Depends(get_db)):
    """
    Return all tracks (with full trajectory & visual attributes) for a video.
    Used by the frontend multi-track canvas overlay to draw ALL bounding boxes
    simultaneously, with query-based colour-highlighting of matched tracks.
    """
    video = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    tracks_out = []
    for tr in video.tracks:
        trajectory = []
        if tr.trajectory_json:
            try:
                trajectory = json.loads(tr.trajectory_json)
            except Exception:
                trajectory = []

        visual_attributes: list = []
        if tr.visual_attributes_json:
            try:
                visual_attributes = json.loads(tr.visual_attributes_json)
            except Exception:
                visual_attributes = []

        tracks_out.append(
            {
                "track_id": tr.track_id,
                "class_name": tr.class_name,
                "first_seen_sec": round(tr.first_seen_sec, 2),
                "last_seen_sec": round(tr.last_seen_sec, 2),
                "duration_sec": round(tr.duration_sec, 2),
                "avg_speed_px_sec": round(tr.avg_speed_px_sec or 0.0, 2),
                "visual_attributes": visual_attributes,
                "trajectory": trajectory,
            }
        )

    return {
        "video_id": video_id,
        "video_width": video.width or 1920,
        "video_height": video.height or 1080,
        "total_tracks": len(tracks_out),
        "tracks": tracks_out,
    }


@router.get("/videos/{video_id}")
def get_video_details(video_id: str, db: Session = Depends(get_db)):
    """Get details of a specific video including its events and tracks."""
    video = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Map track_id to trajectory
    track_trajectories: dict[int, list] = {}
    for tr in video.tracks:
        if tr.trajectory_json:
            try:
                track_trajectories[tr.track_id] = json.loads(tr.trajectory_json)
            except Exception:
                track_trajectories[tr.track_id] = []

    events_list = []
    for ev in video.events:
        # Only expose clip_url when the clip file actually exists on disk
        clip_url: str | None = None
        if ev.clip_path:
            clip_file = Path(ev.clip_path)
            if clip_file.is_file() and clip_file.stat().st_size > 1024:
                clip_url = f"/api/v1/videos/{video.id}/clips/{ev.id}"

        events_list.append(
            {
                "event_id": ev.id,
                "video_id": video.id,
                "video_filename": video.filename,
                "track_id": ev.track_id,
                "class_name": ev.class_name,
                "event_type": ev.event_type,
                "start_time_sec": round(ev.start_time_sec, 2),
                "end_time_sec": round(ev.end_time_sec, 2),
                "duration_sec": round(max(0.0, ev.end_time_sec - ev.start_time_sec), 2),
                "confidence": round(ev.confidence, 4),
                "details": ev.details or "",
                "score": 1.0,
                "similarity": 1.0,
                "clip_url": clip_url,
                "video_url": f"/api/v1/videos/{video.id}/stream",
                "video_width": video.width or 1920,
                "video_height": video.height or 1080,
                "visual_attributes": json.loads(ev.visual_attributes_json) if ev.visual_attributes_json else [],
                "trajectory": track_trajectories.get(ev.track_id, []),
            }
        )

    return {
        "id": video.id,
        "filename": video.filename,
        "filepath": video.filepath,
        "annotated_filepath": video.annotated_filepath,
        "video_url": f"/api/v1/videos/{video.id}/stream",
        "status": video.status,
        "duration_sec": video.duration_sec,
        "total_frames": video.total_frames,
        "processed_at": video.processed_at.isoformat() if video.processed_at else None,
        "total_tracks": len(video.tracks),
        "total_events": len(video.events),
        "events": events_list,
    }


@router.post("/videos/{video_id}/reprocess")
def reprocess_video(video_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Re-run the YOLO + Pose + Gemini attribute pipeline on an existing video."""
    video = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not Path(video.filepath).is_file():
        raise HTTPException(status_code=400, detail="Original video file no longer exists on disk")

    video.status = "QUEUED"
    db.commit()

    background_tasks.add_task(run_video_pipeline, video_id)
    return {"video_id": video_id, "status": "QUEUED", "message": "Video queued for reprocessing with active detectors."}


@router.get("/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """Return live telemetry metrics, class distribution, and event stream from database."""
    total_videos = db.query(VideoRecord).count()
    completed_videos = db.query(VideoRecord).filter(VideoRecord.status == "COMPLETED").count()
    total_frames = db.query(func.sum(VideoRecord.total_frames)).scalar() or 0
    total_tracks = db.query(TrackRecord).count()
    total_events = db.query(EventRecord).count()

    class_counts = (
        db.query(TrackRecord.class_name, func.count(TrackRecord.id))
        .group_by(TrackRecord.class_name)
        .all()
    )
    total_class_items = sum(c[1] for c in class_counts) or 1
    class_breakdown = [
        {
            "name": name.capitalize(),
            "count": count,
            "pct": round((count / total_class_items) * 100, 1),
        }
        for name, count in sorted(class_counts, key=lambda x: x[1], reverse=True)
    ]

    recent_events_records = (
        db.query(EventRecord)
        .order_by(EventRecord.created_at.desc())
        .limit(5)
        .all()
    )
    recent_events = [
        {
            "id": ev.id,
            "title": f"{ev.event_type.replace('_', ' ').title()} - {ev.class_name.capitalize()}",
            "desc": ev.details or f"Track #{ev.track_id} in {ev.zone_name or 'monitored sector'}",
            "time": ev.created_at.strftime("%H:%M:%S") if ev.created_at else "Recently",
            "severity": "high" if any(k in ev.event_type for k in ("INTRUSION", "FAST", "LOITERING")) else "normal",
        }
        for ev in recent_events_records
    ]

    return {
        "total_videos": total_videos,
        "completed_videos": completed_videos,
        "total_frames": int(total_frames),
        "total_tracks": total_tracks,
        "total_events": total_events,
        "class_breakdown": class_breakdown,
        "recent_events": recent_events,
    }
