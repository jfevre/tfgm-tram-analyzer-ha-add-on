#!/usr/bin/env python3
"""
TfGM Tram Analyzer — Home Assistant add-on service.

Runs on a configurable interval and pushes tram sensor state directly to
Home Assistant via the Supervisor API. No external trigger, shared file,
or configuration.yaml sensors needed.

Endpoints:
  POST /trigger  — manually trigger a scrape (returns immediately)
  GET  /status   — current state + consecutive failure count
  GET  /health   — health check
"""

import threading
import time
import os
from datetime import datetime
import requests
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn

from tram_analyzer import fetch_and_build

app = FastAPI(title="TfGM Tram Analyzer", version="3.1")

# ── Configuration ─────────────────────────────────────────────────────────────
SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN", "")
HA_API = "http://supervisor/core/api"
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL", "120"))

# Quiet hours configuration
QUIET_HOURS_ENABLED = os.getenv("QUIET_HOURS_ENABLED", "false").lower() == "true"
QUIET_HOURS_START = int(os.getenv("QUIET_HOURS_START", "23"))
QUIET_HOURS_END = int(os.getenv("QUIET_HOURS_END", "7"))

# Logging configuration
LOG_ONLY_ON_CHANGE = os.getenv("LOG_ONLY_ON_CHANGE", "true").lower() == "true"

# ── Shared state (thread-safe) ────────────────────────────────────────────────
_state = {
    "state": "idle",
    "last_run": None,
    "last_success": None,
    "last_error": None,
    "consecutive_failures": 0,
    "last_sensor_status": None,  # Track previous status (success/no_service/error) for change detection
    "in_quiet_hours": False,
}
_state_lock = threading.Lock()


def _is_quiet_hours() -> bool:
    """Check if current time is within quiet hours."""
    if not QUIET_HOURS_ENABLED:
        return False

    current_hour = datetime.now().hour

    # Handle overnight ranges (e.g., 23:00 to 07:00)
    if QUIET_HOURS_START > QUIET_HOURS_END:
        return current_hour >= QUIET_HOURS_START or current_hour < QUIET_HOURS_END
    else:
        return QUIET_HOURS_START <= current_hour < QUIET_HOURS_END


# ── Supervisor API ────────────────────────────────────────────────────────────
def _push_sensor(entity_id: str, state: str, attributes: dict) -> None:
    if not SUPERVISOR_TOKEN:
        print(f"[WARN] No SUPERVISOR_TOKEN — skipping push for {entity_id}")
        return
    url = f"{HA_API}/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(
            url,
            headers=headers,
            json={"state": state, "attributes": attributes},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"[INFO] Pushed {entity_id} → {state!r}")
    except Exception as e:
        print(f"[WARN] Push failed for {entity_id}: {e}")


def _push_tram_sensor(result: dict, force: bool = False) -> None:
    status = result.get("status")
    if status == "success":
        state = result["next_tram"]["departure_text"]
    elif status == "no_service":
        state = "No service"
    else:
        state = "Error"

    # Check if STATUS has changed (for log_only_on_change mode)
    # We track status (success/no_service/error), not departure times
    with _state_lock:
        last_status = _state.get("last_sensor_status")
        status_changed = last_status != status

        if LOG_ONLY_ON_CHANGE and not force and not status_changed:
            print(f"[INFO] Status unchanged ({status}) — skipping HA push (state: {state})")
            return

        _state["last_sensor_status"] = status

    _push_sensor(
        "sensor.tram_next_departure",
        state,
        {
            "status": result.get("status"),
            "next_tram": result.get("next_tram"),
            "all_destination_trams": result.get("all_destination_trams"),
            "all_departures": result.get("all_departures"),
            "last_updated": result.get("last_updated"),
            "message": result.get("message"),
            "destination_filters": result.get("destination_filters"),
            "friendly_name": "Tram Next Departure",
        },
    )


