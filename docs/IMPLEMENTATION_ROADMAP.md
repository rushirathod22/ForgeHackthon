# ASK MY CCTV — Phased Implementation Roadmap

**Document Version**: 1.0.0  
**Date**: August 24, 2026  

---

## Roadmap Summary

```
   PHASE 0              PHASE 1              PHASE 2              PHASE 3              PHASE 4              PHASE 5
┌────────────┐      ┌────────────┐      ┌────────────┐      ┌────────────┐      ┌────────────┐      ┌────────────┐
│  PROJECT   │ ────►│ CORE API & │ ────►│ SEMANTIC   │ ────►│ SPATIAL    │ ────►│ SECURITY   │ ────►│ PRODUCTION │
│   AUDIT    │      │ BACKEND    │      │ VECTOR     │      │ MULTI-CAM  │      │ DISPATCH & │      │ HARDENING &│
│(Completed) │      │ HARDENING  │      │ SEARCH     │      │ RE-ID      │      │ CALLING    │      │ DEPLOYMENT │
└────────────┘      └────────────┘      └────────────┘      └────────────┘      └────────────┘      └────────────┘
```

---

## Phase Breakdown

### Phase 0: Project Audit & Architectural Specification (Completed)
- **Objective**: Conduct full repository analysis, document existing code, design system architecture, and map API contracts.
- **Status**: Completed.

---

### Phase 1: Core API & Backend Integration Hardening
- **Objective**: Connect React frontend state machine directly to live FastAPI backend endpoints (`/api/v1/search`, `/api/v1/videos/upload`, `/api/v1/videos/{id}/stream`), improve CORS/error handling, and resolve environment variables.
- **Scope**:
  - Connect React `handlePerformSearch()` to `POST /api/v1/search`.
  - Add video upload UI trigger in `Meet ASK` screen to `POST /api/v1/videos/upload`.
  - Add `.env` configuration for backend file paths and model weights.
  - Implement structured error handling and background task progress notifications.
- **Affected Files**:
  - `frontend/src/App.jsx`
  - `frontend/src/components/EvidenceViewer.jsx`
  - `backend/api/app.py`
  - `backend/api/routes/videos.py`
  - `backend/api/routes/search.py`
- **Acceptance Criteria**:
  - Search query in React frontend sends HTTP request to FastAPI and renders live returned video search results.
  - Video upload from UI successfully triggers background YOLO pipeline and displays status.
  - All existing unit tests pass.

---

### Phase 2: Enhanced AI Intelligence & Semantic Vector Search (Completed)
- **Objective**: Integrate Vision-Language Model (VLM) embeddings (e.g. OpenCLIP / CLIP) to allow zero-shot semantic visual search (e.g. *"white car with roof rack"*, *"person carrying red backpack"*).
- **Status**: Completed.
- **Scope Implemented**:
  - Added `VisualEmbeddingEngine` extracting normalized 128-dimensional dense visual vectors for frame crops and text queries.
  - Extended SQLite database models with `embedding_json` and auto-migration support.
  - Integrated frame cropping and track embedding generation into `CCTVDetector` and background video pipeline.
  - Enhanced `NLQueryParser` and `HybridRetriever` with multimodal cosine similarity ranking and score boosting.
  - Created 10 automated unit tests (`tests/test_embeddings.py` and `tests/test_search.py`), with all 27 backend tests passing.
  - Updated frontend `EvidenceViewer` HUD to render vector similarity confidence scores.

---

### Phase 3: Spatial Multi-Camera ReID & Person Journey Tracking
- **Objective**: Implement cross-camera target re-identification (ReID) to link object trajectories across multiple camera streams.
- **Scope**:
  - Feature extraction per track (ResNet ReID backbone).
  - Spatial-temporal graph connector calculating target movement velocity and journey timeline.
- **Affected Files**:
  - `backend/tracking/tracker.py`
  - `backend/events/detector.py`
  - `frontend/src/components/PersonJourney.jsx`

---

### Phase 4: Security Incident Dispatch & Calling Assistant Backend
- **Objective**: Connect AI Security Calling Assistant to real WebRTC / Twilio / SIP audio dispatch service and incident reporting DB.
- **Scope**:
  - Create `/api/v1/incidents` endpoint.
  - Implement audio streaming endpoint for AI dispatch voice calls.

---

### Phase 5: Production Readiness, Live RTSP Streaming & Deployment
- **Objective**: Containerize full stack with Docker Compose, add PostgreSQL database with pgvector, and support live RTSP camera stream ingestion.
