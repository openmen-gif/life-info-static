#!/usr/bin/env python3
"""Open-Meteo 대기질 API로 세계 주요도시의 오존·미세먼지를 수집해
data/airquality_incidents.json으로 저장한다. 키·회원가입 불필요.

한 요청에 여러 좌표를 넘길 수 있어 도시 수백 곳도 몇 번의 호출로 끝난다.
"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# 직접 실행(python scripts/build_x.py)과 패키지 import(scripts.build_x) 양쪽을 지원한다
try:
    from feed_common import UA, iso_utc, now_iso, valid_coordinates, write_feed
except ImportError:  # pragma: no cover - 테스트에서 패키지로 import 될 때
    from scripts.feed_common import UA, iso_utc, now_iso, valid_coordinates, write_feed

API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
OUTPUT_PATH = Path("data/airquality_incidents.json")
CHUNK_SIZE = 50
VARIABLES = [
    "pm10", "pm2_5", "ozone", "nitrogen_dioxide", "sulphur_dioxide",
    "carbon_monoxide", "dust", "uv_index", "european_aqi", "us_aqi",
]

# European AQI 구간 -> (마커 색 등급, 한국어 표기)
# 유럽환경청(EEA) 공식 6단계를 3색 체계로 접는다.
AQI_BANDS = [
    (20, "Green", "좋음"),
    (40, "Green", "양호"),
    (60, "Orange", "보통"),
    (80, "Orange", "나쁨"),
    (100, "Red", "매우 나쁨"),
    (float("inf"), "Red", "극히 나쁨"),
]

# (도시, 국가, 위도, 경도) — 한국 전역 + 대륙별 주요 도시
CITIES = [
    ("서울", "대한민국", 37.5665, 126.9780), ("부산", "대한민국", 35.1796, 129.0756),
    ("인천", "대한민국", 37.4563, 126.7052), ("대구", "대한민국", 35.8714, 128.6014),
    ("대전", "대한민국", 36.3504, 127.3845), ("광주", "대한민국", 35.1595, 126.8526),
    ("울산", "대한민국", 35.5384, 129.3114), ("수원", "대한민국", 37.2636, 127.0286),
    ("창원", "대한민국", 35.2280, 128.6811), ("제주", "대한민국", 33.4996, 126.5312),

    ("도쿄", "일본", 35.6762, 139.6503), ("오사카", "일본", 34.6937, 135.5023),
    ("베이징", "중국", 39.9042, 116.4074), ("상하이", "중국", 31.2304, 121.4737),
    ("광저우", "중국", 23.1291, 113.2644), ("선전", "중국", 22.5431, 114.0579),
    ("청두", "중국", 30.5728, 104.0668), ("시안", "중국", 34.3416, 108.9398),
    ("홍콩", "중국", 22.3193, 114.1694), ("타이베이", "대만", 25.0330, 121.5654),
    ("마닐라", "필리핀", 14.5995, 120.9842), ("자카르타", "인도네시아", -6.2088, 106.8456),
    ("방콕", "태국", 13.7563, 100.5018), ("하노이", "베트남", 21.0285, 105.8542),
    ("호치민", "베트남", 10.8231, 106.6297), ("싱가포르", "싱가포르", 1.3521, 103.8198),
    ("쿠알라룸푸르", "말레이시아", 3.1390, 101.6869), ("델리", "인도", 28.6139, 77.2090),
    ("뭄바이", "인도", 19.0760, 72.8777), ("콜카타", "인도", 22.5726, 88.3639),
    ("첸나이", "인도", 13.0827, 80.2707), ("다카", "방글라데시", 23.8103, 90.4125),
    ("카라치", "파키스탄", 24.8607, 67.0011), ("라호르", "파키스탄", 31.5204, 74.3587),
    ("카트만두", "네팔", 27.7172, 85.3240), ("울란바토르", "몽골", 47.8864, 106.9057),
    ("알마티", "카자흐스탄", 43.2220, 76.8512), ("타슈켄트", "우즈베키스탄", 41.2995, 69.2401),

    ("두바이", "아랍에미리트", 25.2048, 55.2708), ("리야드", "사우디아라비아", 24.7136, 46.6753),
    ("도하", "카타르", 25.2854, 51.5310), ("테헤란", "이란", 35.6892, 51.3890),
    ("바그다드", "이라크", 33.3152, 44.3661), ("이스탄불", "튀르키예", 41.0082, 28.9784),

    ("런던", "영국", 51.5074, -0.1278), ("파리", "프랑스", 48.8566, 2.3522),
    ("베를린", "독일", 52.5200, 13.4050), ("마드리드", "스페인", 40.4168, -3.7038),
    ("로마", "이탈리아", 41.9028, 12.4964), ("밀라노", "이탈리아", 45.4642, 9.1900),
    ("암스테르담", "네덜란드", 52.3676, 4.9041), ("브뤼셀", "벨기에", 50.8503, 4.3517),
    ("빈", "오스트리아", 48.2082, 16.3738), ("프라하", "체코", 50.0755, 14.4378),
    ("바르샤바", "폴란드", 52.2297, 21.0122), ("크라쿠프", "폴란드", 50.0647, 19.9450),
    ("부다페스트", "헝가리", 47.4979, 19.0402), ("부쿠레슈티", "루마니아", 44.4268, 26.1025),
    ("아테네", "그리스", 37.9838, 23.7275), ("스톡홀름", "스웨덴", 59.3293, 18.0686),
    ("오슬로", "노르웨이", 59.9139, 10.7522), ("코펜하겐", "덴마크", 55.6761, 12.5683),
    ("모스크바", "러시아", 55.7558, 37.6173), ("키이우", "우크라이나", 50.4501, 30.5234),
    ("리스본", "포르투갈", 38.7223, -9.1393),

    ("뉴욕", "미국", 40.7128, -74.0060), ("로스앤젤레스", "미국", 34.0522, -118.2437),
    ("시카고", "미국", 41.8781, -87.6298), ("휴스턴", "미국", 29.7604, -95.3698),
    ("샌프란시스코", "미국", 37.7749, -122.4194), ("시애틀", "미국", 47.6062, -122.3321),
    ("덴버", "미국", 39.7392, -104.9903), ("토론토", "캐나다", 43.6532, -79.3832),
    ("밴쿠버", "캐나다", 49.2827, -123.1207), ("멕시코시티", "멕시코", 19.4326, -99.1332),
    ("과테말라시티", "과테말라", 14.6349, -90.5069), ("보고타", "콜롬비아", 4.7110, -74.0721),
    ("리마", "페루", -12.0464, -77.0428), ("산티아고", "칠레", -33.4489, -70.6693),
    ("부에노스아이레스", "아르헨티나", -34.6037, -58.3816), ("상파울루", "브라질", -23.5505, -46.6333),
    ("리우데자네이루", "브라질", -22.9068, -43.1729), ("라파스", "볼리비아", -16.4897, -68.1193),

    ("카이로", "이집트", 30.0444, 31.2357), ("라고스", "나이지리아", 6.5244, 3.3792),
    ("나이로비", "케냐", -1.2921, 36.8219), ("요하네스버그", "남아프리카공화국", -26.2041, 28.0473),
    ("케이프타운", "남아프리카공화국", -33.9249, 18.4241), ("아디스아바바", "에티오피아", 9.0320, 38.7469),
    ("아크라", "가나", 5.6037, -0.1870), ("카사블랑카", "모로코", 33.5731, -7.5898),
    ("알제", "알제리", 36.7538, 3.0588), ("다르에스살람", "탄자니아", -6.7924, 39.2083),

    ("시드니", "호주", -33.8688, 151.2093), ("멜버른", "호주", -37.8136, 144.9631),
    ("브리즈번", "호주", -27.4698, 153.0251), ("퍼스", "호주", -31.9505, 115.8605),
    ("오클랜드", "뉴질랜드", -36.8485, 174.7633),
]


def classify(aqi):
    for limit, tag, label in AQI_BANDS:
        if aqi < limit:
            return tag, label
    return "Red", "극히 나쁨"


def fetch_chunk(cities):
    query = urllib.parse.urlencode({
        "latitude": ",".join(f"{c[2]:.4f}" for c in cities),
        "longitude": ",".join(f"{c[3]:.4f}" for c in cities),
        "current": ",".join(VARIABLES),
        "timezone": "UTC",
    })
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    # 좌표가 1곳이면 dict, 여러 곳이면 list 로 돌아온다
    return payload if isinstance(payload, list) else [payload]


def build_incident(city, block):
    name, country, lat, lon = city
    coordinates = valid_coordinates(lat, lon)
    if coordinates is None:
        return None
    current = (block or {}).get("current") or {}
    aqi = current.get("european_aqi")
    if aqi is None:
        return None
    tag, label = classify(aqi)

    def value(key):
        raw = current.get(key)
        return round(raw, 1) if isinstance(raw, (int, float)) else None

    measured = (current.get("time") or "").strip()
    return {
        "lat": coordinates[0],
        "lon": coordinates[1],
        "name": name,
        "country": country,
        "dateadded": measured if len(measured) > 16 else f"{measured}:00" if measured else now_iso(),
        "threat": f"{label} · AQI {round(aqi)}",
        "tags": tag,
        "severity": round(float(aqi), 1),
        "band": label,
        "ozone": value("ozone"),
        "pm2_5": value("pm2_5"),
        "pm10": value("pm10"),
        "no2": value("nitrogen_dioxide"),
        "so2": value("sulphur_dioxide"),
        "co": value("carbon_monoxide"),
        "dust": value("dust"),
        "uv": value("uv_index"),
        "usAqi": value("us_aqi"),
        "reportUrl": f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&current=european_aqi,ozone,pm2_5",
    }


def main():
    incidents = []
    for start in range(0, len(CITIES), CHUNK_SIZE):
        chunk = CITIES[start:start + CHUNK_SIZE]
        try:
            blocks = fetch_chunk(chunk)
        except Exception as error:
            print(f"{start}~{start + len(chunk)} 구간 실패: {error}", file=sys.stderr)
            continue
        if len(blocks) != len(chunk):
            print(f"경고: 요청 {len(chunk)}곳 대비 응답 {len(blocks)}곳", file=sys.stderr)
        for city, block in zip(chunk, blocks):
            incident = build_incident(city, block)
            if incident:
                incidents.append(incident)

    incidents.sort(key=lambda item: item["severity"], reverse=True)
    bad = sum(1 for i in incidents if i["tags"] != "Green")
    write_feed(OUTPUT_PATH, {
        "generated_at": now_iso(),
        "source": "Open-Meteo Air Quality API (CAMS 기반, 키 불필요)",
        "airquality": incidents,
    })
    print(
        f"대기질 저장: {len(incidents)}/{len(CITIES)}개 도시 (보통 이상 {bad}곳) -> {OUTPUT_PATH}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
