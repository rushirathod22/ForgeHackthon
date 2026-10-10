from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

try:
    import dotenv
    dotenv.load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception:
    pass

try:
    from api.routes import agent, clips, config, search, videos
    from api.routes.videos import reset_stuck_processing_jobs
    from db.session import init_db
except ModuleNotFoundError:
    from backend.api.routes import agent, clips, config, search, videos
    from backend.api.routes.videos import reset_stuck_processing_jobs
    from backend.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    # Reset any videos that were interrupted mid-processing by a previous restart
    reset_stuck_processing_jobs()
    yield


app = FastAPI(
    title="Ask My CCTV API",
    description="AI-Powered Natural Language CCTV Video Search and Event Detection API",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(videos.router)
app.include_router(search.router)
app.include_router(clips.router)
app.include_router(config.router)
app.include_router(agent.router)

# Mount static video directory
VIDEOS_DIR = Path(__file__).resolve().parents[2] / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/videos", StaticFiles(directory=str(VIDEOS_DIR)), name="videos")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Ask My CCTV Engine", "version": "1.0.0"}


@app.get("/metrics")
def metrics():
    """Metrics endpoint for monitoring probes."""
    return {"status": "ok", "service": "Ask My CCTV Engine"}


