import { upload } from '@vercel/blob/client';
const form = document.querySelector('.upload-form');
const input = document.querySelector('#pdf_file');
const button = form.querySelector('button[type="submit"]');
const picker = document.querySelector('.file-picker');
const name = document.querySelector('[data-file-name]');
function status(message,percent = null) {
  form.querySelector('.upload-status').hidden = false;
  form.querySelector('[data-upload-status]').textContent = message;
  form.querySelector('[data-upload-percent]').textContent = percent === null ? '' : `${Math.round(percent)}%`;
  const progress = form.querySelector('[data-upload-progress]');
  if (percent === null) progress.removeAttribute('value'); else progress.value = percent;
}
input.addEventListener('change',() => {name.textContent = Array.from(input.files).map(f => f.name).join(' · ') || 'Choose PDFs or drop them here';});
for (const event of ['dragenter','dragover']) picker.addEventListener(event,e => {e.preventDefault(); picker.classList.add('is-dragging');});
picker.addEventListener('dragleave',() => picker.classList.remove('is-dragging'));
picker.addEventListener('drop',e => {e.preventDefault(); picker.classList.remove('is-dragging'); input.files = e.dataTransfer.files; input.dispatchEvent(new Event('change'));});
function safeFilename(value) {
  const stem = value.replace(/\.pdf$/i,'').normalize('NFKD').replace(/[^A-Za-z0-9._-]+/g,'-').replace(/^[._-]+|[._-]+$/g,'').slice(0,80);
  return `${stem || 'upload'}.pdf`;
}
form.addEventListener('submit',async event => {
  const files = Array.from(input.files || []); const max = Number(form.dataset.maxMb);
  if (!files.length || files.length > 3 || files.some(f => !f.name.toLowerCase().endsWith('.pdf')) || files.reduce((sum,f) => sum+f.size,0) > max*1024*1024) {
    event.preventDefault(); status(`Choose 1–3 PDFs, up to ${max} MB combined.`,0); return;
  }
  button.disabled = true; button.textContent = 'Uploading…';
  if (form.dataset.blobUploadEnabled !== 'true') return;
  event.preventDefault();
  try {
    const uploaded = [];
    for (const [index,file] of files.entries()) {
      const path = `x1-inputs/${crypto.randomUUID().replaceAll('-','')}-${safeFilename(file.name)}`;
      const blob = await upload(path,file,{access:'private',handleUploadUrl:'/api/blob-upload',contentType:'application/pdf',
        onUploadProgress:({percentage}) => status(`Uploading ${index+1} of ${files.length}…`,percentage)});
      uploaded.push({blob_pathname:blob.pathname,source_name:file.name});
    }
    status('Preparing the three document tools…');
    const response = await fetch('/generate-from-blob',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({files:uploaded})});
    const result = await response.json();
    if (!response.ok || !result.result_url) throw new Error(result.error || 'Upload preparation failed.');
    window.location.assign(result.result_url);
  } catch (error) {
    button.disabled = false; button.textContent = 'Upload & run tools';
    status(error.message || 'Upload failed. Please try again.',0);
  }
});
