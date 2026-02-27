# 🚋 TfGM Metrolink Live Departures — Home Assistant Integration

> Real-time Manchester Metrolink tram departure times in Home Assistant.  
> **No OpenAI. Free forever.**  
> Pure HTML scraping — ~600ms per fetch.

![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.6%2B-blue?logo=home-assistant)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 📸 What It Does

- Scrapes live departure times from the [TfGM Bee Network](https://tfgm.com) website
- Filters for your destination (default: **Victoria**)
- Writes structured JSON to a shared volume
- Home Assistant reads it as a sensor with attributes
- Sends **phone push notifications + Alexa announcements** when your tram is in the catchable window
- Runs as a persistent **FastAPI sidecar** container — triggered by HA automation

```
HA Automation (every 2 min)
    → POST http://tram-analyzer:5001/trigger
        → requests + BeautifulSoup scrapes TfGM page (~600ms)
            → writes tram_status.json to shared volume
                → HA command_line sensor reads JSON every 60s
                    → Alert automation notifies phone + Alexa
```

---

## 🏗️ Directory Structure

```
metrolink-tram-ha/
├── tram-analyzer/
│   ├── tram_analyzer.py     # Scraper — fetches & parses TfGM departure board
│   ├── api.py               # FastAPI sidecar — HTTP trigger endpoint for HA
│   ├── Dockerfile           # Slim Python 3.11 image (~150MB)
│   └── requirements.txt     # requests, beautifulsoup4, fastapi, uvicorn
│
├── home-assistant/
│   ├── configuration-additions.yaml   # rest_command + sensors + input helpers
│   └── automations.yaml               # All 4 tram automations ready to paste
│
├── docker-compose-snippet.yml   # tram-analyzer service block to add to your compose
└── README.md
```

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/metrolink-tram-ha.git
cd metrolink-tram-ha
```

### 2. Add the tram-analyzer service to your docker-compose

Copy the contents of `docker-compose-snippet.yml` into your existing `docker-compose.yml`.

### 3. Build and start the sidecar

```bash
docker-compose build tram-analyzer
docker-compose up -d tram-analyzer

# Verify it's running
docker logs tram-analyzer --since 30s
# Expected: 🚀 Tram Analyzer Sidecar v2.0 starting on port 5001
```

### 4. Update Home Assistant config

Add the blocks from `home-assistant/configuration-additions.yaml` to your `configuration.yaml`:

```yaml
# Adds: rest_command, command_line sensors, input_number, input_datetime
```

Restart Home Assistant:
```bash
docker restart homeassistant
```

### 5. Add automations

Paste the contents of `home-assistant/automations.yaml` into your `automations.yaml`.

Reload automations: **Developer Tools → YAML → Reload Automations**

### 6. Test it

```bash
# Trigger a manual scrape from inside HA container
docker exec homeassistant curl -sf -X POST http://tram-analyzer:5001/trigger

# Watch the scrape happen in real time
docker logs tram-analyzer -f
```

---

## ⚙️ Configuration

### Change your tram stop

Edit the `TRAM_WEBSITE_URL` environment variable in your docker-compose:

```yaml
environment:
  - TRAM_WEBSITE_URL=https://tfgm.com/travel-updates/live-departures/tram/YOUR-STOP-tram
```

Find your stop URL at [tfgm.com/public-transport/tram](https://tfgm.com/public-transport/tram).

### Change your destination

Edit `VALID_DESTINATIONS` in `tram_analyzer.py` and update the Victoria filter:

```python
# In fetch_departures() - change the destination pattern
VALID_DESTINATIONS = {
    "victoria", "manchester airport", "altrincham", ...
}
```

And in `build_result()`:
```python
# Change "victoria" to your destination
victoria = [d for d in departures if "altrincham" in d["destination"].lower()]
```

### Change the alert window

In `automations.yaml`, update the time conditions:

```yaml
conditions:
  - condition: time
    after: "07:55:00"   # ← your window start
    before: "08:30:00"  # ← your window end
```

### Change the catchable window (walk time)

In the alert automation condition, set your walk time as the minimum:

```yaml
# 8-18 mins = 8 min walk time, 10 min buffer
{{ trams[0].minutes_until | int(default=99) >= 8 and
   trams[0].minutes_until | int(default=99) <= 18 }}
```

---

## 📡 API Endpoints

The sidecar exposes three endpoints on port 5001 (internal Docker network only):

| Endpoint | Method | Description |
|---|---|---|
| `/trigger` | POST | Triggers a scrape. Returns immediately, runs in background. |
| `/status` | GET | Returns current state, last run time, consecutive failures. |
| `/health` | GET | Health check. |

```bash
# From inside HA container:
curl http://tram-analyzer:5001/health
curl http://tram-analyzer:5001/status
curl -X POST http://tram-analyzer:5001/trigger
```

---

## 🏠 Home Assistant Sensors

After setup, two new sensors are available:

| Entity | Description |
|---|---|
| `sensor.tram_next_victoria` | State = next departure text (e.g. "8 mins"). Attributes include full trams list. |
| `sensor.tram_analyzer_health` | State = idle/running/success/error. Tracks consecutive failures. |

### Using in templates

```jinja2
{# Next tram departure time #}
{% set trams = state_attr('sensor.tram_next_victoria', 'all_victoria_trams') %}
Next tram at {{ (now().timestamp() + trams[0].minutes_until * 60) | timestamp_custom('%H:%M') }}

{# All Victoria trams #}
{% for tram in state_attr('sensor.tram_next_victoria', 'all_victoria_trams') %}
  {{ tram.departure_text }} ({{ tram.carriages }})
{% endfor %}
```

### Lovelace card example

```yaml
type: markdown
title: 🚋 Next Trams to Victoria
content: >
  {% set trams = state_attr('sensor.tram_next_victoria', 'all_victoria_trams') %}
  {% if trams %}
  {% for tram in trams %}
  **{{ (now().timestamp() + tram.minutes_until * 60) | timestamp_custom('%H:%M') }}**
  — {{ tram.departure_text }} ({{ tram.carriages }} tram)
  {% endfor %}
  *Last updated: {{ state_attr('sensor.tram_next_victoria', 'last_updated') | as_timestamp | timestamp_custom('%H:%M:%S') }}*
  {% else %}
  No Victoria trams currently showing.
  {% endif %}
```

---

## 🔔 Automations Overview

Four automations are included:

| Automation | Trigger | Purpose |
|---|---|---|
| `Tram_Check - Morning Tram Periodic Check Early` | Every 2 min, 07:55–08:30 | Triggers scrape during peak window |
| `Tram_Check - Morning Tram Periodic Check Late` | Every 5 min, 08:30–10:00 | Triggers scrape during late window |
| `Tram_Check - Alert When Victoria Tram Close` | Every 2 min, 07:55–08:30 | Sends notification when tram is 8–18 mins away |
| `Tram_Check - Alert On Consecutive Failures` | On sensor state change | Notifies if scraper fails 2+ times in a row |

---

## 🛠️ Troubleshooting

**Sidecar not reachable from HA:**
```bash
# Both containers must be on the same Docker network
docker network inspect hass_net | grep -A3 "tram-analyzer\|homeassistant"
```

**Sensor showing `unknown`:**
```bash
# Verify HA can read the JSON file
docker exec homeassistant cat /config/tram_data/tram_status.json

# Check for duplicate sensor: blocks in configuration.yaml
# HA 2024.6+ requires the new command_line: syntax (not platform: command_line)
```

**No departures parsed:**
```bash
# TfGM may have updated their page structure
# Run the diagnostic script locally
uv run --with requests --with beautifulsoup4 tram-analyzer/tram_analyzer.py
# Check the "Departure section:" log line for raw page content
```

**Destinations not matching:**
```bash
# Add your destination to VALID_DESTINATIONS in tram_analyzer.py
# Destination names must match TfGM's spelling exactly
```

---

## 📦 Requirements

- Home Assistant 2024.6+
- Docker + Docker Compose
- Both containers on the same Docker network

---

## 🤝 Contributing

PRs welcome! Particularly useful contributions:

- Additional stop URLs tested and confirmed working
- Support for other destinations / filtering options
- Dashboard card examples
- Non-Docker installation instructions

---

## 📄 License

MIT — do whatever you want with it.

---

## 🙏 Credits

Built for the Manchester Metrolink network. Data sourced from [TfGM Bee Network](https://tfgm.com).  
Not affiliated with TfGM or Transport for Greater Manchester.
