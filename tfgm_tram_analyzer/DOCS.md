# TfGM Tram Analyzer

Scrapes the TfGM Bee Network live departure board for your Metrolink stop and
pushes tram timing data **directly into Home Assistant** as sensor entities via
the Supervisor API. No `configuration.yaml` sensors or REST commands needed.

## Configuration

| Option | Default | Description |
|--------|---------|-------------|
| `tram_website_url` | Prestwich stop | Full URL of your stop's TfGM live departure page |
| `destinations` | `Piccadilly` | List of destination names to filter for. Select from dropdown or enter custom values. |
| `scan_interval` | `120` | Seconds between scrapes |
| `quiet_hours_enabled` | `false` | Pause scraping during specified hours to avoid rate limiting |
| `quiet_hours_start` | `23` | Hour to start quiet period (0-23) |
| `quiet_hours_end` | `7` | Hour to end quiet period (0-23) |
| `log_only_on_change` | `true` | Only push to Home Assistant when status changes (reduces activity log noise) |

### Finding your stop URL

Visit [tfgm.com/travel-updates/live-departures](https://tfgm.com/travel-updates/live-departures)
and navigate to your stop. Copy the full URL from the browser.

### Available destinations

The dropdown includes the main Metrolink termini:

- Altrincham
- Ashton-under-Lyne
- Bury
- East Didsbury
- Eccles
- Etihad Campus
- Manchester Airport
- Piccadilly
- Rochdale Town Centre
- The Trafford Centre
- Trafford Bar
- Victoria

You can also enter custom destination names if needed.

## Home Assistant integration

Once the add-on is running it automatically creates and updates two sensor entities:

| Entity | Description |
|--------|-------------|
| `sensor.tram_next_departure` | State = departure text (e.g. `8 mins`). Attributes include `next_tram`, `all_destination_trams`, `all_departures`, `status`, `last_updated` |
| `sensor.tram_analyzer_health` | State = `idle` / `running` / `success` / `error` / `quiet`. Attributes include `consecutive_failures`, `last_error`, `last_run`, `last_success`, `in_quiet_hours` |

No `configuration.yaml` changes are needed for the sensors themselves.

### Sensor attributes

**`sensor.tram_next_departure` attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `status` | string | `success`, `no_service`, or `error` |
| `next_tram` | object | Details of the next tram: `destination`, `carriages`, `departure_text`, `minutes_until` |
| `all_destination_trams` | array | All trams matching your configured destinations |
| `all_departures` | array | Every tram from the stop (all destinations) |
| `destination_filters` | array | Your configured destination filters |
| `last_updated` | string | ISO timestamp of last successful scrape |

**`sensor.tram_analyzer_health` attributes:**

| Attribute | Type | Description |
|-----------|------|-------------|
| `last_run` | string | ISO timestamp of last analysis attempt |
| `last_success` | string | ISO timestamp of last successful scrape |
| `last_error` | string | Error message from last failure (if any) |
| `consecutive_failures` | int | Number of failures in a row |
| `in_quiet_hours` | bool | Whether scraping is currently paused |

## Dashboard examples

### Basic tram list

```yaml
type: markdown
title: Trams to Manchester
content: >
  {% set trams = state_attr('sensor.tram_next_departure', 'all_destination_trams') %}
  {% set updated = state_attr('sensor.tram_next_departure', 'last_updated') %}
  {% if trams %}{% for tram in trams %}
  - **{{ tram.destination }}** - {{ tram.departure_text }} ({{ tram.carriages }})
  {% endfor %}

  _{{ relative_time(as_datetime(updated)) }} ago_
  {% else %}
  No trams currently scheduled
  {% endif %}
```

### With colour indicators

```yaml
type: markdown
title: Upcoming Trams
content: >
  {% set trams = state_attr('sensor.tram_next_departure', 'all_destination_trams') %}
  {% if trams %}{% for tram in trams %}
  {{ '🟢' if tram.minutes_until <= 5 else '🟡' if tram.minutes_until <= 10 else '⚪' }} **{{ tram.departure_text }}** → {{ tram.destination }} ({{ tram.carriages }})
  {% endfor %}
  {% else %}
  No service
  {% endif %}
```

### Conditional catchable tram card

```yaml
type: conditional
conditions:
  - entity: sensor.tram_next_departure
    state_not: "No service"
  - condition: numeric_state
    entity: sensor.tram_next_departure
    attribute: next_tram.minutes_until
    above: 7
    below: 19
card:
  type: entity
  entity: sensor.tram_next_departure
  name: "Catchable Tram!"
```

## Optional: alert automations

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
|----------|--------|-------------|
| `/trigger` | POST | Manually trigger a scrape (returns immediately) |
| `/status` | GET | Current analyzer state and failure count |
| `/health` | GET | Health check |

## Quiet hours

When `quiet_hours_enabled` is set to `true`, the add-on will pause scraping during
the specified hours. This is useful to avoid potential rate limiting from TfGM
during times when you don't need tram data (e.g., overnight).

The quiet hours support overnight ranges. For example, setting `quiet_hours_start: 23`
and `quiet_hours_end: 7` will pause scraping from 11pm to 7am.

During quiet hours:
- The health sensor state will show `quiet`
- The `in_quiet_hours` attribute will be `true`
- No scraping or HA updates will occur

## Reduced activity logging

When `log_only_on_change` is set to `true` (the default), the add-on will only
push updates to Home Assistant when the **status** changes:

- `success` ↔ `no_service` ↔ `error`

This significantly reduces noise in the Home Assistant activity log, as departure
times changing (e.g., "8 mins" → "7 mins") won't trigger updates.

The add-on's internal container logs still show all activity regardless of this setting.
