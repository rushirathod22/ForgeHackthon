from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Float, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CameraRecord(Base):
    __tablename__ = "cameras"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=False, default="Main Entrance")
    status = Column(String(50), nullable=False, default="ONLINE")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    videos = relationship("VideoRecord", back_populates="camera", cascade="all, delete-orphan")


class VideoRecord(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    camera_id = Column(String(36), ForeignKey("cameras.id"), nullable=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    annotated_filepath = Column(String(500), nullable=True)
    json_metadata_path = Column(String(500), nullable=True)
    duration_sec = Column(Float, default=0.0)
    fps = Column(Float, default=30.0)
    width = Column(Integer, default=1920)
    height = Column(Integer, default=1080)
    total_frames = Column(Integer, default=0)
    status = Column(String(50), default="COMPLETED")  # QUEUED, PROCESSING, COMPLETED, FAILED
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    camera = relationship("CameraRecord", back_populates="videos")
    tracks = relationship("TrackRecord", back_populates="video", cascade="all, delete-orphan")
    events = relationship("EventRecord", back_populates="video", cascade="all, delete-orphan")


class TrackRecord(Base):
    __tablename__ = "tracks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    track_id = Column(Integer, nullable=False)
    class_name = Column(String(50), nullable=False)
    first_seen_sec = Column(Float, nullable=False)
    last_seen_sec = Column(Float, nullable=False)
    duration_sec = Column(Float, nullable=False)
    avg_speed_px_sec = Column(Float, default=0.0)
    trajectory_json = Column(Text, nullable=True)
    embedding_json = Column(Text, nullable=True)
    visual_attributes_json = Column(Text, nullable=True)

    video = relationship("VideoRecord", back_populates="tracks")


class EventRecord(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id = Column(String(36), ForeignKey("videos.id"), nullable=False)
    track_id = Column(Integer, nullable=False)
    event_type = Column(String(100), nullable=False)  # LOITERING, FAST_MOVEMENT, ZONE_INTRUSION, STOPPED_VEHICLE
    class_name = Column(String(50), nullable=False)
    start_time_sec = Column(Float, nullable=False)
    end_time_sec = Column(Float, nullable=False)
    confidence = Column(Float, default=1.0)
    zone_name = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    clip_path = Column(String(500), nullable=True)
    embedding_json = Column(Text, nullable=True)
    visual_attributes_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    video = relationship("VideoRecord", back_populates="events")
