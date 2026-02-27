# TfGM Tram Analyzer

Scrapes the TfGM Bee Network live departure board for your Metrolink stop and
exposes the data to Home Assistant via a local HTTP API on port 5001.

## Configuration

| Option | Description |
|---|---|
| `tram_website_url` | Full URL of your stop's TfGM live departure page |
| `destination` | Destination name to filter for (e.g. `victoria`, `altrincham`) |

To find your stop URL, visit [tfgm.com/travel-updates/live-departures](https://tfgm.com/travel-updates/live-departures)
and navigate to your stop. Copy the full URL from the browser.

## Home Assistant integration

After starting the add-on, add the following to your `configuration.yaml`:

```yaml
rest_command:
  fetch_tram_data:
    url: "http://localhost:5001/trigger"
    method: POST
    content_type: "application/json"

command_line:
  - sensor:
      name: "Tram Next Victoria"
      command: "cat /share/tram_status.json 2>/dev/null || echo '{\"status\":\"unavailable\"}'"
      scan_interval: 60
      value_template: >
        {% if value_json.status == 'success' %}
          {{ value_json.next_victoria_tram.departure_text }}
        {% elif value_json.status == 'no_service' %}
          No service
        {% elif value_json.status == 'error' %}
          Error
        {% else %}
          {{ value_json.status | default('unavailable') }}
        {% endif %}
      json_attributes:
        - status
        - next_victoria_tram
        - all_victoria_trams
        - last_updated
        - message
        - all_departures

  - sensor:
      name: "Tram Analyzer Health"
      command: >
        curl -sf --max-time 5 http://localhost:5001/status 2>/dev/null
        || echo '{"state":"unreachable","consecutive_failures":0}'
      scan_interval: 60
      value_template: "{{ value_json.state }}"
      json_attributes:
        - state
        - last_run
        - last_success
        - last_error
        - consecutive_failures
```

See `automations.yaml` in the repository for example HA automations that
trigger scrapes on a schedule and alert when a tram is in your catchable window.

## API endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/trigger` | POST | Trigger a scrape (returns immediately, runs in background) |
| `/status` | GET | Current analyzer state and consecutive failure count |
| `/health` | GET | Health check |

## Output file

Results are written to `/share/tram_status.json`. This file is accessible to
Home Assistant Core via the `/share` directory.
