#!/usr/bin/env python3
"""재난 피드 빌더 공용 헬퍼.

모든 피드는 모니터 HTML이 그대로 읽는 동일한 계약을 지킨다:
    {lat, lon, name, country, dateadded, threat, tags, severity, reportUrl}
    tags     = "Green" | "Orange" | "Red"   (마커 색)
    severity = 숫자                          (확산 링 크기)
    dateadded= "YYYY-MM-DDTHH:MM:SS" (UTC, 접미사 Z 없음)
"""
import json
from datetime import datetime, timezone

UA = "life-info-static-hazard-feed/1.0"

# 모니터 HTML의 timeAgo()가 `iso.replace(' ','T') + 'Z'` 로 파싱하므로
# 접미사 Z 없는 ISO 형식이어야 한다. RFC822("Thu, 23 Jul ...")를 넣으면
# 첫 공백만 치환돼 Invalid Date -> "NaN일 전"이 된다.
ISO_FORMAT = "%Y-%m-%dT%H:%M:%S"


def now_iso():
    return datetime.now(timezone.utc).strftime(ISO_FORMAT)


def iso_utc(moment):
    """tz-aware datetime -> 접미사 Z 없는 UTC ISO 문자열."""
    if moment is None:
        return now_iso()
    return moment.astimezone(timezone.utc).strftime(ISO_FORMAT)


def valid_coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None
    return lat, lon


def write_feed(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
