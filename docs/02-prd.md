# Product Requirements Document (PRD)

| Field | Value |
|---|---|
| Project | Ask My CCTV |
| Title | AI-Powered Natural Language CCTV Video Search and Event Detection System |
| Document Version | 2.0.0 (Enterprise Industry Specification) |
| Document Status | Approved for Development Baseline |
| Target Release | Phase 1 Baseline -> Phase 4 Enterprise Rollout |
| Engineering Owners | AI/ML Pipeline, Backend Platform, and Frontend UI Engineering Teams |

---

## 1. Executive Summary & Problem Rationale

Modern physical security installations produce thousands of hours of continuous closed-circuit television (CCTV) video daily across hundreds of IP cameras. Security personnel, law enforcement investigators, and facility operations managers face a severe operational bottleneck: **manual video scrubbing**.

### 1.1 Key Pain Points
* **High Operator Fatigue & Manual Scrubbing Burden**: Human operators experience severe cognitive decline within 20–30 minutes of continuous footage monitoring, missing up to 90% of critical visual events.
* **Primitive Metadata & Keyword Search Limitations**: Existing Video Management Systems (VMS) only index footage by coarse metadata (camera identifier, date, time). Locating specific events (e.g., *"Find a black SUV entering the south gate between 2:00 PM and 3:30 PM"*) requires manual playback across multiple video channels.
* **Evidence Chain of Custody & Traceability Gaps**: Exporting video clips for legal or internal audits frequently lacks tamper-evident hashing, structured metadata logs, or immutable timestamp correlation.

### 1.2 Product Vision & Value Proposition
**Ask My CCTV** transforms passive CCTV video archives into an interactive, natural-language searchable intelligence platform. Authorized users can query surveillance archives using natural English prompts, receive instantaneous ranked video clips with overlaid bounding boxes, and track unique object trajectories across multi-camera layouts while preserving strict legal chain-of-custody metadata.

---

## 2. Target User Personas & Usage Scenarios

| Persona | Primary Goal | Core Workflows | Pain Points Addressed |
|---|---|---|---|
| **Security Operator** | Real-time monitoring and immediate incident response | Real-time alert dashboard, ROI boundary monitoring, live clip playback | Removes need to watch 10+ screens simultaneously |
| **Forensic Investigator** | Rapid evidence collection and post-event analysis | Natural language search over historical archives, trajectory plotting, clip export | Reduces 10-hour manual search to under 30 seconds |
| **Security Supervisor** | Governance, compliance, and multi-camera oversight | System health monitoring, audit trail review, retention policy enforcement | Ensures strict legal evidence compliance and zero data loss |
| **System Administrator** | Platform stability, user access, and resource allocation | User RBAC management, GPU/worker scaling, camera RTSP registration | Simplifies deployment across edge and cloud infrastructure |

---

## 3. Product Scope & Multi-Phase Engineering Roadmap

```mermaid
flowchart LR
    subgraph P1[Phase 1: Detection Baseline]
        P1A[YOLO11 Object Detection]
        P1B[Local MP4 Frame I/O]
        P1C[Bounding Box Rendering]
    end
    subgraph P2[Phase 2: Multi-Object Tracking]
        P2A[ByteTrack ID Association]
        P2B[Trajectory Extraction]
        P2C[SQLite / PostgreSQL Storage]
    end
    subgraph P3[Phase 3: Hybrid NL Search Engine]
        P3A[CLIP Visual Embeddings]
        P3B[FAISS Vector Indexing]
        P3C[LLM Query Parsing]
    end
    subgraph P4[Phase 4: Enterprise Web Platform]
        P4A[FastAPI Async Backend]
        P4B[React + Canvas Canvas Dashboard]
        P4C[RTSP Ingestion & Security RBAC]
    end

    P1 --> P2 --> P3 --> P4
```

