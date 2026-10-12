import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import vm from 'node:vm';

const source = readFileSync(new URL('../public/tekapo-cycle.js', import.meta.url), 'utf8');

function media({ duration = 24, readyState = 4, rejected = false } = {}) {
  const events = {};
  return {
    dataset: { src: '/scene.mp4' }, duration, readyState, currentTime: 0,
    plays: 0, pauses: 0, loads: 0,
    load() { this.loads++; },
    play() { this.plays++; return rejected ? Promise.reject(Error('autoplay blocked')) : Promise.resolve(); },
    pause() { this.pauses++; },
    addEventListener(name, callback) { events[name] = callback; },
    emit(name) { events[name]?.(); },
  };
}

function page({ theme = 'tekapo-minimal', type = 'upload', now = 100000, stored, blocked = false,
                form = null, video = null, cityVideo = null, ready = [], reducedMotion = false } = {}) {
  const storage = stored ?? new Map();
  const timers = new Map();
  const properties = new Map();
  const events = {};
  let clock = now;
  let observeTheme;
  let observeMotion;
  let timerId = 0;
  const motionPreference = {
    matches: reducedMotion,
    addEventListener(name, callback) { observeMotion = callback; },
  };
  const root = {
    dataset: { theme },
    style: {
      setProperty: (key, value) => properties.set(key, value),
      removeProperty: (key) => properties.delete(key),
    },
  };
  const context = {
    document: {
      documentElement: root, body: { dataset: { page: type } }, hidden: false,
      querySelector: (selector) => ({ '.upload-form': form, '.scenery-video': video, '.city-video': cityVideo })[selector],
      querySelectorAll: () => ready.map((value) => ({ dataset: { ready: String(value) } })),
      addEventListener: (key, callback) => { events[key] = callback; },
    },
    window: {
      addEventListener: (key, callback) => { events[key] = callback; },
      matchMedia: () => motionPreference,
    },
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
    api: context.window.X1Scenery, root, storage, properties, timers,
    theme(value) { root.dataset.theme = value; observeTheme(); },
    motion(value) { motionPreference.matches = value; observeMotion?.(); },
    event(name, value = {}) { events[name]?.(value); },
    jump(ms) { clock += ms; },
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

test('fast PDF completion leaves the one-way timeline running, then holds night permanently', () => {
  const app = page();
  assert.equal(app.api.start(), undefined);
  app.advance(1000);
  assert.equal(app.api.complete(), undefined);
  app.advance(22999);
  assert.equal(app.root.dataset.scenery, 'running');
  app.advance(1);
  assert.equal(app.root.dataset.scenery, 'night');
  assert.equal(app.properties.get('--scenery-delay'), '-24s');
  app.advance(3600000);
  assert.equal(app.root.dataset.scenery, 'night');
  assert.equal(app.timers.size, 0);
  assert.deepEqual(JSON.parse(app.storage.get('x1-tekapo-cycle')), { version: 2, startedAt: 100000 });
});

test('result navigation resumes absolute elapsed time and repeated output starts never restart it', () => {
  const upload = page();
  upload.api.start();
  const result = page({ type: 'result', now: 106000, stored: upload.storage });
  assert.equal(result.properties.get('--scenery-delay'), '-6s');
  result.api.start();
  result.advance(18000);
  assert.equal(result.root.dataset.scenery, 'night');
  result.api.start();
  result.api.complete();
  assert.equal(result.root.dataset.scenery, 'night');
  assert.equal(result.properties.get('--scenery-delay'), '-24s');
});

test('night survives result reloads long after completion and bfcache resumption', () => {
  const upload = page();
  upload.api.start();
  const result = page({ type: 'result', now: 3700000, stored: upload.storage });
  assert.equal(result.root.dataset.scenery, 'night');
  result.event('pageshow', { persisted: true });
  assert.equal(result.root.dataset.scenery, 'night');
  const running = page({ type: 'result', now: 105000, stored: upload.storage });
  running.jump(50000);
  running.event('visibilitychange');
  assert.equal(running.root.dataset.scenery, 'night');
});

test('repeat renders preserve the original CSS offset while video time keeps advancing', () => {
  const upload = page();
  upload.api.start();
  const video = media();
  const result = page({ type: 'result', now: 106000, stored: upload.storage, video });
  assert.equal(result.properties.get('--scenery-delay'), '-6s');
  result.advance(2000);
  result.event('visibilitychange');
  assert.equal(result.properties.get('--scenery-delay'), '-6s');
  assert.equal(video.currentTime, 8);
  result.api.start();
  assert.equal(result.properties.get('--scenery-delay'), '-6s');
  result.advance(16000);
  assert.equal(result.root.dataset.scenery, 'night');
  assert.equal(result.properties.get('--scenery-delay'), '-24s');
  result.api.reset();
  result.api.start();
  assert.equal(result.properties.get('--scenery-delay'), '0s');
});

test('a completed result without storage opens at night', () => {
  const result = page({ type: 'result', blocked: true, ready: [true, true] });
  assert.equal(result.root.dataset.scenery, 'night');
});

test('explicit reset and a fresh upload clear night while other themes stay unchanged', () => {
  const standard = page({ theme: 'standard' });
  standard.api.start();
  assert.equal(standard.root.dataset.scenery, undefined);
  const app = page();
  app.api.start();
  app.advance(24000);
  app.api.reset();
  assert.equal(app.root.dataset.scenery, undefined);
  assert.equal(app.storage.size, 0);
  app.api.start();
  app.theme('sakura');
  assert.equal(app.root.dataset.scenery, undefined);
  assert.equal(app.storage.size, 0);
});

test('storage failures do not block animation, generation or explicit new-upload reset', () => {
  const app = page({ blocked: true });
  app.api.start();
  app.api.complete();
  app.advance(24000);
  assert.equal(app.root.dataset.scenery, 'night');
  app.event('pageshow', { persisted: true });
  assert.equal(app.root.dataset.scenery, undefined);
});

test('errors and new upload pages discard state; old version and future timestamps are rejected', () => {
  const upload = page();
  upload.api.start();
  assert.equal(page({ type: 'error', stored: upload.storage }).storage.size, 0);
  for (const value of [{ startedAt: 99900, stopAt: null }, { version: 2, startedAt: 100001 }]) {
    const stored = new Map([['x1-tekapo-cycle', JSON.stringify(value)]]);
    assert.equal(page({ type: 'result', stored }).root.dataset.scenery, undefined);
    assert.equal(stored.size, 0);
  }
});

test('Tekapo media is muted, preloaded, synchronized after navigation, never looped and held on its final frame', () => {
  const video = media();
  const upload = page({ video });
  assert.equal(video.loads, 1);
  assert.equal(video.muted, true);
  assert.equal(video.loop, false);
  upload.api.start();
  const resumedVideo = media();
  const result = page({ type: 'result', now: 109000, stored: upload.storage, video: resumedVideo });
  assert.equal(resumedVideo.currentTime, 9);
  assert.ok(resumedVideo.plays > 0);
  result.advance(15000);
  assert.equal(result.root.dataset.scenery, 'night');
  assert.ok(Math.abs(resumedVideo.currentTime - (24 - 1 / 30)) < 0.001);
  const plays = resumedVideo.plays;
  result.api.start();
  assert.equal(resumedVideo.plays, plays);
});

test('late decoding seeks the elapsed position; failed media uses fallback without affecting PDF hooks', async () => {
  const video = media({ readyState: 0, rejected: true });
  const app = page({ video });
  app.api.start();
  app.advance(5000);
  video.readyState = 4;
  video.emit('canplay');
  await Promise.resolve();
  assert.equal(video.currentTime, 5);
  assert.equal(app.root.dataset.sceneryVideo, 'fallback');
  assert.equal(app.api.complete(), undefined);
  app.advance(19000);
  assert.equal(app.root.dataset.scenery, 'night');
});

test('inactive video assets are not preloaded and theme changes remain isolated', () => {
  const video = media();
  const cityVideo = media();
  const app = page({ theme: 'standard', video, cityVideo });
  assert.equal(video.loads + cityVideo.loads, 0);
  app.theme('tekapo-minimal');
  assert.equal(video.loads, 1);
  assert.equal(cityVideo.loads, 0);
  app.api.start();
  app.theme('city-night');
  assert.equal(cityVideo.loads, 1);
  assert.equal(app.root.dataset.scenery, undefined);
  assert.equal(app.storage.has('x1-tekapo-cycle'), false);
});

test('City plays only while processing then pauses and preserves its exact current frame across reloads', () => {
  const video = media({ duration: 30 });
  const app = page({ theme: 'city-night', cityVideo: video });
  app.api.start();
  assert.equal(video.loop, true);
  assert.equal(app.root.dataset.scenery, 'running');
  video.currentTime = 8.75;
  app.api.complete();
  assert.equal(app.root.dataset.scenery, 'paused');
  assert.equal(JSON.parse(app.storage.get('x1-city-cycle')).mediaTime, 8.75);
  const restored = media({ duration: 30 });
  const result = page({ theme: 'city-night', type: 'result', cityVideo: restored,
                        now: 200000, stored: app.storage, ready: [true, true] });
  assert.equal(result.root.dataset.scenery, 'paused');
  assert.equal(restored.currentTime, 8.75);
  assert.equal(restored.plays, 0);
  result.advance(60000);
  assert.equal(restored.currentTime, 8.75);
});

test('City resumes in-flight elapsed time and errors pause without clearing the frame; retry resumes it', () => {
  const app = page({ theme: 'city-night', cityVideo: media({ duration: 30 }) });
  app.api.start();
  const video = media({ duration: 30 });
  const result = page({ theme: 'city-night', type: 'result', cityVideo: video, now: 135000, stored: app.storage });
  assert.equal(video.currentTime, 5);
  video.currentTime = 7.2;
  result.api.reset();
  assert.equal(result.root.dataset.scenery, 'paused');
  assert.equal(video.currentTime, 7.2);
  result.api.start();
  assert.equal(result.root.dataset.scenery, 'running');
  assert.equal(video.currentTime, 7.2);
  result.theme('standard');
  assert.equal(result.root.dataset.scenery, undefined);
  assert.equal(result.storage.size, 0);
});

test('reduced-motion uses static fallback without downloading or playing either video', () => {
  const video = media();
  const cityVideo = media();
  const app = page({ video, cityVideo, reducedMotion: true });
  app.api.start();
  assert.equal(app.root.dataset.sceneryVideo, 'fallback');
  app.advance(24000);
  assert.equal(app.root.dataset.scenery, 'night');
  app.theme('city-night');
  app.api.start();
  app.api.complete();
  assert.equal(app.root.dataset.scenery, 'paused');
  assert.equal(video.loads + cityVideo.loads + video.plays + cityVideo.plays, 0);
});

test('changing reduced-motion preference pauses media and can restore playback', () => {
  const video = media();
  const app = page({ video, reducedMotion: true });
  app.api.start();
  app.advance(5000);
  app.motion(false);
  assert.equal(video.loads, 1);
  assert.ok(video.plays > 0);
  assert.equal(app.properties.get('--scenery-delay'), '-5s');
  app.motion(true);
  assert.equal(app.root.dataset.sceneryVideo, 'fallback');
  assert.ok(video.pauses > 0);
});

test('City completion before metadata normalizes its saved frame to the real video duration', () => {
  const video = media({ readyState: 0, duration: NaN });
  const app = page({ theme: 'city-night', cityVideo: video });
  app.api.start();
  app.advance(18000);
  app.api.complete();
  assert.equal(JSON.parse(app.storage.get('x1-city-cycle')).mediaTime, 18);
  video.readyState = 4;
  video.duration = 12;
  video.emit('loadedmetadata');
  assert.equal(video.currentTime, 6);
  assert.equal(JSON.parse(app.storage.get('x1-city-cycle')).mediaTime, 6);
  assert.equal(app.root.dataset.scenery, 'paused');
  assert.equal(video.plays, 0);
});

function nativeForm(size) {
  let submit;
  let change;
  const input = { files: [{ name: 'schedule.pdf', size }], addEventListener(name, callback) { change = callback; } };
  return {
    dataset: { blobUploadEnabled: 'false', maxUploadBytes: '26214400' },
    querySelector: () => input,
    checkValidity: () => true,
    addEventListener(event, callback) { if (event === 'submit') submit = callback; },
    submit() { submit({ defaultPrevented: false }); },
    change() { change(); },
  };
}

test('valid native upload starts scenery; selecting a new input clears the old background', () => {
  const form = nativeForm(26214400);
  const app = page({ form });
  form.submit();
  assert.equal(app.root.dataset.scenery, 'running');
  form.change();
  assert.equal(app.root.dataset.scenery, undefined);
});

test('oversized native uploads do not start scenery before the server rejects them', () => {
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

test('PDF requests remain independent and downloads become usable before scenery completes', async () => {
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

test('a failed output invokes scenery reset without blocking the other PDF', async () => {
  const app = outputsPage();
  await app.settle(0, false);
  assert.equal(app.calls.reset, 1);
  await app.settle(1, true);
  assert.equal(app.cards[1].querySelector('[data-output-download]').hidden, false);
  assert.equal(app.calls.complete, 0);
});
