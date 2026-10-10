from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

try:
    from api.app import app
    from db.session import init_db
except ModuleNotFoundError:
    from backend.api.app import app
    from backend.db.session import init_db

# Ensure database tables are created for API test suite
init_db()

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Ask My CCTV Engine"


def test_list_videos_endpoint() -> None:
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_search_endpoint() -> None:
    response = client.post("/api/v1/search", json={"query": "show fast moving cars"})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["query"] == "show fast moving cars"


def test_video_details_and_stream_head() -> None:
    # First get list of videos
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    vids = response.json()
    if vids:
        vid_id = vids[0]["id"]
        # Test GET details
        detail_res = client.get(f"/api/v1/videos/{vid_id}")
        assert detail_res.status_code == 200
        data = detail_res.json()
        assert data["id"] == vid_id
        assert "events" in data

        # Test HEAD on stream
        head_res = client.head(f"/api/v1/videos/{vid_id}/stream")
        assert head_res.status_code in (200, 206)
        assert "video/mp4" in head_res.headers.get("content-type", "")


def test_track_reid_journey_endpoint() -> None:
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    vids = response.json()
    if vids:
        vid_id = vids[0]["id"]
        res = client.get(f"/api/v1/tracks/{vid_id}/1/journey")
        assert res.status_code == 200
        data = res.json()
        assert "journey" in data
        assert isinstance(data["journey"], list)


def test_stats_endpoint() -> None:
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_videos" in data
    assert "total_frames" in data
    assert "total_tracks" in data
    assert "class_breakdown" in data
    assert isinstance(data["class_breakdown"], list)


