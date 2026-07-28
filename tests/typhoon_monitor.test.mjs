import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

test('typhoon monitor reads the same-origin GDACS snapshot instead of a CORS-blocked direct API', async () => {
  const page = await readFile(path.resolve('typhoon_monitor.html'), 'utf8');

  assert.match(page, /fetch\('data\/gdacs_incidents\.json'/);
  assert.match(page, /snapshot\.typhoon/);
  assert.match(page, /GDACS 지연 · 캐시/);
});
