#!/usr/bin/env python3
"""Smithsonian GVP 주간 화산활동 보고서(좌표)와 USGS HANS 경보등급을 병합해
data/volcano_incidents.json으로 저장한다. GitHub Actions에서 주기 실행.

GVP 주간 보고서는 전 지구 화산의 좌표·활동 요약을 주는 대신 경보등급이 없고,
USGS HANS는 경보등급을 주는 대신 좌표가 없다. 둘을 화산명으로 매칭해 보완한다.
"""
import json
import re
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# 직접 실행(python scripts/build_x.py)과 패키지 import(scripts.build_x) 양쪽을 지원한다
try:
    from feed_common import UA, iso_utc, now_iso, write_feed
except ImportError:  # pragma: no cover - 테스트에서 패키지로 import 될 때
    from scripts.feed_common import UA, iso_utc, now_iso, write_feed

GVP_RSS = "https://volcano.si.edu/news/WeeklyVolcanoRSS.xml"
USGS_ELEVATED = "https://volcanoes.usgs.gov/hans-public/api/volcano/getElevatedVolcanoes"
GEORSS_NS = "http://www.georss.org/georss"
OUTPUT_PATH = Path("data/volcano_incidents.json")

# USGS 경보등급 -> (마커 색 등급, 링 크기용 점수, 한국어 표기)
USGS_ALERT = {
    "NORMAL": ("Green", 20, "정상 (Normal)"),
    "ADVISORY": ("Orange", 45, "주의 (Advisory)"),
    "WATCH": ("Orange", 70, "감시 (Watch)"),
    "WARNING": ("Red", 100, "경보 (Warning)"),
}


def korean_status(status):
    """GVP 활동 구분('New Eruptive Activity')을 한국어로 바꾼다."""
    text = (status or "").lower()
    if "erupt" in text:
        activity = "분출"
    elif "unrest" in text:
        activity = "전조활동"
    else:
        return (status or "활동 보고").strip()
    return f"신규 {activity}" if text.startswith("new") else f"{activity} 지속"


def classify_gvp(status):
    """GVP 주간 보고서 활동 구분 -> (마커 색 등급, 링 크기용 점수).

    GVP는 경보를 발령하지 않으므로 보고서 문구로 대체 표기한다. 실제 관측된 값은
    {New, Continuing} x {Eruptive Activity, Unrest} 조합이다.

    주간 보고서에 실린 화산은 전부 활동 중이라 활동 유무로 색을 나누면 모두 같은
    색이 된다. 그래서 두 축을 분리한다 — 색(tags)은 '이번 주에 새로 생긴 변화인가',
    링 크기(severity)는 '활동이 얼마나 강한가(분출 > 전조)'.
    """
    text = (status or "").lower()
    is_new = text.startswith("new")
    if "erupt" in text:
        return ("Orange" if is_new else "Green", 70 if is_new else 55)
    if "unrest" in text:
        return ("Orange" if is_new else "Green", 45 if is_new else 30)
    return ("Green", 30)


def fetch(url, timeout=45):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def normalize_name(name):
    """화산명 매칭 키 — 발음기호·공백·대소문자 차이를 제거한다."""
    decomposed = unicodedata.normalize("NFKD", name or "")
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", ascii_only.lower())


def strip_html(html):
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", text).strip()


def parse_title(title):
    """'Esan (Japan) - Report for 6 August-12 August 2026 - New Unrest' 를 분해한다."""
    name, country, status = title.strip(), "", ""
    matched = re.match(r"^(.*?)\s*\(([^)]*)\)\s*(.*)$", title.strip())
    if matched:
        name = matched.group(1).strip()
        country = matched.group(2).strip()
        rest = matched.group(3)
        parts = [p.strip() for p in rest.split(" - ") if p.strip()]
        if parts:
            status = parts[-1]
    return name, country, status


def coordinates_of(item):
    point = (item.findtext(f"{{{GEORSS_NS}}}point") or "").split()
    if len(point) < 2:
        return None
    try:
        lat, lon = float(point[0]), float(point[1])
    except ValueError:
        return None
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return lat, lon


def parse_pubdate(raw):
    try:
        return parsedate_to_datetime(raw).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def fetch_usgs_alerts():
    """화산명(정규화) -> (등급, 점수, 원문 경보명) 매핑. 실패해도 GVP 단독으로 진행한다."""
    try:
        rows = json.loads(fetch(USGS_ELEVATED, timeout=30).decode("utf-8"))
    except Exception as error:  # 부가 정보이므로 실패를 치명적으로 다루지 않는다
        print(f"USGS HANS 조회 실패(GVP 단독 진행): {error}", file=sys.stderr)
        return {}
    alerts = {}
    for row in rows:
        level = (row.get("alert_level") or "").upper()
        if level not in USGS_ALERT:
            continue
        alerts[normalize_name(row.get("volcano_name"))] = USGS_ALERT[level]
    return alerts


def parse_gvp(xml_bytes, alerts):
    root = ET.fromstring(xml_bytes)
    incidents = []
    for item in root.findall(".//item"):
        coordinates = coordinates_of(item)
        if coordinates is None:
            continue
        lat, lon = coordinates
        name, country, status = parse_title(item.findtext("title") or "")
        published = parse_pubdate(item.findtext("pubDate"))

        status_ko = korean_status(status)
        usgs = alerts.get(normalize_name(name))
        if usgs:
            tag, score, level_text = usgs
            threat = f"USGS 경보 {level_text} · {status_ko}"
        else:
            tag, score = classify_gvp(status)
            threat = status_ko

        summary = strip_html(item.findtext("description"))
        incidents.append({
            "lat": lat,
            "lon": lon,
            "name": name or "이름 미상",
            "country": country or "미상",
            "dateadded": iso_utc(published),
            "threat": threat,
            "tags": tag,
            "severity": score,
            "summary": summary[:300],
            "reportUrl": (item.findtext("guid") or item.findtext("link")
                          or "https://volcano.si.edu/reports_weekly.cfm").strip(),
        })
    incidents.sort(key=lambda item: item["dateadded"], reverse=True)
    return incidents


def main():
    alerts = fetch_usgs_alerts()
    incidents = parse_gvp(fetch(GVP_RSS), alerts)
    matched = sum(1 for i in incidents if i["threat"].startswith("USGS 경보"))
    write_feed(OUTPUT_PATH, {
        "generated_at": now_iso(),
        "source": "Smithsonian GVP Weekly Volcanic Activity Report + USGS HANS alert levels",
        "volcano": incidents,
    })
    print(
        f"화산 저장: {len(incidents)}건 (USGS 경보 매칭 {matched}건) -> {OUTPUT_PATH}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
