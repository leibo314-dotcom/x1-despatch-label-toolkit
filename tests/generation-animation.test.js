import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const code = readFileSync(new URL('../public/generation-animation.js', import.meta.url), 'utf8');
const path = '/result/' + 'a'.repeat(32);
function page({ theme = 'standard', job = false, storage = new Map(), now = 100000, reduced = false, brokenStorage = false, brokenCanvas = false } = {}) {
  let clock = now;
  const root = { dataset: { theme } };
  const canvas = { hidden: true };
  const frames = new Map();
  let nextId = 0;
  const drawn = [];
  const events = {};
  let themeChanged;
  const motion = { matches: reduced, addEventListener(type, fn) { this.changed = fn; } };
  const context = {
    document: { documentElement: root, querySelector: (selector) => selector === '[data-generation-canvas]' ? canvas : job ? { dataset: { job: 'a'.repeat(32) } } : null },
    location: { href: 'https://example.test' + (job ? path : '/'), origin: 'https://example.test', pathname: job ? path : '/' },
    window: { matchMedia: () => motion, addEventListener: (type, fn) => { events[type] = fn; },
      X1TimeRing: () => {
        if (brokenCanvas) throw new Error('No canvas');
        return { duration: 15000, resize() {}, draw(t) { drawn.push(t); } };
      } },
    MutationObserver: class { constructor(fn) { themeChanged = fn; } observe() {} },
    sessionStorage: {
      getItem(key) { if (brokenStorage) throw Error('Storage blocked'); return storage.get(key) || null; },
      setItem(key, value) { if (brokenStorage) throw Error('Storage blocked'); storage.set(key, value); },
      removeItem(key) { if (brokenStorage) throw Error('Storage blocked'); storage.delete(key); },
    },
    Date: { now: () => clock }, URL,
    requestAnimationFrame: (fn) => { const id = ++nextId; frames.set(id, fn); return id; },
    cancelAnimationFrame: (id) => { frames.delete(id); },
  };
  vm.runInNewContext(code, context);
  return {
    api: context.window.X1Scenery, storage, canvas, frames, drawn, root, events, motion,
    tick(ms) { clock += ms; const queued = [...frames.values()]; frames.clear(); queued.forEach((fn) => fn()); },
    theme(value) { root.dataset.theme = value; themeChanged(); },
  };
}

test('a valid generation runs the original 15 second score once, even when started again', () => {
  const app = page();
  app.api.start();
  app.tick(4000);
  app.api.start();
  assert.equal(app.frames.size, 1);
  assert.equal(app.drawn.at(-1), 4);
  app.api.complete();
  assert.equal(app.canvas.hidden, false); // completion is independent of decoration
  app.tick(11000);
  assert.equal(app.canvas.hidden, true);
  assert.equal(app.frames.size, 0);
  assert.equal(app.storage.size, 0);
  app.tick(30000);
  assert.equal(app.drawn.at(-1), 4); // no repeated loop
});

test('upload and result share one clock, and a result reload never starts a second score', () => {
  const upload = page();
  upload.api.start();
  upload.api.navigate(path + '?source_name=test.pdf');
  upload.events.pagehide();
  assert.equal(upload.frames.size, 0);
  const result = page({ job: true, storage: upload.storage, now: 104000 });
  result.api.resume();
  assert.equal(result.drawn[0], 4);
  result.api.resume();
  assert.equal(result.frames.size, 1);
  result.events.pagehide();
  const reload = page({ job: true, storage: upload.storage, now: 108000 });
  reload.api.resume();
  assert.equal(reload.drawn[0], 8);
  reload.tick(7000);
  assert.equal(reload.canvas.hidden, true);
  const later = page({ job: true, storage: upload.storage, now: 116000 });
  later.api.resume();
  assert.equal(later.drawn.length, 0);
});

test('ordinary multipart upload continues the score after the server redirect', () => {
  const upload = page();
  upload.api.start();
  upload.api.navigate();
  upload.events.pagehide();
  const result = page({ job: true, storage: upload.storage, now: 102000 });
  result.api.resume();
  assert.equal(result.drawn[0], 2);
});

test('failure cancels playback and storage; retry is a new single valid operation', () => {
  const app = page();
  app.api.start();
  app.tick(3000);
  app.api.reset();
  assert.equal(app.frames.size, 0);
  assert.equal(app.canvas.hidden, true);
  assert.equal(app.storage.size, 0);
  app.api.start();
  assert.equal(app.drawn.at(-1), 0);
});

test('other themes, reduced motion, theme changes and back navigation stay clean', () => {
  for (const theme of ['original', 'tekapo', 'sakura']) {
    const app = page({ theme });
    app.api.start();
    assert.equal(app.drawn.length, 0);
    assert.equal(app.storage.size, 0);
  }
  const reduced = page({ reduced: true });
  reduced.api.start();
  assert.equal(reduced.drawn.length, 0);
  const app = page();
  app.api.start();
  app.theme('sakura');
  app.theme('standard');
  assert.equal(app.canvas.hidden, true);
  assert.equal(app.frames.size, 0);
  assert.equal(app.storage.size, 0);
  app.api.start();
  app.events.pageshow({ persisted: true });
  assert.equal(app.frames.size, 0);
  app.api.start();
  app.motion.matches = true;
  app.motion.changed();
  assert.equal(app.canvas.hidden, true);
});

test('storage and canvas failures cannot throw into PDF submission', () => {
  const blocked = page({ brokenStorage: true });
  assert.doesNotThrow(() => blocked.api.start());
  assert.equal(blocked.canvas.hidden, false);
  const noCanvas = page({ brokenCanvas: true });
  assert.doesNotThrow(() => noCanvas.api.start());
  assert.equal(noCanvas.canvas.hidden, true);
  assert.equal(noCanvas.frames.size, 0);
});

test('unrelated result pages and switched themes never consume a score incorrectly', () => {
  const upload = page();
  upload.api.start();
  upload.api.navigate('/result/' + 'b'.repeat(32));
  const different = page({ job: true, storage: upload.storage });
  different.api.resume();
  assert.equal(different.drawn.length, 0);
  upload.api.reset();
  upload.api.start();
  upload.api.navigate(path);
  const otherTheme = page({ job: true, theme: 'tekapo', storage: upload.storage });
  otherTheme.api.resume();
  assert.equal(otherTheme.storage.size, 0);
});

test('the original draw/easing/particle score is preserved verbatim', () => {
  const original = readFileSync(new URL('../docs/time-ring-original.html', import.meta.url), 'utf8');
  const score = original.slice(original.indexOf('  // ---------- easing ----------'), original.indexOf('  // ---------- playback:'));
  const renderer = readFileSync(new URL('../public/time-ring.js', import.meta.url), 'utf8');
  assert.ok(score.length > 5000);
  assert.ok(renderer.includes(score));
  assert.ok(renderer.includes('const DUR = 15;'));
});
