import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "cctv_metadata.db"
PROCESSED_DIR = Path(__file__).resolve().parents[2] / "videos" / "processed"

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

# Find all metadata json files
for json_file in PROCESSED_DIR.glob("*_metadata.json"):
    video_id = json_file.stem.replace("_metadata", "")
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        tracks = data.get("tracks", [])
        v_meta = data.get("video_metadata", {})
        width = v_meta.get("width", 1920)
        height = v_meta.get("height", 1080)

        # Update video dimensions
        cur.execute("UPDATE videos SET width=?, height=? WHERE id=?", (width, height, video_id))

        count = 0
        for t in tracks:
            t_id = t.get("track_id")
            traj = t.get("trajectory", [])
            cur.execute(
                "UPDATE tracks SET trajectory_json=? WHERE video_id=? AND track_id=?",
                (json.dumps(traj), video_id, t_id),
            )
            count += 1
        print(f"Synced {count} tracks and dims ({width}x{height}) for video {video_id}")
    except Exception as e:
        print(f"Error for {json_file}: {e}")

conn.commit()
conn.close()
print("Finished syncing trajectories!")