### 3.1 Phase 1 (Baseline Computer Vision Pipeline) - *Current Implementation*
* **In Scope**:
  * Local MP4 video file ingestion using OpenCV.
  * Inference with Ultralytics YOLO11 (`yolo11n.pt` / custom weights).
  * Road vehicle classification (COCO classes: `bicycle`, `car`, `motorcycle`, `bus`, `truck`).
  * Real-time bounding box, confidence score, and class label rendering.
  * Atomic output generation (`.part.mp4` temporary write before atomic rename).
  * Structured JSON execution metrics (total frames, detection density, per-class counts).

### 3.2 Phase 2 (Multi-Object Tracking & Persistence)
* Unique trajectory tracking via ByteTrack across frame sequences.
* Relational persistence of camera metadata, video chunks, and frame-level detections in SQLite/PostgreSQL.
* Polygon Region of Interest (ROI) crossing and stationary object detection.

### 3.3 Phase 3 (Natural Language & Vector Search Engine)
* Image snippet feature vector extraction using OpenAI CLIP (`ViT-B/32`).
* Approximate Nearest Neighbor (ANN) index generation via FAISS.
* Natural language text query parsing into structured SQL filter clauses and high-dimensional vector search queries.

### 3.4 Phase 4 (Enterprise Platform & Real-Time Orchestration)
* Asynchronous FastAPI backend providing RESTful endpoints and WebSocket live notification streams.
* Modern React + Vite frontend featuring a video player with canvas overlays, timeline scrubbers, and query builders.
* RTSP live stream ingestion worker queue, role-based access control (RBAC), SHA-256 evidence hashing, and privacy redacting/masking.

---

## 4. Key Performance Indicators (KPIs) & Target SLAs/SLOs

| Category | Metric / Target | Benchmark Threshold | Measurement Method |
|---|---|---|---|
| **CV Precision** | Vehicle Detection Precision | $\ge 92.5\%$ mAP@50 | Labeled evaluation dataset |
| **CV Recall** | Vehicle Detection Recall | $\ge 89.0\%$ mAP@50-95 | Benchmark test suite |
| **Inference FPS** | Frame Processing Throughput | $\ge 60$ FPS (GPU CUDA) / $\ge 25$ FPS (CPU) | Frame execution timer |
| **Search Latency** | Natural Language Query Time | $\le 500$ ms for 100,000 indexed frames | End-to-end API response timer |
| **UI Responsiveness** | Bounding Box Overlay Latency | $< 16$ ms (smooth 60Hz rendering) | Web canvas profiler |
| **System Uptime** | Platform Availability | $99.9\%$ uptime | Production health monitor |

---

## 5. Non-Functional & Quality Requirements

* **Reliability & Atomic Operations**: Frame processing failures or stream drops must not publish corrupt or incomplete video files.
* **Reproducibility**: Every detection record must bind the exact model checkpoint hash, confidence threshold, and framework version.
* **Security & Auditability**: All queries, clip downloads, and user authentications must record structured audit events with SHA-256 integrity verification.
* **Data Minimization & Retention**: Storage managers must execute automatic pruning of expired video chunks while preserving metadata and audit logs per regional compliance policies.

---

## 6. Product Risks & Mitigation Strategy

| Risk ID | Risk Description | Severity | Mitigation Strategy |
|---|---|---|---|
| **R-01** | Model false positives under heavy rain / night lighting | High | Fine-tune YOLO11 on night/rain CCTV datasets; expose operator confidence sliders in UI. |
| **R-02** | High GPU memory consumption with multi-camera streams | High | Implement frame-skipping heuristics (e.g., infer every $N$-th frame) and asynchronous worker queues. |
| **R-03** | Incomplete temporary video files left on disk after power loss | Medium | Write to isolated `.part` temporary files; execute atomic cleanup routines on service startup. |
| **R-04** | Privacy concerns regarding unredacted bystander footage | High | Implement dynamic bounding-box privacy blur/masking on export for non-target subjects. |
