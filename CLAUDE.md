# TfGM Tram Analyzer - Claude Code Configuration

## Project Overview

This is a **Home Assistant add-on** that scrapes real-time Manchester Metrolink tram departure data from the TfGM Bee Network website and pushes it to Home Assistant via the Supervisor API.

- **Version:** 3.1.0
- **Language:** Python 3.13
- **Framework:** FastAPI + BeautifulSoup4
- **Platform:** Home Assistant Add-on (Docker-based)

## Project Structure

```
tfgm_tram_analyzer/
├── config.yaml                 # Add-on manifest (version, options schema)
├── Dockerfile                  # Alpine Python image
└── rootfs/
    ├── app/
    │   ├── api.py              # FastAPI service (scheduler, endpoints, HA push)
    │   └── tram_analyzer.py    # Core scraper (fetch, parse, filter)
    └── etc/services.d/
        └── tfgm-tram-analyzer/
            └── run             # S6 service entry point (bashio config)

automations.yaml                # Example HA automations for alerts
configuration-additions.yaml    # Example HA helpers for dedup
```

## Key Files

- `tfgm_tram_analyzer/rootfs/app/tram_analyzer.py` - Core scraping logic using BeautifulSoup + regex
- `tfgm_tram_analyzer/rootfs/app/api.py` - FastAPI service that schedules scrapes and pushes to HA
- `tfgm_tram_analyzer/config.yaml` - Add-on configuration schema

## Development Commands

```bash
# Run the scraper standalone (for testing)
cd tfgm_tram_analyzer/rootfs/app
TRAM_WEBSITE_URL="https://tfgm.com/travel-updates/live-departures/tram/prestwich-tram" \
DESTINATIONS="Piccadilly,Altrincham" \
python tram_analyzer.py

# Run the API server locally
cd tfgm_tram_analyzer/rootfs/app
SCAN_INTERVAL=60 python api.py

# Build Docker image locally
docker build -t tfgm-tram-analyzer ./tfgm_tram_analyzer

# Run container locally (without HA)
docker run -e TRAM_WEBSITE_URL="https://tfgm.com/travel-updates/live-departures/tram/prestwich-tram" \
           -e DESTINATIONS="Piccadilly" \
           -e SCAN_INTERVAL=120 \
           -p 5001:5001 \
           tfgm-tram-analyzer
```

## Architecture

1. **Scheduler** (daemon thread) runs every `SCAN_INTERVAL` seconds
2. **Scraper** fetches TfGM page, parses HTML with BeautifulSoup, extracts departures via regex
3. **Filter** matches departures against configured destinations
4. **Push** sends sensor state to HA via `http://supervisor/core/api/states/{entity_id}`

## Sensors Created

| Entity | State | Key Attributes |
|--------|-------|----------------|
| `sensor.tram_next_departure` | Departure text (e.g., "8 mins") | `next_tram`, `all_destination_trams`, `all_departures`, `last_updated` |
| `sensor.tram_analyzer_health` | Status (idle/running/success/error) | `consecutive_failures`, `last_run`, `last_error` |

## Valid Metrolink Destinations

