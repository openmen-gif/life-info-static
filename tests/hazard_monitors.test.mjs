import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

// 4개 모니터는 typhoon_monitor.html 을 기준으로 생성된 클론이라, 개별 파일을 복제해
// 검사하는 대신 표로 한 번에 검증한다. 항목이 어긋나면 어느 모니터인지 바로 드러난다.
const MONITORS = [
  { file: 'flood_monitor.html', brand: 'FLOOD WATCH',
    data: 'data/gdacs_incidents.json', key: 'flood', accent: '#22d3ee', unit: '명' },
  { file: 'volcano_monitor.html', brand: 'VOLCANO WATCH',
    data: 'data/volcano_incidents.json', key: 'volcano', accent: '#ff5252', unit: 'LV' },
  { file: 'tsunami_monitor.html', brand: 'TSUNAMI WATCH',
    data: 'data/tsunami_incidents.json', key: 'tsunami', accent: '#8b7cff', unit: 'M' },
  { file: 'airquality_monitor.html', brand: 'AIR QUALITY WATCH',
    data: 'data/airquality_incidents.json', key: 'airquality', accent: '#a3e635', unit: 'AQI' },
];

const read = (file) => readFile(path.resolve(file), 'utf8');

for (const monitor of MONITORS) {
  test(`${monitor.file} reads its own same-origin snapshot`, async () => {
    const page = await read(monitor.file);

    assert.match(page, new RegExp(`fetch\\('${monitor.data.replace(/[/.]/g, '\\$&')}'`));
    assert.match(page, new RegExp(`snapshot\\.${monitor.key}`));
  });

  test(`${monitor.file} carries its own branding, accent and badge unit`, async () => {
    const page = await read(monitor.file);

    assert.match(page, new RegExp(`<h1>${monitor.brand}</h1>`));
    assert.ok(page.includes(`--accent:${monitor.accent};`), 'accent 색이 설정과 다름');
    assert.ok(page.includes(`<span class="u">${monitor.unit}</span>`), 'badge 단위가 설정과 다름');
  });

  test(`${monitor.file} keeps no leftover typhoon template text`, async () => {
    const page = await read(monitor.file);

    for (const leftover of ['TYPHOON WATCH', '태풍', '열대저기압', 'snapshot.typhoon', 'KM/H']) {
      assert.ok(!page.includes(leftover), `템플릿 잔재 발견: ${leftover}`);
    }
  });

  test(`${monitor.file} parses dates through the tolerant parseUtc helper`, async () => {
    const page = await read(monitor.file);

    // new Date(iso.replace(' ','T')+'Z') 만 쓰면 RFC822 날짜에서 "NaN일 전"이 된다
    assert.match(page, /function parseUtc\(raw\)/);
    assert.match(page, /const t = parseUtc\(iso\);/);
    assert.ok(!/const t = new Date\(iso\.replace/.test(page), 'timeAgo 가 견고한 파서를 쓰지 않음');
  });

  test(`${monitor.file} uses a private cache key so monitors do not clobber each other`, async () => {
    const page = await read(monitor.file);
    const slug = monitor.file.replace('_monitor.html', '');

    assert.match(page, new RegExp(`const CACHE_KEY = '${slug}-monitor:`));
  });
}

test('each monitor uses a distinct accent colour', () => {
  const accents = MONITORS.map((m) => m.accent);

  assert.equal(new Set(accents).size, accents.length);
});

test('tsunami badge shows the raw magnitude, not the scaled ring metric', async () => {
  const page = await read('tsunami_monitor.html');

  // severity 는 규모x10 이라 배지에 그대로 쓰면 규모 4.0 이 40 으로 보인다
  assert.match(page, /\(inc\.magnitude \?\? 0\)\.toFixed\(1\)/);
  assert.ok(!page.includes("dCC').textContent = Math.round(inc.severity"),
    '쓰나미 배지가 severity 를 그대로 쓰고 있음');
});

test('air quality detail panel exposes ozone and both particulate sizes', async () => {
  const page = await read('airquality_monitor.html');

  for (const id of ['dOzone', 'dPm25', 'dPm10', 'dNo2', 'dSo2', 'dCo', 'dDust', 'dUv', 'dUsAqi']) {
    assert.ok(page.includes(`id="${id}"`), `상세 항목 누락: ${id}`);
  }
  assert.match(page, /오존 O₃/);
  assert.match(page, /inc\.ozone/);
});

test('air quality ranks by severity because every city shares one timestamp', async () => {
  const page = await read('airquality_monitor.html');

  assert.match(page, /sort\(\(\(a,b\) => \(b\.severity\|\|0\) - \(a\.severity\|\|0\)\)\)/);
});
