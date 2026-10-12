const job = document.querySelector('[data-job]').dataset.job;
const cards = [...document.querySelectorAll('[data-output]')];
let pending = 0;

function updateScenery() {
  if (cards.some((card) => card.dataset.state === 'error')) {
    window.X1Scenery?.reset();
  } else if (pending === 0) {
    window.X1Scenery?.complete();
  }
}

async function generate(card, retry = false) {
  if (card.dataset.ready === 'true' || card.dataset.state === 'pending') return;
  if (retry) window.X1Scenery?.start();
  pending += 1;
  const badge = card.querySelector('[data-output-status]');
  const message = card.querySelector('[data-output-message]');
  const retryButton = card.querySelector('[data-output-retry]');
  const download = card.querySelector('[data-output-download]');
  card.dataset.state = 'pending'; badge.textContent = 'Generating…';
  message.textContent = ''; retryButton.hidden = true;
  try {
    const response = await fetch(`/api/jobs/${job}/outputs/${card.dataset.output}`, {
      method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({retry}),
    });
    const result = await response.json();
    if (!response.ok || result.status !== 'ready') throw new Error(result.error || 'Generation failed. Please retry.');
    card.dataset.state = 'success'; card.dataset.ready = 'true'; badge.textContent = 'Ready';
    download.hidden = false;
    if (result.items) message.textContent = `${result.items} labels · ${result.pages} A4 ${result.pages === 1 ? 'sheet' : 'sheets'}`;
  } catch (error) {
    card.dataset.state = 'error'; badge.textContent = 'Could not generate';
    message.textContent = error.message || 'Generation failed. Please retry.';
    retryButton.hidden = false;
  } finally {
    pending -= 1;
    updateScenery();
  }
}
// Dispatch separately: either result stays usable if the other request fails.
window.X1Scenery?.resume();
for (const card of cards) {
  card.querySelector('[data-output-retry]').addEventListener('click', () => {
    generate(card, true);
  });
  generate(card);
}
updateScenery();