The scraper validates against a hardcoded list in `tram_analyzer.py:VALID_DESTINATIONS` containing 45+ stops (Victoria, Piccadilly, Altrincham, Bury, etc.). This prevents false positives from page noise.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRAM_WEBSITE_URL` | prestwich-tram page | TfGM stop URL |
| `DESTINATIONS` | "Piccadilly" | Comma-separated destination filters |
| `SCAN_INTERVAL` | 120 | Seconds between scrapes |
| `QUIET_HOURS_ENABLED` | false | Enable quiet hours (no scraping) |
| `QUIET_HOURS_START` | 23 | Hour to start quiet period (0-23) |
| `QUIET_HOURS_END` | 7 | Hour to end quiet period (0-23) |
| `LOG_ONLY_ON_CHANGE` | true | Only push to HA when state changes |
| `SUPERVISOR_TOKEN` | (injected by HA) | Bearer token for HA API |
| `OUTPUT_FILE` | /share/tram_status.json | Legacy JSON output path |

## Testing

When modifying the scraper:
1. Test against the live TfGM page to ensure regex still matches
2. Check edge cases: "Due", "Departing", "Arrived", multi-digit minutes
3. Verify destination filtering works with mixed case

## CI/CD

GitHub Actions workflows in `.github/workflows/`:
- `builder.yaml` - Builds and pushes Docker images for aarch64/amd64
- Images pushed to `ghcr.io/jfevre/{arch}-addon-tfgm_tram_analyzer`

---

## Agents

### ha-dashboard-helper

Use this agent when the user needs help creating Home Assistant dashboard cards, Jinja2 templates, or YAML configurations for displaying tram data.

```yaml
name: ha-dashboard-helper
description: "Helps create Home Assistant dashboard cards and Jinja2 templates for displaying tram data"
tools:
  - Read
  - WebSearch
prompt: |
  You are a Home Assistant dashboard expert. Help the user create dashboard cards,
  Jinja2 templates, and YAML configurations for displaying tram departure data.

  Available sensor data:
  - sensor.tram_next_departure (state = departure text like "8 mins")
    - Attributes: next_tram, all_destination_trams, all_departures, last_updated, status
    - next_tram object: destination, carriages, departure_text, minutes_until
    - all_destination_trams: array of tram objects matching configured destinations
    - all_departures: array of all trams from the stop

  - sensor.tram_analyzer_health (state = idle/running/success/error)
    - Attributes: consecutive_failures, last_run, last_success, last_error

  Common Jinja2 patterns:
  - Access attribute: state_attr('sensor.tram_next_departure', 'next_tram')
  - Format timestamp: as_timestamp(updated) | timestamp_custom('%H:%M:%S')
  - Relative time: relative_time(as_datetime(updated))
  - Use | for multiline YAML to preserve line breaks in markdown cards

  Always provide complete, copy-paste ready YAML.
```

### scraper-debugger

Use this agent when the scraper stops working, returns errors, or the TfGM website structure may have changed.

```yaml
name: scraper-debugger
description: "Debugs scraping issues when TfGM website structure changes or data extraction fails"
tools:
  - Read
  - Bash
  - WebFetch
  - Grep
prompt: |
  You are debugging the TfGM tram scraper. The scraper uses BeautifulSoup and regex
  to extract departure data from the TfGM live departures page.

  Key file: tfgm_tram_analyzer/rootfs/app/tram_analyzer.py

  Debugging steps:
  1. Fetch the current TfGM page and examine its structure
  2. Compare against the regex pattern in fetch_departures()
  3. Check if VALID_DESTINATIONS list needs updating
  4. Test the parse_minutes() function with edge cases

  The regex pattern expects: "{destination} Single|Double tram {time}"
  where destination must be in VALID_DESTINATIONS.

  Common issues:
  - TfGM changed HTML structure
  - New destination names added to Metrolink network
  - Changed time format (e.g., "mins" vs "min")
```

### addon-builder

Use this agent when modifying the add-on configuration, Dockerfile, or preparing releases.

```yaml
name: addon-builder
description: "Helps with Home Assistant add-on configuration, Docker builds, and releases"
tools:
  - Read
  - Edit
  - Write
  - Bash
  - Glob
prompt: |
  You are a Home Assistant add-on developer. Help with:
  - Modifying config.yaml (options schema, version bumps)
  - Dockerfile changes (dependencies, base image)
  - S6 service scripts in rootfs/etc/services.d/
  - GitHub Actions workflows for building/releasing

  Key conventions:
  - Version in tfgm_tram_analyzer/config.yaml
  - Use bashio for reading HA config in run script
  - Images built for aarch64 and amd64 architectures
  - Pushed to ghcr.io/jfevre/{arch}-addon-tfgm_tram_analyzer

  When bumping versions:
  1. Update version in config.yaml
  2. Ensure Dockerfile hasn't changed base image incompatibly
  3. Test build locally before pushing
```
