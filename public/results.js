const job = document.querySelector('[data-job]').dataset.job;
const retry = document.querySelector('[data-retry]');
function line(parent,text,tag='p') { const node=document.createElement(tag);node.textContent=text;parent.append(node); }
function render(card,result) {
  const pass=result.status==='success';
  card.dataset.state=result.status;
  card.querySelector('[data-status]').textContent=pass?'Pass':result.status==='warning'?'Fail':'Needs review';
  card.querySelector('[data-colour]').textContent=card.dataset.feature==='colour'?(result.colour || ''):'';
  const evidence=card.querySelector('[data-evidence]');evidence.hidden=pass;evidence.open=false;
  const details=card.querySelector('[data-details]');details.replaceChildren();
  if(pass)return;
  if(result.summary)line(details,result.summary);
  for(const group of result.groups || [])line(details,`${group.colour} — Items ${group.items.join(', ')}`);
  for(const item of result.details || []) {
    const row=document.createElement('div');row.className='tool-detail';details.append(row);
    const title=[item.item!=null?`Item ${item.item}`:'',item.pages?`Page ${item.pages.join(', ')}`:''].filter(Boolean).join(' · ');
    if(title)line(row,title,'strong');
    if(item.reason)line(row,item.reason);
    if(item.expected_v661!=null)line(row,`Expected ${item.expected_v661} mm · Actual ${item.actual_v661.join(', ')} mm`);
  }
}
async function run(force=false) {
  retry.disabled=true;retry.hidden=true;
  for(const card of document.querySelectorAll('[data-feature]')) {card.dataset.state='pending';card.querySelector('[data-status]').textContent='Checking…';card.querySelector('[data-evidence]').hidden=true;}
  try {
    const response=await fetch(`/api/jobs/${job}/checks`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({retry:force})});
    const data=await response.json();if(!response.ok)throw new Error(data.error || 'Checks could not complete.');
    for(const card of document.querySelectorAll('[data-feature]'))render(card,data[card.dataset.feature]);
    retry.hidden=Object.values(data).every(result=>result.status==='success');
  } catch(error) {
    for(const card of document.querySelectorAll('[data-feature]'))render(card,{status:'manual',details:[{reason:error.message || 'Checks could not complete.'}]});
    retry.hidden=false;
  } finally {retry.disabled=false;}
}
retry.addEventListener('click',()=>run(true));
await run();
