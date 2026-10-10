# ASK MY CCTV — Project Audit

**Document Status**: Complete (Phase 0 Audit)  
**Date**: August 24, 2026  
**Auditor**: Senior Full-Stack AI System Architect  

---

## 1. Executive Summary

**ASK MY CCTV** is an AI-powered CCTV video intelligence platform designed to enable natural language interaction, automated video surveillance analytics, persistent multi-object tracking, security event detection, multi-camera spatial re-identification, and automated security incident response.

This audit presents a comprehensive analysis of the existing codebase, architecture, AI pipelines, database schemas, API routes, frontend components, technical debt, and security considerations.

---

## 2. Repository Structure Analysis

```
ASK_my_CC_TV/
├── backend/
│   ├── api/
│   │   ├── app.py                # FastAPI application entrypoint & CORS middleware
│   │   └── routes/
│   │       ├── clips.py          # Evidence clip streaming API
│   │       ├── search.py         # Natural language video search API
│   │       └── videos.py         # Video upload, registration, list & background pipeline
│   ├── db/
│   │   ├── models.py             # SQLAlchemy models (CameraRecord, VideoRecord, TrackRecord, EventRecord)
│   │   └── session.py            # SQLite database engine & session dependency
│   ├── detection/
│   │   ├── detect.py             # CCTVDetector class with YOLO11 integration & video rendering
│   │   └── metadata_exporter.py # JSON metadata exporter for frame detections
│   ├── events/
│   │   ├── clip_exporter.py      # OpenCV sub-clip extraction utility
│   │   └── detector.py           # EventDetector (LOITERING, FAST_MOVEMENT, ZONE_INTRUSION, STOPPED_VEHICLE)
│   ├── search/
│   │   ├── query_parser.py       # Regex & synonym natural language query parser
│   │   └── retriever.py          # HybridRetriever combining DB filtering & relevance scoring
│   ├── tracking/
│   │   └── tracker.py            # CCTVTracker (IoU-based multi-object persistent tracking)
│   ├── tests/                    # Pytest test suite (5 test modules)
│   ├── cctv_metadata.db          # SQLite database file
│   ├── pyproject.toml            # Python dependencies (OpenCV, Ultralytics, FastAPI, SQLAlchemy)
│   └── yolo11n.pt                # Pretrained YOLO11 Nano weights
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── AiOrbCanvas.jsx          # Interactive HTML5 Canvas AI orb presence
│   │   │   ├── CameraUniverse.jsx       # 2D/3D organic CCTV network node constellation
│   │   │   ├── EvidenceViewer.jsx       # Minimal cinematic video viewer with AI reticle
│   │   │   ├── FloatingDock.jsx         # Glass floating navigation bar & stage controller
│   │   │   ├── PersonJourney.jsx        # Multi-camera spatial movement path visualizer
│   │   │   └── SecurityCallAssistant.jsx# AI Security dispatch with reactive waveform
│   │   ├── App.jsx                      # Master 8-screen fluid AI OS state machine
│   │   ├── App.css                      # Ultra-pro dark aesthetic styling
│   │   └── index.css                    # Design system tokens & global styling
│   ├── package.json                     # Vite + React 19 + Lucide-react
│   └── vite.config.js                   # Vite configuration
├── videos/
│   ├── input/                   # Raw CCTV video files (e.g. test_cctv.mp4)
│   ├── processed/               # Annotated CCTV videos & JSON metadata
│   └── clips/                   # Extracted event clips
└── docs/                        # System architecture & PRD documentation
```

---

## 3. Technology Stack & Dependencies

| Layer | Component / Tool | Version / Details | Status |
| :--- | :--- | :--- | :--- |
| **Backend Framework** | FastAPI + Uvicorn | `fastapi>=0.110.0`, `uvicorn>=0.28.0` | Working |
| **Database** | SQLite + SQLAlchemy ORM | `sqlalchemy>=2.0.0` | Working (Development) |
| **AI / Object Detection** | Ultralytics YOLO11 Nano | `ultralytics>=8.4.121` (`yolo11n.pt`) | Working |
| **Computer Vision** | OpenCV Python | `opencv-python>=4.10.0` | Working |
| **Validation / Schemas** | Pydantic v2 | `pydantic>=2.0.0` | Working |
| **Frontend Framework** | React 19 + Vite | `react^19.2.8`, `vite^8.2.0` | Working |
| **Icons & UI** | Lucide React | `lucide-react^1.33.0` | Working |
| **Testing** | Pytest + HTTPX | `pytest>=9.1.1`, `httpx>=0.27.0` | Working |

