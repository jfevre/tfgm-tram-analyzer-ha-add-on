# TfGM Tram Analyzer

Scrapes the TfGM Bee Network live departure board for your Metrolink stop and
pushes tram timing data **directly into Home Assistant** as sensor entities via
the Supervisor API. No `configuration.yaml` sensors or REST commands needed.

## Configuration

| Option | Description |
|---|---|
| `tram_website_url` | Full URL of your stop's TfGM live departure page |
| `destinations` | List of destination names to filter for (e.g. `Piccadilly`, `Altrincham`). Add as many as needed. |
| `scan_interval` | Seconds between scrapes (default: `120`) |

To find your stop URL, visit [tfgm.com/travel-updates/live-departures](https://tfgm.com/travel-updates/live-departures)
and navigate to your stop. Copy the full URL from the browser.

## Home Assistant integration

Once the add-on is running it automatically creates and updates two sensor entities:

| Entity | Description |
|---|---|
| `sensor.tram_next_departure` | State = departure text (e.g. `8 mins`). Attributes include `next_tram`, `all_destination_trams`, `all_departures`, `status`, `last_updated` |
| `sensor.tram_analyzer_health` | State = `idle` / `running` / `success` / `error`. Attributes include `consecutive_failures`, `last_error`, `last_run`, `last_success` |

No `configuration.yaml` changes are needed for the sensors themselves.

### Optional: alert automations

Add the input helpers from `configuration-additions.yaml` to your
`configuration.yaml` if you want to use the dedup logic in the alert
automation (prevents the same tram alerting more than once):

```yaml
input_number:
  tram_last_alerted_minutes:
    name: "Tram Last Alerted Minutes"
    min: 0
    max: 99
    step: 1
    initial: 0
    icon: mdi:tram

input_datetime:
  tram_last_alert_sent:
    name: "Tram Last Alert Sent"
    has_date: true
    has_time: true
```

Then paste the automations from `automations.yaml` into your `automations.yaml`
and replace the placeholder notify service names with your own.

## API endpoints

The add-on exposes a debug API on port 5001:

| Endpoint | Method | Description |
|---|---|---|
| `/trigger` | POST | Manually trigger a scrape (returns immediately) |
| `/status` | GET | Current analyzer state and failure count |
| `/health` | GET | Health check |
