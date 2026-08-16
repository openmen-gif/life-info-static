# Life Info Static

02_생활정보 대시보드에서 사용하는 정적 HTML 위젯 호스팅 (GitHub Pages).

## 모니터

| 파일 | 화면 | 데이터 소스 | 갱신 |
|------|------|------------|------|
| `global_seismic_monitor.html` | SEISMOS — 전 지구 지진 | USGS Earthquake Hazards Program | 브라우저 직접 조회 |
| `typhoon_monitor.html` | TYPHOON WATCH — 태풍·열대저기압 | GDACS RSS (`TC`) | 15분 |
| `wildfire_monitor.html` | WILDFIRE WATCH — 산불 | GDACS RSS (`WF`) | 15분 |
| `flood_monitor.html` | FLOOD WATCH — 홍수 | GDACS RSS (`FL`) | 15분 |
| `drought_monitor.html` | DROUGHT WATCH — 가뭄 | GDACS RSS (`DR`) | 15분 |
| `volcano_monitor.html` | VOLCANO WATCH — 화산활동 | Smithsonian GVP 주간 보고서 + USGS HANS 경보등급 | 15분 (원본은 주 1회) |
| `tsunami_monitor.html` | TSUNAMI WATCH — 쓰나미 경보 | NOAA NTWC(PAAQ) + PTWC(PHEB) | 15분 |
| `airquality_monitor.html` | AIR QUALITY WATCH — 대기질·오존 | Open-Meteo Air Quality (Copernicus CAMS) | 15분 (원본은 1시간) |
| `spaceweather_monitor.html` | SPACE WEATHER — 지자기 폭풍 | NOAA SWPC OVATION 오로라 + Kp 지수 | 15분 |
| `radiation_monitor.html` | RADIATION WATCH — 환경 방사선 | Safecast 실시간 센서망 (LND7318) | 15분 |
| `cyber_threat_monitor.html` | 사이버 위협 | abuse.ch URLhaus + ip-api 지오로케이션 | 20분 |

모든 소스는 **API 키·회원가입이 필요 없습니다.**

> **방사선 모니터 주의**: Safecast 는 시민이 자발적으로 설치한 관측망이라 일본·유럽·북미에
> 센서가 몰려 있고 그 밖의 지역은 비어 있습니다. 지도에 점이 없는 것이 "방사선이 없다"는
> 뜻이 아닙니다. 국내 공식 수치는 원자력안전위원회 IERNet 을 확인하세요.

## 구조

브라우저 CORS 제약을 피하려고, 외부 API는 GitHub Actions가 **서버에서** 받아 `data/*.json`으로
떨궈 두고 페이지는 같은 출처(same-origin)에서 그 파일만 읽습니다.

```
.github/workflows/  cron -> 빌더 실행 -> data/*.json 커밋
scripts/            피드 빌더 (표준 라이브러리만 사용)
  feed_common.py    공용 헬퍼 + 데이터 계약 정의
data/               빌더 산출물 (모니터가 fetch 하는 파일)
tests/              빌더 단위 테스트 + 모니터 HTML 계약 테스트
```

## 데이터 계약

모니터 HTML은 소스가 달라도 **같은 형태의 배열** 하나만 읽습니다. 새 모니터를 추가하려면
빌더가 이 형태로 내보내기만 하면 됩니다.

| 필드 | 뜻 |
|------|-----|
| `lat` / `lon` | 좌표 (지구본 마커 위치) |
| `name` | 표시 이름 |
| `country` | 국가 또는 소속(쓰나미는 발령 센터) |
| `dateadded` | `YYYY-MM-DDTHH:MM:SS` — **UTC, 접미사 `Z` 없음** |
| `threat` | 사람이 읽는 상태 설명 |
| `tags` | `Green` / `Orange` / `Red` — 마커 색 |
| `severity` | 숫자 — 확산 링 크기 |
| `reportUrl` | 원본 상세 링크 |

> `dateadded`에 RFC822(`Thu, 23 Jul 2026 06:00:00 GMT`)를 넣으면 안 됩니다. 모니터의
> `timeAgo()`가 `replace(' ','T') + 'Z'`로 파싱해 첫 공백만 바뀌면서 `NaN일 전`이 됩니다.

## 실행

```bash
# 피드 빌드 (저장소 루트에서)
python scripts/build_gdacs_feed.py         # 산불 + 태풍 + 홍수 + 가뭄
python scripts/build_volcano_feed.py       # 화산
python scripts/build_tsunami_feed.py       # 쓰나미
python scripts/build_airquality_feed.py    # 대기질·오존
python scripts/build_spaceweather_feed.py  # 지자기 폭풍
python scripts/build_radiation_feed.py     # 환경 방사선
python scripts/build_cyber_feed.py         # 사이버 위협

# 테스트
python -m unittest tests.test_build_gdacs_feed tests.test_build_volcano_feed \
                   tests.test_build_tsunami_feed tests.test_build_airquality_feed \
                   tests.test_build_spaceweather_feed tests.test_build_radiation_feed
node --test tests/*.test.mjs

# 로컬 확인
python -m http.server 8777
```
