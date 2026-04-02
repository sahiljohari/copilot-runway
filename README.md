# 🛫 Copilot Runway

An AI-flavored TODO app and session dashboard for [GitHub Copilot CLI](https://docs.github.com/en/copilot/github-copilot-in-the-cli). Runs entirely in your browser — no server, no uploads, no telemetry.

![Copilot Runway](https://img.shields.io/badge/no--backend-browser--only-blue)

## What it does

| Feature | How it works |
|---------|-------------|
| **📋 Todos** | Create, filter, cycle (pending → in-progress → done). Import priorities from your daily briefing with one paste. |
| **💾 Sessions** | Browse all your Copilot CLI sessions — summaries, checkpoints, files touched, initial/last messages. Click to expand, one-click `copilot resume <id>` copy. |
| **📥 Auto-import briefings** | On DB load, scans your sessions for recent `/daily-briefing` output and auto-creates todos (deduped). |
| **🧹 Cleanup** | One-click workspace cleanup via companion server — stale logs, session artifacts, temp files. |
| **🔄 Persistent refresh** | Connect your `session-store.db` once. The file handle is saved in IndexedDB. Hit 🔄 Refresh anytime — no file picker, no re-upload. |

## Quick start

### Option A: Local file

```bash
# Just open it
open index.html         # macOS
start index.html        # Windows
xdg-open index.html     # Linux
```

### Option B: Both servers at once (Windows)

```powershell
.\start.ps1    # dashboard on :9090, cleanup API on :8111
```

### Option C: Cleanup companion only (optional)

The Python CLI companion adds workspace cleanup (delete stale logs, session artifacts, temp files):

```bash
python cleanup.py              # starts cleanup API on http://localhost:8111
python cleanup.py --port 9000  # custom port
```

Zero external dependencies — Python stdlib only.

## How it works

```
┌─────────────────────────────────────────────────────┐
│  Browser (index.html)                               │
│  ┌─────────┐  ┌──────────┐  ┌────────────────────┐ │
│  │  Todos   │  │ Sessions │  │ Briefing Import    │ │
│  │ (IDB)   │  │ (sql.js) │  │ (regex parser)     │ │
│  └────┬────┘  └────┬─────┘  └────────────────────┘ │
│       │            │                                 │
│  IndexedDB    File System Access API                │
│  (persistent)  (reads local .db file)               │
└─────────────────────────────────────────────────────┘
         ↕               ↕
   Browser storage   ~/.copilot/session-store.db
   (never leaves     (read-only, never uploaded)
    your machine)
```

- **sql.js** (WebAssembly SQLite, loaded from CDN) reads the session store entirely in-browser
- **IndexedDB** persists todos and the file handle across browser sessions
- **File System Access API** re-reads the DB on refresh without a file picker
- Nothing is uploaded, sent to a server, or stored externally

## Browser support

| Browser | Status |
|---------|--------|
| Chrome 86+ | ✅ Full support (File System Access API) |
| Edge 86+ | ✅ Full support |
| Firefox | ⚠️ Manual file re-pick on each visit (no persistent handles) |
| Safari | ⚠️ Manual file re-pick on each visit |

## File structure

```
copilot-runway/
├── index.html     # Single-file browser app (all HTML/CSS/JS inline)
├── cleanup.py     # Optional cleanup companion server (localhost:8111)
├── start.ps1      # Launch both servers at once (Windows)
└── README.md
```

## License

MIT
