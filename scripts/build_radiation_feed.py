#!/usr/bin/env python3
"""Safecast 실시간 센서망에서 환경 방사선을 수집해 data/radiation_incidents.json 에 저장한다.

Safecast 는 시민 참여형 관측망이라 관측 밀도가 일본·북미에 크게 편중돼 있다.
'전 지구 방사선 지도'가 아니라 '참여 관측망이 지금 재고 있는 값'으로 읽어야 한다.

계측관마다 환산계수가 달라, 계수가 공개된 LND7318(Safecast bGeigie 표준관)만 쓴다.
"""
import json
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 직접 실행(python scripts/build_x.py)과 패키지 import(scripts.build_x) 양쪽을 지원한다
try:
    from feed_common import UA, iso_utc, now_iso, valid_coordinates, write_feed
except ImportError:  # pragma: no cover - 테스트에서 패키지로 import 될 때
    from scripts.feed_common import UA, iso_utc, now_iso, valid_coordinates, write_feed

DEVICES_URL = "https://tt.safecast.org/devices"
SAFECAST_MAP = "https://map.safecast.org/"
OUTPUT_PATH = Path("data/radiation_incidents.json")

# Safecast bGeigie 표준 계측관(LND7318): 334 CPM = 1 μSv/h.
# 계수가 다른 관(lnd_712u 등)은 값이 섞이면 비교가 불가능해 제외한다.
LND7318_KEYS = ("lnd_7318u", "lnd_7318c")
CPM_PER_USVH = 334.0
MAX_AGE_DAYS = 14

# μSv/h -> (마커 색 등급, 한국어 표기). 자연 배경방사선은 통상 0.05~0.20 μSv/h.
DOSE_BANDS = [
    (0.25, "Green", "평상 수준"),
    (1.00, "Orange", "주의 관찰"),
    (float("inf"), "Red", "높음"),
]

# (이름, 위도 최소, 위도 최대, 경도 최소, 경도 최대) — 마커 묶음용 대략 구분
REGIONS = [
    ("동아시아", 20, 50, 100, 150),
    ("동남·남아시아", -12, 30, 60, 100),
    ("오세아니아", -50, -10, 110, 180),
    ("유럽", 35, 72, -15, 45),
    ("북미", 15, 72, -170, -50),
    ("중남미", -56, 15, -95, -30),
    ("아프리카", -36, 37, -20, 52),
    ("중동·중앙아시아", 12, 48, 45, 75),
]


def fetch(url, timeout=60):
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def classify(dose):
    for limit, tag, label in DOSE_BANDS:
        if dose < limit:
            return tag, label
    return "Red", "높음"


def region_of(lat, lon):
    for name, lat_min, lat_max, lon_min, lon_max in REGIONS:
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return "기타 지역"


def parse_captured(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def reading_of(device):
    for key in LND7318_KEYS:
        value = device.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def build(devices, now=None):
    now = now or datetime.now(timezone.utc)
    oldest = now - timedelta(days=MAX_AGE_DAYS)
    incidents = []
    for device in devices:
        coordinates = valid_coordinates(device.get("loc_lat"), device.get("loc_lon"))
        cpm = reading_of(device)
        captured = parse_captured(device.get("when_captured"))
        if coordinates is None or cpm is None or captured is None:
            continue
        if not oldest <= captured <= now + timedelta(days=1):
            continue  # 미래 시각·수년 전 값은 고장난 기기다

        lat, lon = coordinates
        dose = cpm / CPM_PER_USVH
        tag, label = classify(dose)
        region = region_of(lat, lon)
        incidents.append({
            "lat": lat,
            "lon": lon,
            "name": device.get("device_sn") or str(device.get("device") or "센서"),
            "country": region,
            "dateadded": iso_utc(captured),
            "threat": f"{label} · {dose:.3f} μSv/h ({cpm:.0f} CPM)",
            "tags": tag,
            "severity": round(dose * 100, 1),
            "band": label,
            "dose": round(dose, 3),
            "cpm": round(cpm, 1),
            "deviceClass": device.get("device_class") or "미상",
            "reportUrl": SAFECAST_MAP,
        })
    incidents.sort(key=lambda item: item["severity"], reverse=True)
    return incidents


def main():
    incidents = build(fetch(DEVICES_URL))
    elevated = sum(1 for i in incidents if i["tags"] != "Green")
    write_feed(OUTPUT_PATH, {
        "generated_at": now_iso(),
        "source": "Safecast realtime sensor network (LND7318 tubes, 334 CPM = 1 μSv/h)",
        "radiation": incidents,
    })
    print(
        f"방사선 저장: {len(incidents)}개 센서 (평상 초과 {elevated}곳) -> {OUTPUT_PATH}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
