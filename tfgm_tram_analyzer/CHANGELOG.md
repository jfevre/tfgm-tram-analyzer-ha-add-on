# Changelog

## 2.1.0

- Initial Home Assistant add-on release
- Migrated from Docker Compose sidecar to native HA add-on
- Output now written to `/share/tram_status.json` (HA shared volume)
- Stop URL and destination configurable via add-on options UI
- s6-overlay service management for automatic restart on failure
