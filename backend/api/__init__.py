try:
    from api.app import app
except ModuleNotFoundError:
    from backend.api.app import app

__all__ = ["app"]
