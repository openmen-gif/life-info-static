#!/usr/bin/env python3
"""NOAA SWPC 자료로 지자기 폭풍 감시 스냅샷을 만들어 data/spaceweather_incidents.json 에 저장한다.

지자기 폭풍은 GPS 정밀도·극지 항공 통신·위성에 영향을 준다. 그 교란이 집중되는 곳이
오로라대(auroral oval)라, OVATION 오로라 예보 격자를 지구본 마커로 쓰고
Kp 지수(전 지구 지자기 교란 세기)를 함께 실어 등급 판정에 반영한다.
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# 직접 실행(python scripts/build_x.py)과 패키지 import(scripts.build_x) 양쪽을 지원한다
try:
    from feed_common import UA, now_iso, valid_coordinates, write_feed
except ImportError:  # pragma: no cover - 테스트에서 패키지로 import 될 때
    from scripts.feed_common import UA, now_iso, valid_coordinates, write_feed

OVATION_URL = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
FORECAST_PAGE = "https://www.swpc.noaa.gov/products/aurora-30-minute-forecast"
OUTPUT_PATH = Path("data/spaceweather_incidents.json")

# 격자 65,160점을 그대로 그리면 화면이 뭉개진다. 셀 하나당 최댓값만 남겨 솎아낸다.
# 8x5 / 최소 3% 는 오로라대 형태를 유지하면서 약 470개로 줄어드는 값이다(실측).
LON_CELL = 8
LAT_CELL = 5
MIN_PROBABILITY = 3
MAX_MARKERS = 500

# 오로라 관측 확률(%) -> 한국어 표기. 확률은 링 크기(severity)로만 쓴다.
PROBABILITY_BANDS = [(10, "약함"), (30, "보통"), (60, "강함"), (float("inf"), "매우 강함")]

# Kp 지수 -> (마커 색 등급, NOAA G-scale 폭풍 등급)
# 조용한 날에도 극지 오로라 확률은 30%대까지 올라간다. 확률로 색을 매기면 평시에도
# 전부 주의색이 되므로, 색은 실제 위험 지표인 Kp(전 지구 지자기 교란)로 정한다.
KP_STORM = [
    (5, "Green", "폭풍 없음"),
    (6, "Orange", "G1 약한 폭풍"),
    (7, "Orange", "G2 보통 폭풍"),
    (8, "Red", "G3 강한 폭풍"),
    (9, "Red", "G4 심각한 폭풍"),
    (float("inf"), "Red", "G5 극심한 폭풍"),
]


def fetch(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def probability_label(probability):
    for limit, label in PROBABILITY_BANDS:
        if probability < limit:
            return label
    return "매우 강함"


def storm_level(kp):
    """Kp 지수 -> (마커 색 등급, 폭풍 등급). Kp를 모르면 관심(Green)으로 둔다."""
    if kp is None:
        return "Green", "Kp 미상"
    for limit, tag, label in KP_STORM:
        if kp < limit:
            return tag, label
    return "Red", "G5 극심한 폭풍"


def latest_kp():
    """가장 최근 Kp 지수. 실패해도 오로라 격자만으로 진행한다."""
    try:
        rows = fetch(KP_URL, timeout=30)
    except Exception as error:
        print(f"Kp 지수 조회 실패(오로라 단독 진행): {error}", file=sys.stderr)
        return None
    values = [r.get("Kp") for r in rows if isinstance(r, dict) and isinstance(r.get("Kp"), (int, float))]
    return float(values[-1]) if values else None


def normalize_longitude(lon):
    """OVATION 격자는 경도가 0~359로 오므로 -180~180으로 옮긴다."""
    return lon - 360 if lon > 180 else lon


def to_iso(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return now_iso()


def thin_grid(coordinates):
    """셀별 최댓값만 남겨 격자를 솎아낸다. 반환: [(lat, lon, 확률), ...]"""
    best = {}
    for point in coordinates:
        if len(point) < 3:
            continue
        lon, lat, probability = point[0], point[1], point[2]
        if probability < MIN_PROBABILITY:
            continue
        cell = (round(lat / LAT_CELL), round(lon / LON_CELL))
        if probability > best.get(cell, (0, 0, -1))[2]:
            best[cell] = (lat, normalize_longitude(lon), probability)
    ranked = sorted(best.values(), key=lambda item: item[2], reverse=True)
    return ranked[:MAX_MARKERS]


def build(ovation, kp):
    observed = to_iso(ovation.get("Observation Time"))
    tag, storm = storm_level(kp)
    kp_text = f"Kp {kp:.1f} · {storm}" if kp is not None else storm

    incidents = []
    for lat, lon, probability in thin_grid(ovation.get("coordinates") or []):
        coordinates = valid_coordinates(lat, lon)
        if coordinates is None:
            continue
        label = probability_label(probability)
        hemisphere = "북반구 오로라대" if lat >= 0 else "남반구 오로라대"
        incidents.append({
            "lat": coordinates[0],
            "lon": coordinates[1],
            "name": f"{abs(lat):.0f}°{'N' if lat >= 0 else 'S'} {abs(lon):.0f}°{'E' if lon >= 0 else 'W'}",
            "country": hemisphere,
            "dateadded": observed,
            "threat": f"오로라 {label} {probability:.0f}% · {kp_text}",
            "tags": tag,
            "severity": round(float(probability), 1),
            "band": label,
            "kp": kp,
            "storm": storm,
            "reportUrl": FORECAST_PAGE,
        })
    return incidents, kp, storm


def main():
    ovation = fetch(OVATION_URL)
    incidents, kp, storm = build(ovation, latest_kp())
    strong = sum(1 for i in incidents if i["tags"] != "Green")
    write_feed(OUTPUT_PATH, {
        "generated_at": now_iso(),
        "source": "NOAA SWPC OVATION aurora forecast + planetary K-index",
        "kp": kp,
        "storm": storm,
        "spaceweather": incidents,
    })
    print(
        f"우주기상 저장: {len(incidents)}개 지점 (보통 이상 {strong}곳) · {storm} -> {OUTPUT_PATH}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
