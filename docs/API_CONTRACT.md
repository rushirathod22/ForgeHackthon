# ASK MY CCTV — REST API Specification

**Document Version**: 1.0.0  
**Base URL**: `/api/v1`  
**Date**: August 24, 2026  

---

## 1. Health Check

### `GET /health`
- **Description**: Verify backend server operational status.
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "status": "ok",
  "service": "Ask My CCTV Engine",
  "version": "1.0.0"
}
```

---

## 2. Natural Language Video Search

### `POST /api/v1/search`
- **Description**: Process a natural language prompt and return matching CCTV video evidence records.
- **Auth**: None
- **Request Body**:
```json
{
  "query": "Find people wearing helmets near the main gate",
  "video_id": "v-9981"
}
```
- **Response `200 OK`**:
```json
{
  "query": "Find people wearing helmets near the main gate",
  "results_count": 1,
  "results": [
    {
      "event_id": "evt-7712",
      "video_id": "v-9981",
      "video_filename": "main_gate_cam04.mp4",
      "track_id": 884,
      "class_name": "person",
      "event_type": "ZONE_INTRUSION",
      "start_time_sec": 42.5,
      "end_time_sec": 48.0,
      "duration_sec": 5.5,
      "confidence": 0.964,
      "details": "Track #884 (person) entered restricted zone 'MainGate'",
      "score": 2.0,
      "clip_url": "/api/v1/videos/v-9981/clips/evt-7712"
    }
  ]
}
```

---

## 3. Video Management & Pipeline Execution

### `POST /api/v1/videos/upload`
- **Description**: Upload a new CCTV MP4 video file and queue background object detection & event extraction pipeline.
- **Auth**: None
- **Request**: `multipart/form-data` with `file: UploadFile`.
- **Response `200 OK`**:
```json
{
  "video_id": "3a8f9c12-8812-4d2b-b91c-123456789abc",
  "status": "QUEUED",
  "message": "Video uploaded and processing queued."
}
```

### `POST /api/v1/videos/register`
- **Description**: Register an existing video file path on the server file system.
- **Auth**: None
- **Request Body**:
```json
{
  "filename": "test_cctv.mp4",
  "filepath": "videos/input/test_cctv.mp4"
}
```
- **Response `200 OK`**:
```json
{
  "video_id": "3a8f9c12-8812-4d2b-b91c-123456789abc",
  "status": "QUEUED",
  "message": "Video registered and processing queued."
}
```
- **Response `404 Not Found`**:
```json
{
  "detail": "File not found at 'videos/input/missing.mp4'"
}
```

### `GET /api/v1/videos`
- **Description**: Retrieve list of all processed or queued video streams in the system.
- **Auth**: None
- **Response `200 OK`**:
```json
[
  {
    "id": "3a8f9c12-8812-4d2b-b91c-123456789abc",
    "filename": "test_cctv.mp4",
    "filepath": "c:/.../videos/input/test_cctv.mp4",
    "annotated_filepath": "c:/.../videos/processed/test_cctv_annotated.mp4",
    "status": "COMPLETED",
    "duration_sec": 42.5,
    "total_frames": 1275,
    "processed_at": "2026-08-24T14:22:10Z",
    "total_tracks": 14,
    "total_events": 4
  }
]
```

### `GET /api/v1/jobs/{job_id}`
- **Description**: Query background processing status for a video job ID.
- **Auth**: None
- **Response `200 OK`**:
```json
{
  "job_id": "3a8f9c12-8812-4d2b-b91c-123456789abc",
  "filename": "test_cctv.mp4",
  "status": "PROCESSING",
  "total_tracks": 0,
  "total_events": 0,
  "processed_at": null
}
```

---

## 4. Evidence Media Streaming

### `GET /api/v1/videos/{video_id}/clips/{clip_id}`
- **Description**: Stream or download extracted MP4 evidence clip.
- **Response `200 OK`**: Video stream (`Content-Type: video/mp4`).

### `GET /api/v1/videos/{video_id}/stream`
- **Description**: Stream full annotated MP4 CCTV video file.
- **Response `200 OK`**: Video stream (`Content-Type: video/mp4`).
