import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const code = readFileSync(new URL('../public/theme.js', import.meta.url), 'utf8');
function page(saved, blocked = false) {
  const root = { dataset: {} };
  const picker = { value: '', addEventListener(type, fn) { this[type] = fn; } };
  const storage = { value: saved };
  vm.runInNewContext(code, {
    document: { documentElement: root, readyState: 'complete', querySelectorAll: () => [picker] },
    localStorage: {
      getItem() { if (blocked) throw Error('blocked'); return storage.value; },
      setItem(key, value) { if (blocked) throw Error('blocked'); storage.value = value; },
    },
  });
  return { root, picker, storage, select(value) { picker.value = value; picker.change(); } };
}

test('renaming Standard to Simple retains existing saved theme choices', () => {
  for (const theme of ['standard', 'tekapo', 'sakura']) {
    const app = page(theme);
    assert.equal(app.root.dataset.theme, theme);
    assert.equal(app.picker.value, theme);
  }
});

test('Original selection survives navigation without overwriting other theme keys', () => {
  const app = page('standard');
  app.select('original');
  assert.equal(page(app.storage.value).root.dataset.theme, 'original');
  app.select('standard');
  assert.equal(app.storage.value, 'standard');
  app.select('unknown');
  assert.equal(app.root.dataset.theme, 'standard');
});

test('the default and blocked-storage theme picker remain usable', () => {
  assert.equal(page(null).root.dataset.theme, 'tekapo');
  const app = page(null, true);
  app.select('original');
  assert.equal(app.root.dataset.theme, 'original');
});
