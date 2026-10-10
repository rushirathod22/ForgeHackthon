from __future__ import annotations

import json
from pathlib import Path
import pytest
import cv2
import numpy as np

from detection.detect import (
    CCTVDetector,
    DetectorConfig,
    parse_args,
)
from detection.metadata_exporter import (
    DetectionItem,
    DetectionMetadataExporter,
    VideoMetadata,
)


def test_invalid_confidence_arg_raises_error(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--confidence", "1.5"])


def test_missing_model_file_raises_error(tmp_path: Path) -> None:
    missing_model = tmp_path / "non_existent.pt"
    dummy_input = tmp_path / "dummy.mp4"
    dummy_output = tmp_path / "out.mp4"
    config = DetectorConfig(
        model_path=missing_model,
        input_path=dummy_input,
        output_path=dummy_output,
    )
    with pytest.raises(FileNotFoundError, match="YOLO model file not found"):
        CCTVDetector(config)


def test_missing_input_file_raises_error(tmp_path: Path) -> None:
    model_path = Path(__file__).resolve().parents[2] / "backend" / "yolo11n.pt"
    if not model_path.exists():
        pytest.skip("yolo11n.pt not present for test execution")

    missing_input = tmp_path / "non_existent_video.mp4"
    dummy_output = tmp_path / "out.mp4"
    config = DetectorConfig(
        model_path=model_path,
        input_path=missing_input,
        output_path=dummy_output,
    )
    detector = CCTVDetector(config)
    with pytest.raises(FileNotFoundError, match="Input video was not found"):
        detector.process()


def test_metadata_exporter_serialization(tmp_path: Path) -> None:
    json_output = tmp_path / "test_meta.json"
    meta = VideoMetadata(
        video_name="test.mp4",
        fps=30.0,
        width=640,
        height=480,
        total_frames=10,
        model_name="yolo11n.pt",
        confidence_threshold=0.5,
    )
    exporter = DetectionMetadataExporter(meta, json_output)
    
    # Add sample frame detection
    item = DetectionItem(
        class_id=2,
        class_name="car",
        confidence=0.92,
        bbox=[100.0, 150.0, 250.0, 300.0],
    )
    exporter.add_frame_detections(frame_index=0, timestamp_sec=0.0, detections=[item])
    exporter.save()

    assert json_output.is_file()
    with open(json_output, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["video_metadata"]["video_name"] == "test.mp4"
    assert data["frames_processed"] == 1
    assert data["frames"][0]["detections"][0]["class_name"] == "car"
    assert data["frames"][0]["detections"][0]["bbox"] == [100.0, 150.0, 250.0, 300.0]


def test_synthetic_video_detection_smoke_test(tmp_path: Path) -> None:
    model_path = Path(__file__).resolve().parents[2] / "backend" / "yolo11n.pt"
    if not model_path.exists():
        pytest.skip("yolo11n.pt not present for test execution")

    # Create a 5-frame synthetic video
    video_path = tmp_path / "synthetic_cctv.mp4"
    output_path = tmp_path / "synthetic_out.mp4"
    json_path = tmp_path / "synthetic_out.json"

    width, height, fps = 320, 240, 10
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    for _ in range(5):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Draw a white rectangle to simulate an object
        cv2.rectangle(frame, (50, 50), (150, 150), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()

    config = DetectorConfig(
        model_path=model_path,
        input_path=video_path,
        output_path=output_path,
        json_output_path=json_path,
        confidence=0.30,
    )
    detector = CCTVDetector(config)
    stats, generated_json = detector.process()

    assert stats.frames_processed == 5
    assert output_path.is_file()
    assert output_path.stat().st_size > 0
    assert generated_json is not None and generated_json.is_file()
