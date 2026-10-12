(() => {
  const root = document.documentElement;
  const theme = 'tekapo-minimal';
  const storageKey = 'x1-tekapo-cycle';
  const duration = 16000;
  const maxAge = 15 * 60 * 1000;
  let cycle = null;
  let finishTimer;

  const save = () => {
    try {
      if (cycle) sessionStorage.setItem(storageKey, JSON.stringify(cycle));
      else sessionStorage.removeItem(storageKey);
    } catch {
      // Storage is optional; generation and this page's animation still work.
    }
  };

  const reset = () => {
    clearTimeout(finishTimer);
    cycle = null;
    delete root.dataset.scenery;
    root.style.removeProperty('--scenery-delay');
    save();
  };

  const render = () => {
    const phase = (Date.now() - cycle.startedAt) % duration;
    root.style.setProperty('--scenery-delay', `${-phase / 1000}s`);
    root.dataset.scenery = 'running';
  };

  const scheduleFinish = () => {
    clearTimeout(finishTimer);
    if (cycle?.stopAt) {
      finishTimer = setTimeout(reset, Math.max(0, cycle.stopAt - Date.now()));
    }
  };

  const start = () => {
    if (root.dataset.theme !== theme) return;
    clearTimeout(finishTimer);
    if (!cycle) {
      cycle = { startedAt: Date.now(), stopAt: null };
      render();
    } else {
      cycle.stopAt = null;
    }
    save();
  };

  const complete = () => {
    if (!cycle || root.dataset.theme !== theme) return;
    const elapsed = Math.max(0, Date.now() - cycle.startedAt);
    const cycles = Math.max(1, Math.ceil(elapsed / duration));
    cycle.stopAt = cycle.startedAt + cycles * duration;
    save();
    scheduleFinish();
  };

  window.X1Scenery = { start, complete, reset };

  // A result page carries on at the same time of day after the upload navigates.
  // Revisiting the upload page or reaching an error discards the previous run.
  if (root.dataset.theme === theme && document.body.dataset.page === 'result') {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey));
      const age = Date.now() - saved?.startedAt;
      if (Number.isFinite(saved?.startedAt) && age >= 0 && age < maxAge &&
          (saved.stopAt === null || (Number.isFinite(saved.stopAt) && saved.stopAt > Date.now()))) {
        cycle = saved;
      }
    } catch {
      // A blocked or damaged storage entry is harmless.
    }
    if (cycle) {
      render();
      scheduleFinish();
    } else {
      reset();
    }
  } else {
    reset();
  }

  new MutationObserver(() => {
    if (root.dataset.theme !== theme) reset();
  }).observe(root, { attributes: true, attributeFilter: ['data-theme'] });

  const form = document.querySelector('.upload-form');
  if (form && form.dataset.blobUploadEnabled !== 'true') {
    form.addEventListener('submit', (event) => {
      const file = form.querySelector('input[type="file"]')?.files?.[0];
      const configuredLimit = Number(form.dataset.maxUploadBytes);
      const maxBytes = Number.isFinite(configuredLimit) && configuredLimit > 0 ? configuredLimit : Infinity;
      if (!event.defaultPrevented && form.checkValidity() && file?.name.toLowerCase().endsWith('.pdf') &&
          file.size <= maxBytes) {
        start();
      }
    });
  }

  // Back/forward cache restores the old document without executing this script.
  window.addEventListener('pageshow', (event) => {
    if (!event.persisted) return;
    if (document.body.dataset.page !== 'result' || root.dataset.theme !== theme) reset();
    else if (cycle?.stopAt && cycle.stopAt <= Date.now()) reset();
    else if (cycle) {
      render();
      scheduleFinish();
    }
  });
})();
