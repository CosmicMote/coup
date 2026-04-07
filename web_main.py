"""
Web entry point — starts the FastAPI server.

Usage:
    python web_main.py

Development (with live-reload React dev server):
    1. python web_main.py              # FastAPI on :8080
    2. cd frontend && npm run dev      # Vite on :5173, proxies /api and /ws to :8000

Production (serve built React app via FastAPI):
    1. cd frontend && npm run build    # writes to frontend/dist/
    2. python web_main.py              # FastAPI serves dist/ at /

The CLI (python main.py) is completely unaffected by this file.
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import uvicorn
from server.app import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=False)
