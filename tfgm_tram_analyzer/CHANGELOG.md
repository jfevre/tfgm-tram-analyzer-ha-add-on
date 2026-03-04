# Changelog

## 3.1.0

### New Features
- **Quiet Hours**: Skip scraping during configurable hours (e.g., 11pm-7am) to avoid rate limiting
  - `quiet_hours_enabled`: Enable/disable quiet hours
  - `quiet_hours_start`: Hour to start quiet period (0-23)
  - `quiet_hours_end`: Hour to end quiet period (0-23)
- **Reduced HA Activity Logging**: Only push to Home Assistant when status changes (success/no_service/error), not on every departure time update
  - `log_only_on_change`: Enable/disable (default: true)
  - Internal container logs still show all activity
- **Simplified Destinations**: 12 main Metrolink termini available in dropdown, plus custom entry support

### Changes
- Health sensor now includes `in_quiet_hours` attribute
- Scheduler logs entry/exit from quiet hours

## 3.0.0

### Breaking Changes
- Sensors now pushed directly to Home Assistant via Supervisor API
- No longer requires `configuration.yaml` sensor definitions
- Shared file output (`/share/tram_status.json`) retained as backup only

### New Features
- FastAPI service with background scheduler
- Endpoints: `POST /trigger`, `GET /status`, `GET /health`
- Two sensors created automatically:
  - `sensor.tram_next_departure` - Next tram departure info
  - `sensor.tram_analyzer_health` - Analyzer health status
- Consecutive failure tracking with `consecutive_failures` attribute
- Thread-safe state management

## 2.1.0

- Initial Home Assistant add-on release
- Migrated from Docker Compose sidecar to native HA add-on
- Output now written to `/share/tram_status.json` (HA shared volume)
- Stop URL and destination configurable via add-on options UI
- s6-overlay service management for automatic restart on failure
