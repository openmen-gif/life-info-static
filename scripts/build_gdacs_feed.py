#!/usr/bin/env python3
"""Build a same-origin GDACS wildfire and tropical-cyclone feed for GitHub Pages."""
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

RSS_URL = "https://www.gdacs.org/xml/rss.xml"
OUTPUT_PATH = Path("data/gdacs_incidents.json")
GDACS_NS = "http://www.gdacs.org"
GEO_NS = "http://www.w3.org/2003/01/geo/wgs84_pos#"
GEORSS_NS = "http://www.georss.org/georss"


def text_of(item, tag, namespace=GDACS_NS):
    return (item.findtext(f"{{{namespace}}}{tag}") or "").strip()


def parse_number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def coordinates_of(item):
    point = text_of(item, "point", GEORSS_NS).split()
    values = point[:2] if len(point) >= 2 else [text_of(item, "lat", GEO_NS), text_of(item, "long", GEO_NS)]
    try:
        lat, lon = (float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return lat, lon


def parse_feed(xml_bytes):
    root = ET.fromstring(xml_bytes)
    grouped = {"wildfire": [], "typhoon": []}
    kinds = {"WF": "wildfire", "TC": "typhoon"}

    for item in root.findall(".//item"):
        kind = kinds.get(text_of(item, "eventtype"))
        if not kind:
            continue
        severity = item.find(f"{{{GDACS_NS}}}severity")
        name = text_of(item, "eventname") or (item.findtext("title") or "").strip()
        coordinates = coordinates_of(item)
        if coordinates is None:
            continue
        lat, lon = coordinates
        grouped[kind].append({
            "lat": lat,
            "lon": lon,
            "name": name or "이름 미상",
            "country": text_of(item, "country"),
            "dateadded": text_of(item, "fromdate") or text_of(item, "datemodified"),
            "threat": (severity.text or "—").strip() if severity is not None else "—",
            "tags": text_of(item, "alertlevel") or "Green",
            "severity": parse_number(severity.get("value") if severity is not None else 0),
            "reportUrl": (item.findtext("link") or "https://www.gdacs.org/").strip(),
        })

    for incidents in grouped.values():
        incidents.sort(key=lambda item: item["dateadded"], reverse=True)
    return grouped


def fetch_rss():
    request = urllib.request.Request(RSS_URL, headers={"User-Agent": "life-info-static-gdacs-feed/1.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def main():
    grouped = parse_feed(fetch_rss())
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "GDACS RSS (server-side GitHub Actions sync)",
        **grouped,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"GDACS RSS 저장: wildfire={len(grouped['wildfire'])}, typhoon={len(grouped['typhoon'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
