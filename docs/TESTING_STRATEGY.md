# ASK MY CCTV — Testing Strategy Specification

**Document Version**: 1.0.0  
**Date**: August 24, 2026  

---

## 1. Test Architecture Overview

Testing for **ASK MY CCTV** covers unit testing, API integration testing, computer vision pipeline validation, and frontend component testing.

```
                  ┌─────────────────────────────────┐
                  │      End-to-End UI Tests        │
                  │   (Playwright / Cypress)        │
                  └────────────────┬────────────────┘
                                   │
                  ┌────────────────┴────────────────┐
                  │    API & Service Tests          │
                  │    (Pytest + HTTPX Client)      │
                  └────────────────┬────────────────┘
                                   │
      ┌────────────────────────────┴────────────────────────────┐
      │                                                         │
┌─────┴───────────────────────────┐         ┌───────────────────┴───────────────────┐
│     AI Computer Vision Tests    │         │      Frontend Component Tests         │
│  - Object Detection (YOLO11)    │         │   - React 19 State Machine (App.test) │
│  - Multi-Object Tracker (IoU)   │         │   - HTML5 Canvas Orb (AiOrb.test)    │
│  - Event Engine (ROI Polygons)  │         │   - Camera Universe Node Graph        │
└─────────────────────────────────┘         └───────────────────────────────────────┘
```

---

## 2. Test Suites

### 2.1 API Integration Tests (`backend/tests/test_api.py`)
- Test `/health` endpoint returns `200 OK`.
- Test `/api/v1/videos/upload` returns queued job ID.
- Test `/api/v1/videos/register` verifies path existence and returns 404 for invalid paths.
- Test `/api/v1/search` returns query results matching requested criteria.

### 2.2 Computer Vision & Tracker Tests (`backend/tests/test_detection.py`, `test_tracking.py`)
- Test `CCTVTracker` correctly assigns unique track IDs across consecutive frames.
- Test IoU matching calculation for overlapping vs non-overlapping bounding boxes.
- Test trajectory calculation and average velocity estimations.

### 2.3 Event Engine Tests (`backend/tests/test_events.py`)
- Test `ZoneROI.contains_point()` ray-casting algorithm on concave and convex polygons.
- Test `EventDetector` triggers `ZONE_INTRUSION`, `LOITERING`, `FAST_MOVEMENT`, and `STOPPED_VEHICLE` events when thresholds are breached.

### 2.4 Query Parser Tests (`backend/tests/test_search.py`)
- Test `NLQueryParser` correctly maps class synonyms (`car`, `sedan`, `vehicle`, `people`, `man`).
- Test time range pattern extraction (`after 10s`, `before 30s`).

---

## 3. Test Commands Execution

### Backend Pytest Suite
```bash
cd backend
pytest -v
```

### Frontend Build & Lint Checks
```bash
cd frontend
npm run lint
npm run build
```
