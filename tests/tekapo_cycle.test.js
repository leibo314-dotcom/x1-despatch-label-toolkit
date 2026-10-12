import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../public/tekapo-cycle.js', import.meta.url), 'utf8');

function page({ theme = 'tekapo-minimal', type = 'upload', now = 100000, stored, blocked = false, form = null } = {}) {
  const storage = stored ?? new Map();
  const timers = new Map();
  const properties = new Map();
  const events = {};
  let clock = now;
  let observeTheme;
  let timerId = 0;
  const root = {
    dataset: { theme },
    style: {
      setProperty: (key, value) => properties.set(key, value),
      removeProperty: (key) => properties.delete(key),
    },
  };
  const context = {
    document: { documentElement: root, body: { dataset: { page: type } }, querySelector: () => form },
    window: { addEventListener: (key, callback) => { events[key] = callback; } },
    sessionStorage: {
      getItem: (key) => { if (blocked) throw Error('blocked'); return storage.get(key) ?? null; },
      setItem: (key, value) => { if (blocked) throw Error('blocked'); storage.set(key, value); },
      removeItem: (key) => { if (blocked) throw Error('blocked'); storage.delete(key); },
    },
    MutationObserver: class { constructor(callback) { observeTheme = callback; } observe() {} },
    Date: { now: () => clock },
    setTimeout: (callback, delay) => { const id = ++timerId; timers.set(id, { at: clock + delay, callback }); return id; },
    clearTimeout: (id) => timers.delete(id),
  };
  vm.runInNewContext(source, context);
  return {
    api: context.window.X1Scenery, root, storage, properties,
    theme(value) { root.dataset.theme = value; observeTheme(); },
    advance(ms) {
      const end = clock + ms;
      for (;;) {
        const next = [...timers].filter(([, item]) => item.at <= end).sort((a, b) => a[1].at - b[1].at)[0];
        if (!next) break;
        clock = next[1].at;
        timers.delete(next[0]);
        next[1].callback();
      }
      clock = end;
    },
  };
}

test('fast generation completes one cycle without stopping as soon as the PDF is ready', () => {
  const app = page();
  app.api.start();
  app.advance(1000);
  app.api.complete();
  app.advance(14999);
  assert.equal(app.root.dataset.scenery, 'running');
  app.advance(1);
  assert.equal(app.root.dataset.scenery, undefined);
  assert.equal(app.storage.size, 0);
});

test('upload navigation resumes the same phase and long generation finishes its current cycle', () => {
  const upload = page();
  upload.api.start();
  const result = page({ type: 'result', now: 106000, stored: upload.storage });
  assert.equal(result.properties.get('--scenery-delay'), '-6s');
  result.api.start();
  result.advance(15000);
  result.api.complete();
  result.advance(10999);
  assert.equal(result.root.dataset.scenery, 'running');
  result.advance(1);
  assert.equal(result.root.dataset.scenery, undefined);
});

test('retry resumes processing without an earlier completion timer stopping it', () => {
  const app = page();
  app.api.start();
  app.api.complete();
  app.advance(5000);
  app.api.start();
  app.advance(12000);
  assert.equal(app.root.dataset.scenery, 'running');
  app.api.reset();
  assert.equal(app.root.dataset.scenery, undefined);
});

test('other themes stay unchanged and switching away clears the animation', () => {
  const standard = page({ theme: 'standard' });
  standard.api.start();
  assert.equal(standard.root.dataset.scenery, undefined);
  const app = page();
  app.api.start();
  app.theme('sakura');
  assert.equal(app.root.dataset.scenery, undefined);
  assert.equal(app.storage.size, 0);
});

test('storage failures do not break generation or same-page animation', () => {
  const app = page({ blocked: true });
  app.api.start();
  assert.equal(app.root.dataset.scenery, 'running');
  app.api.complete();
  app.advance(16000);
  assert.equal(app.root.dataset.scenery, undefined);
});

test('error pages and stale result visits clear previous runs', () => {
  const upload = page();
  upload.api.start();
  const error = page({ type: 'error', stored: upload.storage });
  assert.equal(error.storage.size, 0);
  upload.api.start();
  const stale = page({ type: 'result', now: 1100000, stored: upload.storage });
  assert.equal(stale.root.dataset.scenery, undefined);
  assert.equal(stale.storage.size, 0);
});

function nativeForm(size) {
  let submit;
  return {
    dataset: { blobUploadEnabled: 'false', maxUploadBytes: '26214400' },
    querySelector: () => ({ files: [{ name: 'schedule.pdf', size }] }),
    checkValidity: () => true,
    addEventListener(event, callback) { if (event === 'submit') submit = callback; },
    submit() { submit({ defaultPrevented: false }); },
  };
}

test('native uploads within the configured size limit start the scenery', () => {
  const form = nativeForm(26214400);
  const app = page({ form });
  form.submit();
  assert.equal(app.root.dataset.scenery, 'running');
});

test('oversized native uploads do not start the scenery before the server rejects them', () => {
  const form = nativeForm(26214401);
  const app = page({ form });
  form.submit();
  assert.equal(app.root.dataset.scenery, undefined);
  assert.equal(app.storage.size, 0);
});

function outputsPage() {
  const calls = { start: 0, complete: 0, reset: 0 };
  const requests = [];
  const cards = ['docket', 'labels'].map((output) => {
    const elements = new Map();
    return {
      dataset: { output, ready: 'false' },
      querySelector(selector) {
        if (!elements.has(selector)) elements.set(selector, { hidden: true, textContent: '', addEventListener() {} });
        return elements.get(selector);
      },
    };
  });
  vm.runInNewContext(readFileSync(new URL('../public/outputs.js', import.meta.url), 'utf8'), {
    document: { querySelector: () => ({ dataset: { job: 'test' } }), querySelectorAll: () => cards },
    window: { X1Scenery: Object.fromEntries(Object.keys(calls).map((name) => [name, () => { calls[name]++; }])) },
    fetch: (url) => new Promise((resolve) => requests.push({ url, resolve })),
  });
  return {
    calls, cards, requests,
    async settle(index, ok) {
      requests[index].resolve({ ok, json: async () => ({ status: ok ? 'ready' : 'error', error: 'Failed' }) });
      await new Promise((resolve) => setImmediate(resolve));
    },
  };
}

test('PDF requests run independently and downloads become usable before the cycle finishes', async () => {
  const app = outputsPage();
  assert.equal(app.requests.length, 2);
  assert.equal(app.calls.start, 1);
  await app.settle(0, true);
  assert.equal(app.cards[0].querySelector('[data-output-download]').hidden, false);
  assert.equal(app.calls.complete, 0);
  await app.settle(1, true);
  assert.equal(app.cards[1].querySelector('[data-output-download]').hidden, false);
  assert.equal(app.calls.complete, 1);
});

test('a failed output resets the scenery without blocking the other PDF', async () => {
  const app = outputsPage();
  await app.settle(0, false);
  assert.equal(app.calls.reset, 1);
  await app.settle(1, true);
  assert.equal(app.cards[1].querySelector('[data-output-download]').hidden, false);
  assert.equal(app.calls.complete, 0);
});
