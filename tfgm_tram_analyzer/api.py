#!/usr/bin/env python3
"""
FastAPI sidecar for TfGM Metrolink tram analyzer.

Home Assistant triggers a scrape via HTTP POST /trigger.
Runs analysis in background thread — HTTP response is immediate.
Results written to /share/tram_status.json (HA shared volume).
HA reads JSON via command_line sensor every 60s.

Endpoints:
  POST /trigger  — trigger a scrape (called by HA automation)
  GET  /status   — current state + consecutive failure count (polled by HA sensor)
  GET  /health   — health check
"""

import threading
import json
import os
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

from tram_analyzer import main as run_tram_main

app = FastAPI(title="TfGM Tram Analyzer Sidecar", version="2.1")

# ── Shared state (thread-safe) ────────────────────────────────────────────────
_state = {
    "state": "idle",           # idle | running | success | error
    "last_run": None,
    "last_success": None,
    "last_error": None,
    "consecutive_failures": 0,
    "last_result": None,
}
_state_lock = threading.Lock()
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "/share/tram_status.json")


# ── Background worker ─────────────────────────────────────────────────────────
def run_analysis():
    with _state_lock:
        _state["state"] = "running"
        _state["last_run"] = datetime.now().isoformat()

    try:
        print(f"🚋 [{datetime.now().strftime('%H:%M:%S')}] Analysis triggered")
        run_tram_main()

        if os.path.exists(OUTPUT_FILE):
            with open(OUTPUT_FILE) as f:
                result = json.load(f)
        else:
            raise FileNotFoundError("tram_status.json was not written by analyzer")

        with _state_lock:
            _state["state"] = "success"
            _state["last_success"] = datetime.now().isoformat()
            _state["consecutive_failures"] = 0
            _state["last_result"] = result
            _state["last_error"] = None

        print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Done — status: {result.get('status')}")

    except Exception as e:
        error_msg = str(e)
        print(f"❌ [{datetime.now().strftime('%H:%M:%S')}] Failed: {error_msg}")

        error_payload = {
            "status": "error",
            "error": error_msg,
            "last_updated": datetime.now().isoformat(),
        }
        try:
            os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_FILE)), exist_ok=True)
            with open(OUTPUT_FILE, "w") as f:
                json.dump(error_payload, f, indent=2)
        except Exception as write_err:
            print(f"❌ Could not write error payload: {write_err}")

        with _state_lock:
            _state["state"] = "error"
            _state["last_error"] = error_msg
            _state["consecutive_failures"] += 1
            _state["last_result"] = error_payload


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/trigger")
async def trigger(background_tasks: BackgroundTasks):
    """
    Trigger a tram data scrape.
    Called by HA automation every 2 minutes.
    Returns immediately — analysis runs in background.
    Duplicate run protection: returns 200 with already_running if busy.
    """
    with _state_lock:
        if _state["state"] == "running":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "already_running",
                    "message": "Previous analysis still in progress — skipping",
                    "started_at": _state["last_run"],
                },
            )

    background_tasks.add_task(run_analysis)
    return {
        "status": "triggered",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/status")
async def get_status():
    """
    Current analyzer state.
    Polled by HA command_line sensor every 60s.
    consecutive_failures used by failure alert automation.
    """
    with _state_lock:
        return dict(_state)


@app.get("/health")
async def health():
    """Health check — used to verify container is reachable from HA."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 TfGM Tram Analyzer Sidecar v2.1 — listening on :5001")
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info")