def _push_health_sensor(force: bool = False) -> None:
    with _state_lock:
        s = dict(_state)

    # Only push health updates on error or when forced
    if LOG_ONLY_ON_CHANGE and not force and s["state"] not in ("error", "running"):
        return

    _push_sensor(
        "sensor.tram_analyzer_health",
        s["state"],
        {
            "last_run": s["last_run"],
            "last_success": s["last_success"],
            "last_error": s["last_error"],
            "consecutive_failures": s["consecutive_failures"],
            "in_quiet_hours": s.get("in_quiet_hours", False),
            "friendly_name": "Tram Analyzer Health",
        },
    )


# ── Analysis worker ───────────────────────────────────────────────────────────
def run_analysis() -> None:
    with _state_lock:
        if _state["state"] == "running":
            print("[INFO] Analysis already running — skipping")
            return
        _state["state"] = "running"
        _state["last_run"] = datetime.now().isoformat()

    _push_health_sensor()

    try:
        print(f"[INFO] Analysis started at {datetime.now().strftime('%H:%M:%S')}")
        result = fetch_and_build()
        result["last_updated"] = datetime.now().isoformat()
        result["stop_url"] = os.getenv("TRAM_WEBSITE_URL", "")
        result["analyzer_version"] = "3.0"

        with _state_lock:
            _state["state"] = "success"
            _state["last_success"] = datetime.now().isoformat()
            _state["consecutive_failures"] = 0
            _state["last_error"] = None

        _push_tram_sensor(result)
        _push_health_sensor()
        print(f"[INFO] Done — status={result.get('status')!r}")

    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Analysis failed: {error_msg}")

        with _state_lock:
            _state["state"] = "error"
            _state["last_error"] = error_msg
            _state["consecutive_failures"] += 1

        _push_sensor(
            "sensor.tram_next_departure",
            "Error",
            {
                "status": "error",
                "error": error_msg,
                "last_updated": datetime.now().isoformat(),
                "friendly_name": "Tram Next Departure",
            },
        )
        _push_health_sensor()


# ── Scheduler ─────────────────────────────────────────────────────────────────
def _scheduler() -> None:
    print(f"[INFO] Scheduler started — interval={SCAN_INTERVAL}s")
    if QUIET_HOURS_ENABLED:
        print(f"[INFO] Quiet hours enabled: {QUIET_HOURS_START:02d}:00 - {QUIET_HOURS_END:02d}:00")
    if LOG_ONLY_ON_CHANGE:
        print("[INFO] Log only on change: enabled")

    while True:
        if _is_quiet_hours():
            with _state_lock:
                was_quiet = _state.get("in_quiet_hours", False)
                _state["in_quiet_hours"] = True
                _state["state"] = "quiet"

            if not was_quiet:
                print(f"[INFO] Entering quiet hours ({QUIET_HOURS_START:02d}:00 - {QUIET_HOURS_END:02d}:00) — pausing scrapes")
                _push_health_sensor(force=True)
        else:
            with _state_lock:
                was_quiet = _state.get("in_quiet_hours", False)
                _state["in_quiet_hours"] = False

            if was_quiet:
                print("[INFO] Exiting quiet hours — resuming scrapes")

            run_analysis()

        time.sleep(SCAN_INTERVAL)


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/trigger")
async def trigger(background_tasks: BackgroundTasks):
    """Manually trigger a tram data scrape (returns immediately)."""
    with _state_lock:
        if _state["state"] == "running":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "already_running",
                    "message": "Analysis already in progress",
                    "started_at": _state["last_run"],
                },
            )
    background_tasks.add_task(run_analysis)
    return {"status": "triggered", "timestamp": datetime.now().isoformat()}


@app.get("/status")
async def get_status():
    """Current analyzer state."""
    with _state_lock:
        return dict(_state)


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"TfGM Tram Analyzer v3.1 — interval={SCAN_INTERVAL}s")
    threading.Thread(target=_scheduler, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="warning")
