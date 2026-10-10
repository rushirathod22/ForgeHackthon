# OpenAPI 3.0 REST & WebSocket API Specification

| Field | Value |
|---|---|
| Project | Ask My CCTV |
| Document Version | 2.0.0 (Production API Specification) |
| Protocol | HTTPS (REST) & WSS (WebSockets) |
| Base URL | `/api/v1` |
| Auth Scheme | Bearer Token (OAuth2 / JWT) |

---

## 1. OpenAPI 3.0 Endpoint Definitions

### 1.1 `POST /api/v1/videos/upload`
Uploads a local CCTV video file for processing.

* **Headers**: `Authorization: Bearer <JWT>`, `Content-Type: multipart/form-data`
* **Request Body**:
  ```yaml
  file: binary (MP4 video)
  camera_id: string (UUID)
  start_time: string (ISO-8601 timestamp)
  ```
* **Response `202 Accepted`**:
  ```json
  {
    "job_id": "b3c9f28a-7d12-4e5a-89a1-0f1122334455",
    "video_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
    "status": "QUEUED",
    "message": "Video accepted for detection and indexing pipeline."
  }
  ```

---

### 1.2 `GET /api/v1/jobs/{job_id}`
Retrieves detection processing progress and status.

* **Response `200 OK`**:
  ```json
  {
    "job_id": "b3c9f28a-7d12-4e5a-89a1-0f1122334455",
    "status": "COMPLETED",
    "progress_percent": 100.0,
    "metrics": {
      "total_frames": 1800,
      "processed_frames": 1800,
      "frames_with_detections": 450,
      "class_counts": {
        "car": 312,
        "truck": 42,
        "bus": 12
      },
      "processing_time_seconds": 18.5,
      "average_fps": 97.3
    }
  }
  ```

---

### 1.3 `POST /api/v1/search`
Executes natural language visual search over indexed footage.

* **Request Body**:
  ```json
  {
    "query": "Find a white delivery truck near main gate after 2 PM",
    "camera_ids": ["c1a2b3c4-d5e6-7f8a-9b0c-1d2e3f4a5b6c"],
    "start_time": "2026-08-23T14:00:00Z",
    "end_time": "2026-08-23T18:00:00Z",
    "top_k": 10,
    "confidence_threshold": 0.60
  }
  ```
* **Response `200 OK`**:
  ```json
  {
    "query_parsed": {
      "text_prompt": "white delivery truck",
      "target_classes": ["truck", "car"],
      "time_range": {"start": "2026-08-23T14:00:00Z", "end": "2026-08-23T18:00:00Z"}
    },
    "total_matches": 3,
    "results": [
      {
        "video_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        "camera_code": "CAM_GATE_01",
        "timestamp": "2026-08-23T14:15:32Z",
        "frame_index": 450,
        "similarity_score": 0.892,
        "bbox": [120.5, 340.0, 480.2, 720.0],
        "class_name": "truck",
        "clip_url": "/api/v1/videos/a1b2/clips/c450.mp4"
      }
    ]
  }
  ```

---

### 1.4 `GET /api/v1/videos/{video_id}/clips/{clip_id}`
Requests an authorized evidence clip.

* **Response `200 OK`**: Video stream (`video/mp4`) with SHA-256 header.
* **Headers**: `X-Evidence-SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

---

## 2. WebSocket Real-Time Event Stream (`WS /api/v1/ws/events`)

Security operators subscribe to live detections and zone intrusion events.

```json
{
  "event_type": "ZONE_INTRUSION",
  "camera_code": "CAM_PARKING_NORTH",
  "timestamp": "2026-08-23T19:01:15Z",
  "track_id": 142,
  "detected_class": "car",
  "confidence": 0.94,
  "bbox": [210, 150, 420, 310]
}
```

---

## 3. Error Contract & HTTP Status Codes

| Code | Status | Meaning |
|---|---|---|
| `400` | Bad Request | Malformed JSON, missing fields, or invalid time formats. |
| `401` | Unauthorized | Missing or expired JWT token. |
| `403` | Forbidden | Insufficient user role permissions (e.g. Operator trying to purge audit logs). |
| `404` | Not Found | Requested video, job, or camera ID does not exist. |
| `429` | Rate Limited | Exceeded API rate limits ($100$ requests / min). |
| `500` | Internal Error | Unhandled server exception (returns safe error code and correlation ID). |
