#!/usr/bin/env python3
"""GDACS RSS 하나에서 산불·태풍·홍수·가뭄 4종 스냅샷을 만들어 GitHub Pages에 올린다."""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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


def parse_impact(text):
    """GDACS 홍수 피해 문구('8 deaths and 7359 displaced')를 한국어 문구와 숫자로 분해한다.

    반환: (한국어 문구, 사망자 수, 이재민 수)
    """
    def count(pattern):
        matched = re.search(pattern, text or "")
        return int(matched.group(1).replace(",", "")) if matched else 0

    deaths = count(r"([\d,]+)\s+deaths?")
    displaced = count(r"([\d,]+)\s+displaced")
    parts = []
    if re.search(r"[\d,]+\s+deaths?", text or ""):
        parts.append(f"사망 {deaths:,}명")
    if displaced:
        parts.append(f"이재민 {displaced:,}명")
    return " · ".join(parts) if parts else (text or "").strip(), deaths, displaced


DROUGHT_IMPACT = {"minor": "영향 경미", "medium": "영향 보통", "high": "영향 큼", "severe": "영향 심각"}


def korean_drought(text):
    """GDACS 가뭄 문구('Minor impact for agricultural drought')를 한국어로 바꾼다."""
    lowered = (text or "").lower()
    for english, korean in DROUGHT_IMPACT.items():
        if lowered.startswith(english):
            return f"농업 가뭄 · {korean}"
    return (text or "").strip() or "가뭄"


def short_region(countries):
    """다국가 묶음('Ethiopia, Kenya, Somalia')을 'Ethiopia 외 2개국'으로 줄인다.

    가뭄은 여러 나라에 걸쳐 발생해 국가 문자열이 길다. 목록·차트는 짧은 이름으로
    묶고, 전체 목록은 별도 필드로 남겨 상세 패널에서 보여준다.
    """
    names = [c.strip() for c in (countries or "").split(",") if c.strip()]
    if not names:
        return "미상"
    return names[0] if len(names) == 1 else f"{names[0]} 외 {len(names) - 1}개국"


def to_iso(raw):
    """GDACS의 RFC822 날짜를 접미사 Z 없는 UTC ISO로 바꾼다.

    모니터 HTML의 timeAgo()는 `iso.replace(' ','T') + 'Z'` 로 파싱하는데,
    RFC822("Thu, 23 Jul 2026 06:00:00 GMT")를 넣으면 첫 공백만 치환돼
    Invalid Date -> "NaN일 전"이 된다.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    for parse in (parsedate_to_datetime, datetime.fromisoformat):
        try:
            moment = parse(raw.replace("Z", "+00:00") if parse is datetime.fromisoformat else raw)
        except (TypeError, ValueError):
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return raw  # 알 수 없는 형식이면 원문을 보존한다 — 날짜를 통째로 잃는 것보다 낫다


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
    grouped = {"wildfire": [], "typhoon": [], "flood": [], "drought": []}
    kinds = {"WF": "wildfire", "TC": "typhoon", "FL": "flood", "DR": "drought"}

    for item in root.findall(".//item"):
        kind = kinds.get(text_of(item, "eventtype"))
        if not kind:
            continue
        severity = item.find(f"{{{GDACS_NS}}}severity")
        population = item.find(f"{{{GDACS_NS}}}population")
        name = text_of(item, "eventname") or (item.findtext("title") or "").strip()
        coordinates = coordinates_of(item)
        if coordinates is None:
            continue
        lat, lon = coordinates

        severity_value = parse_number(severity.get("value") if severity is not None else 0)
        severity_text = (severity.text or "").strip() if severity is not None else ""
        population_value = parse_number(population.get("value") if population is not None else 0)
        population_text = (population.text or "").strip() if population is not None else ""
        # 홍수는 severity 가 항상 "Magnitude 0" 으로 와서 강도 비교가 불가능하다.
        # GDACS 가 홍수 피해를 담아 보내는 population(사망·이재민)을 강도 지표로 대신 쓴다.
        countries = text_of(item, "country")
        display_country = countries
        deaths = displaced = 0
        if kind == "drought":
            severity_text = korean_drought(severity_text)
            display_country = short_region(countries)
        if kind == "flood":
            severity_text, deaths, displaced = parse_impact(population_text)
            severity_text = severity_text or "영향 규모 미상"
            # 사망자만 쓰면 대부분 0이라 확산 링이 전부 최소 크기가 된다.
            # 이재민을 200명당 1점으로 환산해 더한 영향도를 링 크기 지표로 쓴다.
            severity_value = deaths + displaced / 200

        grouped[kind].append({
            "lat": lat,
            "lon": lon,
            "name": name or "이름 미상",
            "country": display_country,
            "countries": countries,
            "dateadded": to_iso(text_of(item, "fromdate") or text_of(item, "datemodified")),
            "threat": severity_text or "—",
            "tags": text_of(item, "alertlevel") or "Green",
            "severity": round(severity_value, 1),
            "deaths": deaths,
            "displaced": displaced,
            "population": population_text,
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
    print(
        "GDACS RSS 저장: " + ", ".join(f"{kind}={len(items)}" for kind, items in grouped.items()),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
