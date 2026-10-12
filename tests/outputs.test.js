import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

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
