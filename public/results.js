const job = document.querySelector('[data-job]').dataset.job;
const initial = JSON.parse(document.querySelector('#initial-results').textContent);
const labels = {pending:'Pending',running:'Running',success:'Complete',warning:'Review needed',manual:'Manual review',unsupported:'Outside verified scope',error:'Could not complete'};
let active = 0;
function line(parent, text, tag = 'p') {
  const node = document.createElement(tag); node.textContent = text; parent.append(node);
}
function render(card, result) {
  card.dataset.state = result.status;
  card.querySelector('[data-status]').textContent = labels[result.status] || result.status;
  card.querySelector('[data-summary]').textContent = result.summary;
  card.querySelector('[data-note]').textContent = result.note || '';
  card.querySelector('[data-download]').hidden = !(card.dataset.feature === 'delivery' && result.status === 'success' && result.artifact);
  card.querySelector('[data-report]').hidden = ['pending','running'].includes(result.status);
  const detail = card.querySelector('[data-details]'); detail.replaceChildren();
  card.querySelector('[data-evidence]').hidden = !(result.groups?.length || result.details?.length);
  card.querySelector('[data-evidence]').open = result.status === 'warning';
  for (const group of result.groups || []) line(detail, `${group.colour} — Items ${group.items.join(', ')}`);
  for (const item of result.details || []) {
    const row = document.createElement('div'); row.className = 'tool-detail'; detail.append(row);
    line(row, [item.item != null ? `Item ${item.item}` : '',item.source || '',item.pages ? `Page ${item.pages.join(', ')}` : ''].filter(Boolean).join(' · '),'strong');
    if (item.reason) line(row,item.reason);
    if (item.expected_v661 != null) line(row,`Expected V661: ${item.expected_v661} mm · Actual: ${item.actual_v661.join(', ')} mm · Difference: ${item.differences.map(v => v > 0 ? `+${v}` : v).join(', ')} mm`);
    if (item.formula) line(row,`Calculation: ${item.formula}`);
  }
  card.querySelector('[data-run]').textContent = result.status === 'pending' ? 'Run tool' : 'Retry this tool';
}
async function run(card) {
  const button = card.querySelector('[data-run]'); button.disabled = true; active += 1;
  document.querySelector('[data-delete]').disabled = true;
  render(card,{status:'running',summary:'Processing the uploaded PDFs…'});
  try {
    const response = await fetch(`/api/jobs/${job}/${card.dataset.feature}/run`,{method:'POST'});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'This request did not complete. Retry this tool.');
    render(card,value);
  } catch (error) {
    render(card,{status:'error',summary:error.message || 'Connection lost. Retry this tool.'});
    card.querySelector('[data-report]').hidden = true;
  } finally {
    button.disabled = false; active -= 1; document.querySelector('[data-delete]').disabled = active > 0;
  }
}
const pending = [];
for (const card of document.querySelectorAll('[data-feature]')) {
  const result = initial[card.dataset.feature]; render(card,result);
  card.querySelector('[data-run]').addEventListener('click',() => run(card));
  if (result.status === 'pending') pending.push(card);
}
await Promise.allSettled(pending.map(run));
