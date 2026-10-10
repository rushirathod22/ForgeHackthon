try:
    from tracking.tracker import CCTVTracker, TrackedObject
except ModuleNotFoundError:
    from backend.tracking.tracker import CCTVTracker, TrackedObject

__all__ = ["CCTVTracker", "TrackedObject"]