---

## 4. Current Functionality Audit

### What Already Works (Verified)
1. **YOLO11 Video Object Detection & Persistent Tracking**:
   - `CCTVDetector` processes MP4 video files frame-by-frame.
   - `CCTVTracker` maintains object IDs across frames using IoU matching, tracking bounding boxes, velocities, and trajectory trails.
2. **Rule-Based Event Engine**:
   - `EventDetector` detects security events:
     - `ZONE_INTRUSION` (Ray-casting polygon point-in-polygon detection)
     - `LOITERING` (Duration threshold inside ROI)
     - `FAST_MOVEMENT` (Velocity threshold in px/sec)
     - `STOPPED_VEHICLE` (Stationary duration threshold)
3. **Automated Clip Extraction**:
   - `ClipExporter` cuts sub-video clips with temporal padding around detected events using OpenCV.
4. **Natural Language Query Parser & Retriever**:
   - `NLQueryParser` extracts target classes (`person`, `car`, `truck`, `bus`, `motorcycle`) and event types using synonym dictionary matching.
   - `HybridRetriever` filters SQL database records and returns ranked `SearchResult` objects.
5. **Fluid AI OS Frontend**:
   - React application with master 8-screen fluid state machine.
   - Dynamic HTML5 Canvas AI core (`ASK`), organic node-graph camera universe, minimal evidence stage, multi-camera person journey path, and AI security call mode.

---

## 5. Incomplete, Broken, or Missing Features

| Feature | Current State | Deficit / Risk | Recommended Action |
| :--- | :--- | :--- | :--- |
| **LLM / VLM Semantic Embedding** | Synonym keyword search only | Cannot process complex visual queries like *"white car with broken headlight"* or *"person carrying red backpack"* | Integrate Vision-Language Embeddings (e.g. CLIP / MobileVLM / OpenCLIP) |
| **Multi-Camera ReID** | Simulated mock journey checkpoints | Single-camera tracking is functional; multi-camera cross-node re-identification is not yet connected to a ReID model | Implement Deep ReID feature embeddings (ResNet/OSNet) |
| **Database Scalability** | Single SQLite database file (`cctv_metadata.db`) | SQLite locks on concurrent background processing writes | Migrate to PostgreSQL with `pgvector` for vector embeddings |
| **Real-time RTSP/HLS Ingestion** | Offline MP4 file ingestion only | Unable to handle live CCTV RTSP stream inputs | Add OpenCV/FFmpeg RTSP stream worker thread pool |
| **Frontend-Backend Integration** | Frontend uses client-side state machine with mock endpoints | Frontend is visually complete but needs full REST API integration for real video uploads & searches | Wire API endpoints (`/api/v1/search`, `/api/v1/videos/upload`) into React state |
| **Authentication & RBAC** | None | Public API endpoints with no user roles or authorization | Implement JWT authentication and role-based access control |

---

## 6. Existing API Endpoints Overview

| Method | Endpoint | Description | Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | Service health check | Operational |
| `POST` | `/api/v1/videos/upload` | Upload MP4 video file and start background worker | Operational |
| `POST` | `/api/v1/videos/register` | Register existing server video file for processing | Operational |
| `GET` | `/api/v1/videos` | List all processed/queued CCTV videos | Operational |
| `GET` | `/api/v1/jobs/{job_id}` | Check status of video processing job | Operational |
| `POST` | `/api/v1/search` | Search video evidence via natural language query | Operational |
| `GET` | `/api/v1/videos/{id}/clips/{clip_id}` | Stream extracted MP4 evidence clip | Operational |
| `GET` | `/api/v1/videos/{id}/stream` | Stream full annotated MP4 CCTV video | Operational |

---

## 7. Technical Debt & Security Risks

1. **Synchronous File IO in Async Routes**: Video uploads copy files to disk synchronously inside route handlers; should use chunked async stream writing.
2. **CORS Permissiveness**: `allow_origins=["*"]` allows any web domain to access endpoints; needs domain whitelisting.
3. **Hardcoded Model & Directory Paths**: Paths derived relative to file locations without environment variable overrides (`.env`).
4. **Error Handling & Rollbacks**: Unhandled exceptions in background workers set job status to `FAILED: <msg>` but don't clean up partial files on disk.

---

## 8. Summary & Next Steps

The existing repository has a solid computer vision foundation (YOLO11 + IoU tracking + Rule-based events + FastAPI) and a pro-designer AI OS frontend. Phase 0 audit is complete. Phase 1 will focus on API/Database hardening, environmental configuration, and connecting the frontend to live backend endpoints.
