# Entry point — re-exports the FastAPI app from api.app so uvicorn can be
# started with either:
#   uvicorn main:app          (simple)
#   uvicorn api.app:app       (explicit)
from api.app import app  # noqa: F401  re-export

from detection.detect import main as detect_main


def main() -> None:
    detect_main()


if __name__ == "__main__":
    main()
