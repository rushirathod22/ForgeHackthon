try:
    from db.models import CameraRecord, EventRecord, TrackRecord, VideoRecord
    from db.session import get_db, init_db
except ModuleNotFoundError:
    from backend.db.models import CameraRecord, EventRecord, TrackRecord, VideoRecord
    from backend.db.session import get_db, init_db

__all__ = ["CameraRecord", "VideoRecord", "TrackRecord", "EventRecord", "init_db", "get_db"]
