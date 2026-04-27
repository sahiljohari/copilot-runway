#!/usr/bin/env python3
"""
Copilot Runway — cleanup companion server.

Runs locally to scan and delete stale logs, session artifacts, and temp files
from ~/.copilot/. Called by the browser frontend via fetch().

Usage:
    python cleanup.py              # http://localhost:8111
    python cleanup.py --port 9000  # custom port

Zero dependencies — stdlib only.
"""

import sqlite3, json, os, sys, argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
from datetime import datetime, timedelta

HOME = Path.home()
COPILOT_DIR = HOME / ".copilot"
LOG_RETENTION_DAYS = 7
LOG_RETENTION_COUNT = 5
LOW_ACTIVITY_TURN_THRESHOLD = 3
LOW_ACTIVITY_CHECKPOINT_THRESHOLD = 0
SESSION_STORE_DB = COPILOT_DIR / "session-store.db"


# ── Helpers ──────────────────────────────────────────────────

def _file_info(p):
    try:
        st = p.stat()
        return {"path": str(p), "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat()}
    except OSError:
        return None


def _human_size(b):
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


def _rmtree(p):
    """Remove a directory tree."""
    import shutil
    shutil.rmtree(p, ignore_errors=True)


def _category(cid, label, files):
    infos = [f for f in (map(_file_info, files)) if f]
    if not infos:
        return None
    return {"id": cid, "label": label, "files": infos,
            "count": len(infos), "size": sum(f["size"] for f in infos)}


def _low_activity_session_ids():
    """Return session IDs with fewer than the threshold turns and checkpoints."""
    if not SESSION_STORE_DB.exists():
        return set()
    try:
        conn = sqlite3.connect(str(SESSION_STORE_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("""
            SELECT s.id
            FROM sessions s
            LEFT JOIN (SELECT session_id, COUNT(*) as cnt FROM turns GROUP BY session_id) t
                ON t.session_id = s.id
            LEFT JOIN (SELECT session_id, COUNT(*) as cnt FROM checkpoints GROUP BY session_id) c
                ON c.session_id = s.id
            WHERE COALESCE(t.cnt, 0) < ?
              AND COALESCE(c.cnt, 0) <= ?
        """, (LOW_ACTIVITY_TURN_THRESHOLD, LOW_ACTIVITY_CHECKPOINT_THRESHOLD))
        ids = {row["id"] for row in cur.fetchall()}
        conn.close()
        return ids
    except Exception:
        return set()


# ── Scan ─────────────────────────────────────────────────────

def scan():
    cats = []
    cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)

    # 1. Stale process logs
    logs_dir = COPILOT_DIR / "logs"
    if logs_dir.exists():
        logs = sorted(logs_dir.glob("process-*.log"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        stale = [f for f in logs[LOG_RETENTION_COUNT:]
                 if datetime.fromtimestamp(f.stat().st_mtime) < cutoff]
        cat = _category("logs", "Stale process logs", stale)
        if cat:
            cats.append(cat)

    # 2. Session artifact files (skip current session)
    current_sid = os.environ.get("COPILOT_SESSION_ID", "")
    ss_dir = COPILOT_DIR / "session-state"
    if ss_dir.exists():
        artifacts = []
        for sdir in ss_dir.iterdir():
            if sdir.name == current_sid:
                continue
            fdir = sdir / "files"
            if fdir.exists():
                artifacts.extend(f for f in fdir.rglob("*") if f.is_file())
        cat = _category("artifacts", "Session artifact files", artifacts)
        if cat:
            cats.append(cat)

    # 3. Temp files in home directory
    temps = []
    for pat in ("temp_*.*", "*.tmp", "*.temp", "*.bak"):
        temps.extend(f for f in HOME.glob(pat) if f.is_file())
    cat = _category("home_temp", "Temp files in home directory", temps)
    if cat:
        cats.append(cat)

    # 4. Package temp
    pkg_tmp = COPILOT_DIR / "pkg" / "tmp"
    if pkg_tmp.exists():
        cat = _category("pkg_tmp", "Package temp files",
                         [f for f in pkg_tmp.rglob("*") if f.is_file()])
        if cat:
            cats.append(cat)

    # 5. Low-activity sessions (fewer than 3 turns, 0 checkpoints)
    low_ids = _low_activity_session_ids()
    if low_ids and ss_dir.exists():
        low_files = []
        for sdir in ss_dir.iterdir():
            if sdir.name in low_ids and sdir.name != current_sid:
                low_files.extend(f for f in sdir.rglob("*") if f.is_file())
        cat = _category(
            "low_activity",
            f"Low-activity sessions (<{LOW_ACTIVITY_TURN_THRESHOLD} turns, no checkpoints)",
            low_files,
        )
        if cat:
            cat["session_count"] = sum(
                1 for sdir in ss_dir.iterdir()
                if sdir.name in low_ids and sdir.name != current_sid
            )
            cats.append(cat)

    return cats


def clean(category_ids):
    results = {"removed": 0, "freed": 0, "errors": []}
    for cat in scan():
        if cat["id"] in category_ids:
            for f in cat["files"]:
                try:
                    Path(f["path"]).unlink()
                    results["removed"] += 1
                    results["freed"] += f["size"]
                except OSError as e:
                    results["errors"].append(f"{f['path']}: {e}")
            # Remove empty session directories left behind for low-activity cleanup
            if cat["id"] == "low_activity":
                current_sid = os.environ.get("COPILOT_SESSION_ID", "")
                ss_dir = COPILOT_DIR / "session-state"
                low_ids = _low_activity_session_ids()
                for sdir in ss_dir.iterdir():
                    if sdir.name in low_ids and sdir.name != current_sid:
                        try:
                            _rmtree(sdir)
                        except OSError as e:
                            results["errors"].append(f"{sdir}: {e}")
    results["freed_human"] = _human_size(results["freed"])
    return results


# ── HTTP ─────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if urlparse(self.path).path == "/api/cleanup/scan":
            return self._json(scan())
        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path == "/api/cleanup/run":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            return self._json(clean(body.get("categories", [])))
        self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description="Copilot Runway cleanup companion")
    parser.add_argument("--port", type=int, default=8111)
    args = parser.parse_args()

    if not COPILOT_DIR.exists():
        print(f"Error: {COPILOT_DIR} not found")
        sys.exit(1)

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"\n  🧹 Cleanup Companion")
    print(f"  ────────────────────")
    print(f"  API at:  http://localhost:{args.port}")
    print(f"  Target:  {COPILOT_DIR}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
