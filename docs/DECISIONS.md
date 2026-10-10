# ASK MY CCTV — Architecture Decision Records (ADR)

**Document Version**: 1.0.0  
**Date**: August 24, 2026  

---

## ADR 001: Selection of FastAPI for Backend Framework

### Status
Accepted

### Context
We required a high-performance Python web framework capable of handling asynchronous background tasks, streaming MP4 video files, serving REST APIs, and running AI computer vision pipelines.

### Decision
Choose **FastAPI** with **Uvicorn** ASGI server.

### Consequences
- High request throughput with native `asyncio` support.
- Automatic OpenAPI/Swagger documentation generation.
- Built-in Pydantic v2 data validation and `BackgroundTasks` execution.

---

## ADR 002: Object Detection Model Architecture (YOLO11)

### Status
Accepted

### Context
Real-time CCTV processing requires object detection models with high frame-per-second (FPS) throughput and accurate bounding box generation for vehicles, pedestrians, and safety gear.

### Decision
Use **Ultralytics YOLO11 Nano (`yolo11n.pt`)**.

### Consequences
- Fast inference speed (~60+ FPS on GPU, ~25+ FPS on CPU).
- Pretrained on COCO dataset classes.
- Option to fine-tune custom weights for specific CCTV attributes (helmets, vests, vehicle license plates).

---

## ADR 003: IoU Multi-Object Persistent Tracking

### Status
Accepted

### Context
Tracking objects across frames requires persistent IDs to compute trajectory paths, velocities, and duration without incurring high computation overhead from complex re-identification neural networks on single-camera streams.

### Decision
Implement a customized **Intersection over Union (IoU) CCTVTracker**.

### Consequences
- Lightweight, deterministic frame-to-frame matching.
- Calculates trajectory velocity vectors and duration thresholds without GPU overhead.
- Can be extended with Deep ReID embeddings in Phase 3 for multi-camera cross-stream tracking.

---

## ADR 004: Fluid AI Operating System UI Architecture

### Status
Accepted

### Context
Traditional CCTV platforms rely on dense, complex dashboards with static video grids and cluttered sidebar metrics. User requirements specify an original, human-centric, fluid AI operating system experience.

### Decision
Build a React 19 fluid state machine driving 8 evolving screens (`Meet ASK`, `AI Understanding`, `Camera Universe`, `Magical Transition`, `Evidence Stage`, `AI Explanation`, `Person Journey`, `AI Security Call Assistant`).

### Consequences
- Replaces traditional dashboard UI with a conversational AI workspace.
- Seamless transitions between AI understanding, camera network search, evidence reveal, spatial journey reconstruction, and security dispatch.
