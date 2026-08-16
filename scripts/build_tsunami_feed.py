#!/usr/bin/env python3
"""NOAA 쓰나미 경보센터 2곳의 Atom 게시문을 병합해 data/tsunami_incidents.json으로 저장한다.

NTWC(Palmer AK)는 북미·알래스카, PTWC(Honolulu)는 태평양 전역을 담당한다.
쓰나미는 드문 현상이라 평시 건수가 0~2건이며, 그 자체가 '현재 위험 없음' 신호다.
"""
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

# 직접 실행(python scripts/build_x.py)과 패키지 import(scripts.build_x) 양쪽을 지원한다
try:
    from feed_common import UA, iso_utc, now_iso, valid_coordinates, write_feed
except ImportError:  # pragma: no cover - 테스트에서 패키지로 import 될 때
    from scripts.feed_common import UA, iso_utc, now_iso, valid_coordinates, write_feed

CENTERS = {
    "NTWC": ("https://www.tsunami.gov/events/xml/PAAQAtom.xml", "국립쓰나미경보센터 (Palmer AK)"),
    "PTWC": ("https://www.tsunami.gov/events/xml/PHEBAtom.xml", "태평양쓰나미경보센터 (Honolulu HI)"),
}
ATOM_NS = "http://www.w3.org/2005/Atom"
GEO_NS = "http://www.w3.org/2003/01/geo/wgs84_pos#"
OUTPUT_PATH = Path("data/tsunami_incidents.json")

# 게시문 Category -> (마커 색 등급, 한국어 표기)
CATEGORY = {
    "warning": ("Red", "경보 (Warning)"),
    "advisory": ("Orange", "주의보 (Advisory)"),
    "watch": ("Orange", "감시 (Watch)"),
    "information": ("Green", "정보 (Information)"),
}


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def summary_text(entry):
    node = entry.find(f"{{{ATOM_NS}}}summary")
    if node is None:
        return ""
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def field(summary, label):
    """'Category: Information' 처럼 라벨 뒤에 붙는 값을 다음 라벨 전까지 잘라 온다."""
    labels = "Category|Bulletin Issue Time|Preliminary Magnitude|Lat/Lon|Affected Region|Note|Definition"
    matched = re.search(rf"{label}:\s*(.*?)(?=(?:{labels}):|$)", summary)
    return matched.group(1).strip() if matched else ""


def parse_magnitude(raw):
    matched = re.search(r"(\d+(?:\.\d+)?)", raw or "")
    return float(matched.group(1)) if matched else 0.0


def parse_updated(raw):
    try:
        return datetime.strptime((raw or "").strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def bulletin_url(entry):
    for link in entry.findall(f"{{{ATOM_NS}}}link"):
        if link.get("rel") == "alternate":
            return link.get("href") or ""
    return "https://www.tsunami.gov/"


def parse_center(xml_bytes, center, center_name):
    root = ET.fromstring(xml_bytes)
    incidents = []
    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        coordinates = valid_coordinates(
            entry.findtext(f"{{{GEO_NS}}}lat"),
            entry.findtext(f"{{{GEO_NS}}}long"),
        )
        if coordinates is None:
            continue
        lat, lon = coordinates
        summary = summary_text(entry)
        category = field(summary, "Category").lower()
        tag, category_ko = CATEGORY.get(category, ("Green", category.title() or "정보"))
        magnitude = parse_magnitude(field(summary, "Preliminary Magnitude"))
        region = field(summary, "Affected Region") or (entry.findtext(f"{{{ATOM_NS}}}title") or "").strip()

        incidents.append({
            "lat": lat,
            "lon": lon,
            "name": region or "발생 해역 미상",
            "country": center_name,
            "dateadded": iso_utc(parse_updated(entry.findtext(f"{{{ATOM_NS}}}updated"))),
            "threat": f"{category_ko} · 규모 {magnitude:.1f}" if magnitude else category_ko,
            "tags": tag,
            "severity": round(magnitude * 10, 1),
            "magnitude": magnitude,
            "center": center,
            "note": (field(summary, "Note") or "").strip()[:200],
            "reportUrl": bulletin_url(entry),
        })
    return incidents


def main():
    incidents = []
    for center, (url, center_name) in CENTERS.items():
        try:
            found = parse_center(fetch(url), center, center_name)
        except Exception as error:  # 한 센터가 죽어도 나머지는 살린다
            print(f"{center} 조회 실패: {error}", file=sys.stderr)
            continue
        print(f"{center}: {len(found)}건", file=sys.stderr)
        incidents.extend(found)

    incidents.sort(key=lambda item: item["dateadded"], reverse=True)
    alerts = sum(1 for i in incidents if i["tags"] != "Green")
    write_feed(OUTPUT_PATH, {
        "generated_at": now_iso(),
        "source": "NOAA NTWC (PAAQ) + PTWC (PHEB) tsunami bulletins",
        "tsunami": incidents,
    })
    print(f"쓰나미 저장: {len(incidents)}건 (경보/주의 {alerts}건) -> {OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
