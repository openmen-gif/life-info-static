import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';

test('wildfire monitor aborts a stalled GDACS request and uses its last successful browser snapshot', async () => {
  const page = await readFile(path.resolve('wildfire_monitor.html'), 'utf8');

  assert.match(page, /GDACS_TIMEOUT_MS\s*=\s*10_000/);
  assert.match(page, /AbortController/);
  assert.match(page, /signal:\s*controller\.signal/);
  assert.match(page, /localStorage\.setItem\(WILDFIRE_CACHE_KEY/);
  assert.match(page, /localStorage\.getItem\(WILDFIRE_CACHE_KEY/);
  assert.match(page, /GDACS 지연 · 캐시/);
});
