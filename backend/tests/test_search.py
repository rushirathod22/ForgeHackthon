from __future__ import annotations

import json
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from db.models import Base, CameraRecord, EventRecord, TrackRecord, VideoRecord
    from search.embeddings import VisualEmbeddingEngine
    from search.query_parser import NLQueryParser
    from search.retriever import HybridRetriever
except ModuleNotFoundError:
    from backend.db.models import Base, CameraRecord, EventRecord, TrackRecord, VideoRecord
    from backend.search.embeddings import VisualEmbeddingEngine
    from backend.search.query_parser import NLQueryParser
    from backend.search.retriever import HybridRetriever


def test_nl_query_parser() -> None:
    parser = NLQueryParser()
    
    q1 = parser.parse("show fast moving cars near main gate after 10s")
    assert "car" in q1.target_classes
    assert "FAST_MOVEMENT" in q1.event_types
    assert q1.time_start_sec == 10.0

    q2 = parser.parse("find loitering person with red helmet or stopped truck")
    assert "person" in q2.target_classes
    assert "truck" in q2.target_classes
    assert "LOITERING" in q2.event_types
    assert "STOPPED_VEHICLE" in q2.event_types
    assert "red" in q2.visual_attributes
    assert "helmet" in q2.visual_attributes

    q3 = parser.parse("track suspicious watchman at gate between 5 and 20 seconds")
    assert "person" in q3.target_classes
    assert "ZONE_INTRUSION" in q3.event_types
    assert "OBJECT_TRACKED" in q3.event_types
    assert q3.zone_name == "MainGate"
    assert q3.time_start_sec == 5.0
    assert q3.time_end_sec == 20.0


def test_nl_query_parser_normalizes_retail_objects_without_conflicting_filters() -> None:
    parser = NLQueryParser()

    standalone_phone = parser.parse("find every mobile phone")
    assert standalone_phone.target_classes == ["cell phone"]
    assert "person" not in standalone_phone.target_classes

    carried_phone = parser.parse("find the person holding a mobile phone")
    assert carried_phone.target_classes == ["person"]
    assert "holding_phone" in carried_phone.visual_attributes


def test_db_models_and_retriever() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    camera = CameraRecord(name="Gate Camera", location="North Gate")
    db.add(camera)
    db.commit()

    video = VideoRecord(camera_id=camera.id, filename="cctv_test.mp4", filepath="/videos/cctv_test.mp4", duration_sec=60.0)
    db.add(video)
    db.commit()

    event1 = EventRecord(
        video_id=video.id,
        track_id=1,
        event_type="FAST_MOVEMENT",
        class_name="car",
        start_time_sec=5.0,
        end_time_sec=12.0,
        confidence=0.92,
        details="Speed 95 px/sec",
    )
    event2 = EventRecord(
        video_id=video.id,
        track_id=2,
        event_type="LOITERING",
        class_name="person",
        start_time_sec=15.0,
        end_time_sec=25.0,
        confidence=0.88,
        details="Person loitering",
    )
    db.add_all([event1, event2])
    db.commit()

    retriever = HybridRetriever()

    # Search 1: Fast cars
    results1 = retriever.search(db, "find fast moving cars")
    assert len(results1) == 1
    assert results1[0].class_name == "car"
    assert results1[0].event_type == "FAST_MOVEMENT"

    # Search 2: Loitering
    results2 = retriever.search(db, "show loitering person after 10s")
    assert len(results2) == 1
    assert results2[0].class_name == "person"
    assert results2[0].event_type == "LOITERING"


