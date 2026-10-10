from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

try:
    from db.session import get_db
    from search.retriever import HybridRetriever
    from tracking.reid import CrossCameraReIDMatcher
except ModuleNotFoundError:
    from backend.db.session import get_db
    from backend.search.retriever import HybridRetriever
    from backend.tracking.reid import CrossCameraReIDMatcher

router = APIRouter(prefix="/api/v1", tags=["search"])
retriever = HybridRetriever()
reid_matcher = CrossCameraReIDMatcher()


class SearchQueryRequest(BaseModel):
    query: str
    video_id: str | None = None


@router.post("/search")
def search_footage(req: SearchQueryRequest, db: Session = Depends(get_db)):
    """Search processed CCTV footage using natural language queries."""
    results = retriever.search(db, req.query, video_id=req.video_id)
    return {
        "query": req.query,
        "results_count": len(results),
        "results": [r.to_dict() for r in results],
    }


@router.get("/tracks/{video_id}/{track_id}/journey")
def get_track_journey(video_id: str, track_id: int, db: Session = Depends(get_db)):
    """Retrieve multi-camera spatial journey for a target track using cross-camera ReID."""
    journey = reid_matcher.build_journey(db, video_id, track_id)
    return {
        "video_id": video_id,
        "track_id": track_id,
        "steps_count": len(journey),
        "journey": journey,
    }

