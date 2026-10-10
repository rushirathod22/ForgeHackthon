# ASK MY CCTV — System Architecture Specification

**Document Version**: 1.0.0  
**Date**: August 24, 2026  

---

## 1. System Overview & Layered Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND LAYER (React 19 + Vite)                  │
│                                                                             │
│  ┌──────────────┐   ┌──────────────────┐   ┌─────────────────────────────┐  │
│  │ Meet ASK     │   │ Camera Universe  │   │ Evidence & Timeline Stage   │  │
│  │ (Canvas Orb) │   │ (Node Graph)     │   │ (Video HUD + Reticle)       │  │
│  └──────┬───────┘   └────────┬─────────┘   └──────────────┬──────────────┘  │
│         │                    │                            │                 │
│  ┌──────┴────────────────────┴────────────────────────────┴──────────────┐  │
│  │                 Fluid AI OS Master State Engine (App.jsx)              │  │
│  │                     & Floating Glass Navigation Dock                  │  │
│  └───────────────────────────────────┬───────────────────────────────────┘  │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │ HTTP / REST API
┌──────────────────────────────────────┴──────────────────────────────────────┐
│                           BACKEND SERVICE LAYER (FastAPI)                   │
│                                                                             │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐ │
│  │ Videos & Upload API   │  │ Search & Query API    │  │ Evidence Clips  │ │
│  │ /api/v1/videos        │  │ /api/v1/search        │  │ /api/v1/clips   │ │
│  └──────────┬────────────┘  └──────────┬────────────┘  └────────┬────────┘ │
│             │                          │                        │          │
│  ┌──────────┴──────────────────────────┴────────────────────────┴────────┐ │
│  │                       Background Pipeline Executor                    │ │
│  └──────┬──────────────────────────────┬─────────────────────────┬───────┘ │
└─────────┼──────────────────────────────┼─────────────────────────┼─────────┘
          │                              │                         │
┌─────────┴─────────────┐  ┌─────────────┴────────────┐  ┌─────────┴─────────┐
│     AI PIPELINE       │  │    SEARCH ENGINE         │  │    STORAGE      │
│  - YOLO11 Detector    │  │  - NL Query Parser      │  │  - SQLite / DB  │
│  - CCTVTracker (IoU)  │  │  - HybridRetriever      │  │  - Video Files  │
│  - EventDetector (ROI)│  │  - Keyword & Synonyms   │  │  - JSON Meta    │
└───────────────────────┘  └──────────────────────────┘  └─────────────────┘
```

---

## 2. Component Subsystems

### 2.1 Frontend Subsystem (`frontend/src/`)
- **App.jsx**: Orchestrates master state machine (`currentScreen` 1 through 8), handles speech input/output, and renders active screen layers.
- **AiOrbCanvas.jsx**: Renders dynamic HTML5 canvas AI orb with mode-dependent colors, wave rings, holographic core, and particle dust.
- **CameraUniverse.jsx**: Organic 2D SVG constellation mesh representing camera nodes (`CAM_01` to `CAM_11`) with animated neural pulses and match activation.
- **EvidenceViewer.jsx**: Video player stage with bounding box overlay reticle, metadata HUD, interactive timeline step markers, and integrated AI explanation block.
- **PersonJourney.jsx**: Multi-camera spatial movement path connecting check-in timestamps with video preview cards.
- **SecurityCallAssistant.jsx**: Live security officer call interface with real-time responsive CSS audio waveform and structured transcript.
- **FloatingDock.jsx**: Floating glass navigation bar and stage controller.

### 2.2 Backend Subsystem (`backend/api/`)
- **FastAPI Core (`app.py`)**: Async server with CORS middleware, lifespan database initialization, and static file mounting.
- **Routes (`backend/api/routes/`)**:
  - `videos.py`: Handles `/videos/upload`, `/videos/register`, `/videos` list, `/jobs/{job_id}` status, and background thread execution.
  - `search.py`: Handles natural language search requests via `/search`.
  - `clips.py`: Handles file streaming for evidence clips and full annotated videos via `/videos/{id}/clips/{clip_id}` and `/videos/{id}/stream`.

### 2.3 AI Pipeline Subsystem (`backend/detection/`, `tracking/`, `events/`)
- **YOLO11 Object Detector (`detect.py`)**: Executes frame-by-frame inference using `yolo11n.pt` for target object classes.
- **Persistent CCTV Tracker (`tracker.py`)**: Performs multi-object tracking using IoU bounding box matching, storing trajectories, velocities, distance, and duration.
- **Event Detector (`events/detector.py`)**: Evaluates trajectories against spatial ROI polygons and thresholds (`ZONE_INTRUSION`, `LOITERING`, `FAST_MOVEMENT`, `STOPPED_VEHICLE`).
- **Clip Exporter (`events/clip_exporter.py`)**: Cuts MP4 video segments with temporal padding using OpenCV.

### 2.4 Database & Persistence Schema (`backend/db/`)
- **CameraRecord**: `id`, `name`, `location`, `status`, `created_at`.
- **VideoRecord**: `id`, `camera_id`, `filename`, `filepath`, `annotated_filepath`, `duration_sec`, `fps`, `total_frames`, `status`.
- **TrackRecord**: `id`, `video_id`, `track_id`, `class_name`, `first_seen_sec`, `last_seen_sec`, `duration_sec`, `avg_speed_px_sec`, `trajectory_json`.
- **EventRecord**: `id`, `video_id`, `track_id`, `event_type`, `class_name`, `start_time_sec`, `end_time_sec`, `confidence`, `zone_name`, `details`, `clip_path`.