def test_hybrid_vector_semantic_search() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    video = VideoRecord(filename="cctv_vector_test.mp4", filepath="/videos/cctv_vector_test.mp4", duration_sec=120.0)
    db.add(video)
    db.commit()

    embedder = VisualEmbeddingEngine(embedding_dim=128)

    # Generate synthetic image embeddings
    white_crop = np.ones((64, 64, 3), dtype=np.uint8) * 245
    red_crop = np.zeros((64, 64, 3), dtype=np.uint8)
    red_crop[:, :, 2] = 245

    vec_white = embedder.embed_image(white_crop)
    vec_red = embedder.embed_image(red_crop)

    # White car event
    event_white = EventRecord(
        video_id=video.id,
        track_id=101,
        event_type="FAST_MOVEMENT",
        class_name="car",
        start_time_sec=2.0,
        end_time_sec=8.0,
        confidence=0.95,
        details="White sedan moving quickly",
        embedding_json=json.dumps(vec_white),
    )
    # Red car event
    event_red = EventRecord(
        video_id=video.id,
        track_id=102,
        event_type="FAST_MOVEMENT",
        class_name="car",
        start_time_sec=12.0,
        end_time_sec=18.0,
        confidence=0.95,
        details="Red sedan moving quickly",
        embedding_json=json.dumps(vec_red),
    )
    db.add_all([event_white, event_red])
    db.commit()

    retriever = HybridRetriever(embedder=embedder)

    # Query for white car
    white_results = retriever.search(db, "find white car")
    assert len(white_results) == 2
    # White car must rank #1
    assert white_results[0].track_id == 101
    assert white_results[0].similarity > white_results[1].similarity

    # Query for red car
    red_results = retriever.search(db, "find red car")
    assert len(red_results) == 2
    # Red car must rank #1
    assert red_results[0].track_id == 102
    assert red_results[0].similarity > red_results[1].similarity


def test_object_tracked_events_are_searchable_with_attributes() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    video = VideoRecord(filename="gate_1.mp4", filepath="/videos/gate_1.mp4", duration_sec=40.0)
    db.add(video)
    db.commit()

    person_event = EventRecord(
        video_id=video.id,
        track_id=7,
        event_type="OBJECT_TRACKED",
        class_name="person",
        start_time_sec=6.0,
        end_time_sec=19.0,
        confidence=0.91,
        zone_name="MainGate",
        details="Track #7 person observed at society gate. Attributes: black.",
        visual_attributes_json=json.dumps(["black"]),
    )
    car_event = EventRecord(
        video_id=video.id,
        track_id=8,
        event_type="OBJECT_TRACKED",
        class_name="car",
        start_time_sec=8.0,
        end_time_sec=12.0,
        confidence=0.89,
        zone_name="MainGate",
        details="Track #8 car observed at society gate. Attributes: white.",
        visual_attributes_json=json.dumps(["white"]),
    )
    db.add_all([person_event, car_event])
    db.commit()

    retriever = HybridRetriever()
    results = retriever.search(db, "track black suspicious person at gate between 5 and 20 seconds")

    assert len(results) == 1
    assert results[0].track_id == 7
    assert results[0].event_type == "OBJECT_TRACKED"
    assert "black" in results[0].visual_attributes


def test_multi_attribute_person_with_phone_search() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    video = VideoRecord(filename="office_cctv.mp4", filepath="/videos/office_cctv.mp4", duration_sec=60.0)
    db.add(video)
    db.commit()

    # Track 1: Person in red shirt holding a phone
    p1 = EventRecord(
        video_id=video.id,
        track_id=101,
        event_type="OBJECT_TRACKED",
        class_name="person",
        start_time_sec=10.0,
        end_time_sec=25.0,
        confidence=0.95,
        zone_name="MainGate",
        details="Person wearing red shirt holding phone",
        visual_attributes_json=json.dumps(["red", "red_shirt", "holding_phone", "black_pants"]),
    )
    # Track 2: Person in blue shirt without phone
    p2 = EventRecord(
        video_id=video.id,
        track_id=102,
        event_type="OBJECT_TRACKED",
        class_name="person",
        start_time_sec=15.0,
        end_time_sec=30.0,
        confidence=0.92,
        zone_name="MainGate",
        details="Person wearing blue shirt",
        visual_attributes_json=json.dumps(["blue", "blue_shirt", "black_pants"]),
    )
    db.add_all([p1, p2])
    db.commit()

    retriever = HybridRetriever()
    results = retriever.search(db, "Find the person wearing a red shirt who is holding a phone")

    assert len(results) == 1
    assert results[0].track_id == 101
    assert "holding_phone" in results[0].matched_attrs
    assert "red_shirt" in results[0].matched_attrs


def test_gemini_config_endpoints() -> None:
    from fastapi.testclient import TestClient
    from api.app import app

    client = TestClient(app)
    # Test GET config
    res = client.get("/api/v1/config/gemini")
    assert res.status_code == 200
    data = res.json()
    assert "configured" in data
    assert "masked_key" in data
    assert data["model"] == "gemini-3.6-flash"
