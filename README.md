# TfGM Tram Analyzer - Home Assistant Add-on

> Real-time Manchester Metrolink tram departure times in Home Assistant.
> **No API keys. Free forever.**
> Pure HTML scraping - ~600ms per fetch.

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-Add--on-blue?logo=home-assistant)
![Python](https://img.shields.io/badge/Python-3.13-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What It Does

- Scrapes live departure times from the [TfGM Bee Network](https://tfgm.com) website
- Filters for your chosen destinations (e.g., Piccadilly, Altrincham, Victoria)
- Pushes sensor data **directly to Home Assistant** via the Supervisor API
- No `configuration.yaml` changes needed - sensors are created automatically
- Supports **quiet hours** to pause scraping overnight
- **Reduced activity logging** - only logs status changes, not every departure update

---

## Installation

### Add the repository

1. Go to **Settings** > **Add-ons** > **Add-on Store**
2. Click the menu (three dots) > **Repositories**
3. Add: `https://github.com/jfevre/tfgm-tram-analyzer-ha-add-on`
4. Find "TfGM Tram Analyzer" and click **Install**

### Configure

1. Set your **tram stop URL** (find it at [tfgm.com/travel-updates/live-departures](https://tfgm.com/travel-updates/live-departures))
2. Select your **destinations** from the dropdown (or enter custom values)
3. Optionally enable **quiet hours** to pause overnight
4. Click **Start**

---

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `tram_website_url` | Prestwich stop | Full URL of your stop's TfGM live departure page |
| `destinations` | `Piccadilly` | Destinations to filter for (select from dropdown or enter custom) |
| `scan_interval` | `120` | Seconds between scrapes |
| `quiet_hours_enabled` | `false` | Pause scraping during specified hours |
| `quiet_hours_start` | `23` | Hour to start quiet period (0-23) |
| `quiet_hours_end` | `7` | Hour to end quiet period (0-23) |
| `log_only_on_change` | `true` | Only push to HA when status changes (reduces activity log noise) |

### Available Destinations

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

---

## Home Assistant Sensors

Once running, two sensors are automatically created:

| Entity | State | Key Attributes |
|--------|-------|----------------|
| `sensor.tram_next_departure` | Departure text (e.g., `8 mins`) | `next_tram`, `all_destination_trams`, `all_departures`, `last_updated` |
| `sensor.tram_analyzer_health` | `idle` / `running` / `success` / `error` / `quiet` | `consecutive_failures`, `in_quiet_hours` |

### Using in Templates

```jinja2
{% set trams = state_attr('sensor.tram_next_departure', 'all_destination_trams') %}
{% for tram in trams %}
  {{ tram.destination }} - {{ tram.departure_text }} ({{ tram.carriages }})
{% endfor %}
```

---

## Dashboard Examples

### Basic Tram List

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

### With Colour Indicators

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

---

## API Endpoints

The add-on exposes a debug API on port 5001:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/trigger` | POST | Manually trigger a scrape |
| `/status` | GET | Current state and failure count |
| `/health` | GET | Health check |

---

## Troubleshooting

**Sensor showing `unknown`:**
- Check the add-on logs for errors
- Verify your stop URL is correct and accessible

**No departures parsed:**
- TfGM may have updated their page structure
- Check the add-on logs for "No departures parsed" errors

**High activity log noise:**
- Ensure `log_only_on_change` is set to `true` (default)
- This only logs when status changes (success/no_service/error), not every minute

---

## Changelog

See [CHANGELOG.md](tfgm_tram_analyzer/CHANGELOG.md) for version history.

### v3.1.0

- **Quiet Hours**: Pause scraping during configurable hours (e.g., 11pm-7am)
- **Reduced HA Logging**: Only push on status changes, not departure time updates
- **Simplified Destinations**: 12 main Metrolink termini in dropdown

### v3.0.0

- **Direct Supervisor API**: Sensors created automatically, no configuration.yaml needed
- **FastAPI Service**: Background scheduler with health tracking

---

## License

MIT - do whatever you want with it.

---

## Credits

Built for the Manchester Metrolink network. Data sourced from [TfGM Bee Network](https://tfgm.com).
Not affiliated with TfGM or Transport for Greater Manchester.
