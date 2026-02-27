#!/usr/bin/env python3
"""
TfGM Metrolink live departure parser for Home Assistant.

Scrapes the TfGM Bee Network departure board and outputs structured JSON.

Configuration via environment variables:
  TRAM_WEBSITE_URL  — TfGM departure page URL for your stop
  OUTPUT_FILE       — Path to write JSON output (default: /app/output/tram_status.json)
  DESTINATION       — Destination to filter for (default: victoria)
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

URL = os.getenv(
    "TRAM_WEBSITE_URL",
    "https://tfgm.com/travel-updates/live-departures/tram/wythenshawe-park-tram"
)
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "/app/output/tram_status.json")
DESTINATION = os.getenv("DESTINATION", "victoria").lower()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# All known Metrolink destinations — anchors the regex to avoid noise
VALID_DESTINATIONS = {
    "victoria",
    "manchester airport",
    "altrincham",
    "bury",
    "rochdale",
    "east didsbury",
    "eccles",
    "ashton",
    "ashton-under-lyne",
    "oldham",
    "shaw",
    "firswood",
    "piccadilly",
    "deansgate - castlefield",
    "cornbrook",
    "mediacity uk",
    "salford quays",
    "exchange square",
    "st peter's square",
    "market street",
    "etihad campus",
    "harbour city",
    "anchorage",
    "new islington",
    "holt town",
    "velopark",
    "clayton hall",
    "edge lane",
    "droylsden",
    "audenshaw",
    "robinswood road",
    "barton dock road",
    "village",
    "wharfside",
    "imperial war museum",
    "the trafford centre",
    "parkway",
    "roundthorn",
    "baguley",
    "shadowmoss",
    "martinscroft",
    "crossacres",
    "benchill",
    "wythenshawe town centre",
    "northern moor",
    "peel hall",
    "kingsway business park",
}


def parse_minutes(text: str) -> int:
    """Convert departure text to integer minutes.
    'Due' / 'Arrived' / 'Departing' → 0
    '4 mins' → 4
    """
    text = text.lower().strip()
    if any(w in text for w in ["due", "arrived", "departing", "now"]):
        return 0
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else 99


def fetch_departures() -> list[dict]:
    """Fetch and parse the TfGM live departure board.

    Returns list of all departures as dicts:
        destination, carriages, departure_text, minutes_until
    Sorted ascending by minutes_until.
    """
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    body_text = soup.body.get_text(" ", strip=True) if soup.body else resp.text

    # Isolate the departures section between "Live Departures" and "Footer"
    match = re.search(
        r"Live Departures.*?Updated.*?ago(.*?)Footer",
        body_text,
        re.DOTALL | re.IGNORECASE
    )
    section = match.group(1) if match else body_text
    print(f"📄 Raw departure section: {section[:400]}")

    # Build alternation from known destinations, longest first
    # to avoid partial matches (e.g. "Manchester Airport" before "Manchester")
    dest_pattern = "|".join(
        sorted(VALID_DESTINATIONS, key=len, reverse=True)
    )

    # Pattern anchors on known destination names — avoids noise text like
    # "Upcoming disruptions Victoria Double tram 3 mins" being parsed as
    # destination "Upcoming disruptions Victoria"
    pattern = re.compile(
        rf"({dest_pattern})\s+"
        r"(Single|Double)\s+tram\s+"
        r"([\d]+\s+mins?|Due|Arrived|Departing|Now)",
        re.IGNORECASE
    )

    departures = []
    seen = set()

    for m in pattern.finditer(section):
        dest = m.group(1).strip().title()
        carriages = m.group(2).strip()
        wait_text = m.group(3).strip()
        key = f"{dest.lower()}:{wait_text.lower()}"

        if key in seen:
            continue
        seen.add(key)

        departures.append({
            "destination": dest,
            "carriages": carriages,
            "departure_text": wait_text,
            "minutes_until": parse_minutes(wait_text),
        })

    departures.sort(key=lambda x: x["minutes_until"])
    return departures


def build_result(departures: list[dict]) -> dict:
    """Filter for target destination and build output JSON."""
    target = [
        d for d in departures
        if DESTINATION in d["destination"].lower()
    ]

    now = datetime.now().isoformat()

    if not target:
        return {
            "status": "no_service",
            "message": f"No {DESTINATION.title()}-bound trams in current departures",
            "destination_filter": DESTINATION,
            "all_departures": departures,
            "timestamp": now,
        }

    return {
        "status": "success",
        "destination_filter": DESTINATION,
        "next_tram": {
            "departure_text": target[0]["departure_text"],
            "minutes_until": target[0]["minutes_until"],
            "destination": target[0]["destination"],
            "carriages": target[0]["carriages"],
        },
        # Keep legacy key for backwards compatibility
        "next_victoria_tram": {
            "departure_text": target[0]["departure_text"],
            "minutes_until": target[0]["minutes_until"],
            "destination": target[0]["destination"],
            "carriages": target[0]["carriages"],
        },
        "all_destination_trams": [
            {
                "departure_text": t["departure_text"],
                "minutes_until": t["minutes_until"],
                "carriages": t["carriages"],
            }
            for t in target
        ],
        # Legacy key for backwards compatibility
        "all_victoria_trams": [
            {
                "departure_text": t["departure_text"],
                "minutes_until": t["minutes_until"],
                "carriages": t["carriages"],
            }
            for t in target
        ],
        "all_departures": departures,
        "timestamp": now,
    }


def save_result(result: dict) -> dict:
    """Write result to JSON file for Home Assistant."""
    output = {
        **result,
        "last_updated": datetime.now().isoformat(),
        "stop_url": URL,
        "analyzer_version": "2.1",
        "method": "html_parse",
    }

    os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_FILE)), exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"💾 Saved → {OUTPUT_FILE}")
    return output


def main():
    start = datetime.now()
    print(f"🚋 TfGM Tram Analyzer v2.1 — {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 Stop: {URL}")
    print(f"🎯 Filtering for: {DESTINATION.title()}\n")

    try:
        departures = fetch_departures()

        if not departures:
            print("⚠️  No departures found — TfGM page structure may have changed")
            result = {
                "status": "error",
                "error": "No departures parsed — page structure may have changed",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            print(f"✅ {len(departures)} departures found:")
            for d in departures:
                icon = "🚋" if DESTINATION in d["destination"].lower() else "  "
                print(f"  {icon} {d['destination']} ({d['carriages']}) → {d['departure_text']}")

            result = build_result(departures)
            target_count = len(result.get("all_destination_trams", []))
            print(f"\n🎯 {DESTINATION.title()} trams: {target_count}")

        output = save_result(result)
        elapsed = (datetime.now() - start).total_seconds()
        print(f"⚡ {elapsed:.2f}s total")
        print(f"\n📊 Output:\n{json.dumps(output, indent=2)}")

    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        save_result({
            "status": "error",
            "error": f"Network error: {e}",
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        save_result({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


if __name__ == "__main__":
    main()
