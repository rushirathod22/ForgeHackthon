from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

try:
    from db.models import EventRecord, VideoRecord
    from db.session import get_db
except ModuleNotFoundError:
    from backend.db.models import EventRecord, VideoRecord
    from backend.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["clips"])


@router.api_route("/videos/{video_id}/clips/{clip_id}", methods=["GET", "HEAD"])
def get_evidence_clip(video_id: str, clip_id: str, db: Session = Depends(get_db)):
    """Stream or download an evidence clip file."""
    event = db.query(EventRecord).filter(EventRecord.id == clip_id, EventRecord.video_id == video_id).first()
    if not event or not event.clip_path:
        raise HTTPException(status_code=404, detail="Evidence clip not found")

    clip_file = Path(event.clip_path)
    if not clip_file.is_file():
        raise HTTPException(status_code=404, detail=f"Clip file missing on disk: '{event.clip_path}'")

    return FileResponse(
        path=clip_file,
        media_type="video/mp4",
        content_disposition_type="inline",
    )


@router.api_route("/videos/{video_id}/stream", methods=["GET", "HEAD"])
def stream_processed_video(video_id: str, db: Session = Depends(get_db)):
    """Stream the full CCTV video with native HTML5 browser support."""
    video = db.query(VideoRecord).filter(VideoRecord.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video record not found")

    # Browser playback is most reliable with the original upload, which is commonly H.264.
    # OpenCV's annotated MP4 writer often emits FMP4/mp4v streams that Chrome renders black.
    video_file = Path(video.filepath)
    if not video_file.is_file():
        if video.annotated_filepath and Path(video.annotated_filepath).is_file():
            video_file = Path(video.annotated_filepath)
        else:
            raise HTTPException(status_code=404, detail=f"Video file missing: '{video.filepath}'")

    return FileResponse(
        path=video_file,
        media_type="video/mp4",
        content_disposition_type="inline",
    )
