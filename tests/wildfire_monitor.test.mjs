import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

test('wildfire monitor reads a same-origin GDACS snapshot and uses its last successful browser snapshot on failure', async () => {
  const page = await readFile(path.resolve('wildfire_monitor.html'), 'utf8');

  assert.match(page, /fetch\('data\/gdacs_incidents\.json'/);
  assert.match(page, /snapshot\.wildfire/);
  assert.match(page, /localStorage\.setItem\(WILDFIRE_CACHE_KEY/);
  assert.match(page, /localStorage\.getItem\(WILDFIRE_CACHE_KEY/);
  assert.match(page, /GDACS 지연 · 캐시/);
});
