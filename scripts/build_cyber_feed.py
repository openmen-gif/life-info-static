#!/usr/bin/env python3
"""URLhaus 최근 악성 URL을 수집해 IP를 지오로케이션한 뒤 data/cyber_incidents.json으로 저장한다.
GitHub Actions에서 주기 실행(예: 20분 간격). 브라우저 CORS 제약 회피용 서버측 사전 가공.
"""
import csv
import io
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

URLHAUS_CSV = "https://urlhaus.abuse.ch/downloads/csv_recent/"
GEO_BATCH_URL = "http://ip-api.com/batch?fields=status,country,countryCode,lat,lon,query"
MAX_ENTRIES = 300
MAX_UNIQUE_IPS = 200
OUTPUT_PATH = "data/cyber_incidents.json"


def fetch_urlhaus_rows():
    req = urllib.request.Request(URLHAUS_CSV, headers={"User-Agent": "life-info-static-cyber-feed/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    lines = [ln for ln in raw.splitlines() if ln and not ln.startswith("#")]
    reader = csv.reader(lines)
    rows = []
    for row in reader:
        if len(row) < 9:
            continue
        rows.append({
            "id": row[0], "dateadded": row[1], "url": row[2], "url_status": row[3],
            "last_online": row[4], "threat": row[5], "tags": row[6],
            "urlhaus_link": row[7], "reporter": row[8],
        })
    return rows[:MAX_ENTRIES]


def extract_ip(url):
    try:
        host = urlparse(url).hostname
    except Exception:
        return None
    if host and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
        return host
    return None


def geolocate_batch(ips):
    result = {}
    for i in range(0, len(ips), 100):
        chunk = ips[i:i + 100]
        req = urllib.request.Request(
            GEO_BATCH_URL,
            data=json.dumps(chunk).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for entry in data:
            if entry.get("status") == "success":
                result[entry["query"]] = entry
        if i + 100 < len(ips):
            time.sleep(2)
    return result


def main():
    rows = fetch_urlhaus_rows()
    print(f"URLhaus 수집: {len(rows)}건", file=sys.stderr)

    ip_rows = []
    for row in rows:
        ip = extract_ip(row["url"])
        if ip:
            row["ip"] = ip
            ip_rows.append(row)
    print(f"IP 기반 URL: {len(ip_rows)}건", file=sys.stderr)

    unique_ips = list(dict.fromkeys(r["ip"] for r in ip_rows))[:MAX_UNIQUE_IPS]
    geo = geolocate_batch(unique_ips)
    print(f"지오로케이션 성공: {len(geo)}/{len(unique_ips)}", file=sys.stderr)

    incidents = []
    for row in ip_rows:
        g = geo.get(row["ip"])
        if not g:
            continue
        incidents.append({
            "ip": row["ip"],
            "url": row["url"],
            "dateadded": row["dateadded"],
            "threat": row["threat"],
            "tags": row["tags"],
            "urlhaus_link": row["urlhaus_link"],
            "country": g["country"],
            "countryCode": g["countryCode"],
            "lat": g["lat"],
            "lon": g["lon"],
        })

    out = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "abuse.ch URLhaus (recent malware-hosting URLs) + ip-api.com geolocation",
        "count": len(incidents),
        "incidents": incidents,
    }
    import os
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print(f"저장 완료: {OUTPUT_PATH} ({len(incidents)}건)", file=sys.stderr)


if __name__ == "__main__":
    main()
