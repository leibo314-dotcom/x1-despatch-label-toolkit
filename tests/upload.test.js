import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function uploadPage({ blob = true, file = { name: 'sample.pdf', size: 1000 }, limit = 100, failUpload = false, failGenerate = false } = {}) {
  const calls = { start: 0, reset: 0, navigate: [] };
  const requests = [];
  const elements = new Map();
  const fileInput = { files: file ? [file] : [] };
  const form = {
    dataset: { blobUploadEnabled: String(blob), maxUploadBytes: String(limit * 1024 * 1024) },
    querySelector(selector) {
      if (!elements.has(selector)) elements.set(selector, { textContent: '', hidden: true, disabled: false, removeAttribute() {} });
      return elements.get(selector);
    },
    addEventListener(type, fn) { this[type] = fn; },
  };
  let finishUpload;
  const uploadResult = new Promise((resolve) => { finishUpload = resolve; });
  const locations = [];
  const windowEvents = {};
  const code = readFileSync(new URL('../src/upload.js', import.meta.url), 'utf8').replace(/^import[^\n]*\n/, '');
  vm.runInNewContext(code, {
    document: { querySelector: (selector) => selector === '.upload-form' ? form : fileInput },
    window: {
      X1Scenery: { start() { calls.start++; }, reset() { calls.reset++; }, navigate(path) { calls.navigate.push(path); } },
      location: { assign: (url) => locations.push(url) }, addEventListener: (type, fn) => { windowEvents[type] = fn; },
    },
    crypto: { randomUUID: () => 'a'.repeat(32) },
    upload: async (...args) => { requests.push(args); if (failUpload) throw Error('Upload failed'); return uploadResult; },
    fetch: async () => ({ ok: !failGenerate, json: async () => failGenerate ? { error: 'Bad PDF' } : { result_url: '/result/' + 'b'.repeat(32) } }),
  });
  return {
    calls, requests, locations, elements, windowEvents,
    submit() {
      const event = { prevented: false, preventDefault() { this.prevented = true; } };
      const done = form.submit(event);
      return { event, done };
    },
    finish: () => finishUpload({ pathname: 'x1-inputs/test.pdf' }),
  };
}

test('invalid selections never trigger an animation or an upload', async () => {
  for (const file of [null, { name: 'text.txt', size: 1 }, { name: 'big.pdf', size: 101 * 1024 * 1024 }]) {
    const app = uploadPage({ file });
    const action = app.submit();
    await action.done;
    assert.equal(action.event.prevented, true);
    assert.equal(app.calls.start, 0);
    assert.equal(app.requests.length, 0);
  }
});

test('one valid submit starts immediately, blocks re-entry, and hands off without awaiting animation', async () => {
  const app = uploadPage();
  const first = app.submit();
  const second = app.submit();
  assert.equal(app.calls.start, 1);
  assert.equal(app.requests.length, 1);
  assert.equal(second.event.prevented, true);
  app.finish();
  await first.done;
  assert.equal(app.locations.length, 1);
  assert.equal(app.calls.navigate[0], app.locations[0]);
});

test('both upload and generation errors clear animation and allow another attempt', async () => {
  for (const options of [{ failUpload: true }, { failGenerate: true }]) {
    const app = uploadPage(options);
    const action = app.submit();
    app.finish();
    await action.done;
    assert.equal(app.calls.reset, 1);
    assert.equal(app.elements.get('button[type="submit"]').disabled, false);
    assert.equal(app.locations.length, 0);
    await app.submit().done;
    assert.equal(app.calls.start, 2);
  }
});

test('multipart fallback preserves native form submission and its own size limit', async () => {
  const app = uploadPage({ blob: false, limit: 25 });
  const action = app.submit();
  await action.done;
  assert.equal(action.event.prevented, false);
  assert.equal(app.requests.length, 0);
  assert.equal(app.calls.start, 1);
  assert.equal(app.calls.navigate.length, 1);
  assert.equal(app.submit().event.prevented, true);
  app.windowEvents.pageshow({ persisted: true });
  assert.equal(app.elements.get('button[type="submit"]').disabled, false);
  const large = uploadPage({ blob: false, limit: 25, file: { name: 'large.pdf', size: 26 * 1024 * 1024 } });
  const rejected = large.submit();
  await rejected.done;
  assert.equal(rejected.event.prevented, true);
  assert.equal(large.calls.start, 0);
});
