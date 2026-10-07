const job = document.querySelector('[data-job]').dataset.job;
async function generate(card, retry = false) {
  if (card.dataset.ready === 'true') return;
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
  }
}
// Dispatch separately: either result stays usable if the other request fails.
for (const card of document.querySelectorAll('[data-output]')) {
  card.querySelector('[data-output-retry]').addEventListener('click', () => generate(card, true));
  generate(card);
}
