# System Architecture Document

| Field | Value |
|---|---|
| Project | Ask My CCTV |
| Document Version | 2.0.0 (Enterprise Architecture Blueprint) |
| Architecture Style | Microservices & Event-Driven Asynchronous Pipeline |
| Status | Approved Architecture |

---

## 1. Architectural Principles

1. **Separation of Media Ingestion & Analytics**: Frame demuxing and video streaming must remain strictly decoupled from deep-learning inference, tracking, and vector indexing.
2. **Immutability of Original Footage**: Source CCTV streams and video files are treated as read-only evidence. Derived artifacts (annotations, cropped object snippets, vectors) are indexed separately.
3. **Metadata-First Querying**: Search operations execute over indexed scalar metadata (SQL) and vector embeddings (FAISS) without touching raw video binaries during query processing.
4. **Fault-Tolerant Asynchronous Execution**: All heavy processing tasks execute within isolated background workers with idempotent state recovery.

---

## 2. High-Level System Context (C4 Level 1)

```mermaid
C4Context
    title System Context Diagram for Ask My CCTV

    Person(operator, "Security Operator / Investigator", "Searches CCTV archives using natural language, monitors real-time alerts, exports video evidence.")
    System(ask_cctv, "Ask My CCTV System", "AI-powered natural language CCTV video search and event detection platform.")
    System_Ext(cctv_cameras, "IP CCTV Camera Network", "Continuous RTSP / H.264 video streams.")
    System_Ext(idp, "Identity Provider (OIDC)", "Authenticates system users and issues OAuth2 JWT tokens.")

    Rel(operator, ask_cctv, "Searches queries, views live overlays, exports clips", "HTTPS / WSS")
    Rel(cctv_cameras, ask_cctv, "Streams raw video channels", "RTSP / RTP")
    Rel(ask_cctv, idp, "Validates user tokens and roles", "HTTPS")
```

---

## 3. Container & Component Architecture (C4 Level 2 & 3)

```mermaid
flowchart TB
    subgraph Client Tier
        UI[React + Vite Web Dashboard]
        CANVAS[HTML5 Canvas Overlay Engine]
    end

    subgraph API & Gateway Tier
        GATEWAY[FastAPI Gateway Services]
        AUTH[JWT Authentication & RBAC Filter]
        WS[WebSocket Real-Time Event Pusher]
    end

    subgraph Analytics & AI Worker Pipeline
        INGEST_WORKER[Video Ingestion & Demuxer Worker]
        CV_WORKER[YOLO11 Object Detector Worker]
        TRACK_WORKER[ByteTrack Multi-Object Tracker]
        CLIP_WORKER[CLIP Embedding Generator]
    end

    subgraph Storage & Indexing Tier
        FAISS_INDEX[(FAISS Vector Index)]
        PG_DB[(PostgreSQL / SQLite Metadata)]
        REDIS[(Redis Message Queue & Cache)]
        OBJECT_STORE[(S3 / Local Media Store)]
    end

    UI <--> CANVAS
    UI <--> GATEWAY
    UI <--> WS

    GATEWAY --> AUTH
    AUTH --> PG_DB
    GATEWAY --> REDIS
    WS <--> REDIS

    INGEST_WORKER --> OBJECT_STORE
    INGEST_WORKER --> REDIS
    REDIS --> CV_WORKER
    CV_WORKER --> TRACK_WORKER
    TRACK_WORKER --> CLIP_WORKER

    CLIP_WORKER --> FAISS_INDEX
    TRACK_WORKER --> PG_DB
    CV_WORKER --> PG_DB
```

---

## 4. Subsystem Component Specification

### 4.1 Ingestion & Demuxing Subsystem
* **Responsibility**: Ingests multi-format RTSP streams and static MP4 files, demuxes streams into standardized $1080\text{p}$ RGB frames, and computes hardware timestamps.
* **Technology**: OpenCV `VideoCapture`, FFmpeg C API bindings.

### 4.2 Computer Vision Engine (`backend/detection`)
* **Responsibility**: Runs object detection across frames using YOLO11, filters target classes, and computes bounding boxes.
* **Technology**: PyTorch, Ultralytics YOLO11, TensorRT execution backend.

### 4.3 Multi-Object Tracking & Event Engine (`backend/tracking`, `backend/events`)
* **Responsibility**: Connects detections across consecutive frames to form unique trajectories (`track_id`), evaluates spatial polygon crossing (ROI), and logs stationary or unauthorized movement events.
* **Technology**: ByteTrack algorithm, Shapely geometric polygon library.

### 4.4 Vector Search Engine (`backend/search`)
* **Responsibility**: Encodes object crop snippets into 512-dimensional vector embeddings, maintains FAISS Index FlatIP / HNSW, and executes natural language text query matching.
* **Technology**: OpenAI CLIP (`ViT-B/32`), FAISS C++ Python bindings.

### 4.5 API Service & Persistence Layer (`backend/api`, `backend/db`)
* **Responsibility**: Exposes OpenAPI REST endpoints, manages PostgreSQL/SQLite metadata connections, enforces security policy, and pushes live WebSocket events.
* **Technology**: FastAPI, SQLAlchemy ORM, Pydantic v2, Redis pub/sub.

---

## 5. End-to-End Data Flow (Sequence Diagram)

```mermaid
sequenceDiagram
    autonumber
    participant Camera as IP Camera / File
    participant Ingest as Ingestion Worker
    participant CV as YOLO11 / ByteTrack
    participant Vector as CLIP + FAISS
    participant DB as PostgreSQL
    participant API as FastAPI Gateway
    participant User as Investigator UI

    Camera->>Ingest: Stream video frames (RTSP/MP4)
    Ingest->>CV: Forward raw frame buffer
    CV->>CV: Detect vehicles & assign Track IDs
    CV->>Vector: Forward object cropped image snippets
    Vector->>Vector: Generate 512d CLIP vectors & update FAISS index
    CV->>DB: Insert detection & track records
    User->>API: POST /api/v1/search ("Red truck at main entrance")
    API->>Vector: Parse query text to vector & query FAISS
    Vector-->>API: Return top-k matched track IDs
    API->>DB: Fetch timestamped metadata & clip references
    API-->>User: Return JSON result payload with clip URLs & canvas bounding boxes
```

---

## 6. Security Boundaries & Trust Zones

| Boundary | Security Controls Implemented |
|---|---|
| **Ingestion Trust Zone** | Strict stream decoding sandboxing, RTSP authentication credentials stored in secure environment vaults. |
| **API Gateway Boundary** | HTTPS TLS 1.3 enforced, OAuth2/JWT token validation, rate-limiting ($100$ req/min). |
| **Media Storage Boundary** | Signed, short-lived evidence URLs (expiry $15$ mins), AES-256 server-side encryption at rest. |
| **Audit & Governance Zone** | Read-only append-only audit log database tables with SHA-256 verification. |
