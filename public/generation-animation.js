(() => {
  const root = document.documentElement;
  const canvas = document.querySelector('[data-generation-canvas]');
  if (!canvas) return;
  // The user requested Standard only; never change the initial or saved theme.
  const animationTheme = 'standard';
  const storageKey = 'x1-generation-time-ring-v1';
  const motion = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  const job = document.querySelector('[data-job]')?.dataset.job;
  let scene;
  let cycle = null;
  let frameId = null;
  let completed = false;

  function save() {
    try {
      if (cycle) sessionStorage.setItem(storageKey, JSON.stringify(cycle));
      else sessionStorage.removeItem(storageKey);
    } catch { /* Decorative playback never requires browser storage. */ }
  }

  function cancelFrame() {
    if (frameId !== null) cancelAnimationFrame(frameId);
    frameId = null;
  }

  function reset() {
    cancelFrame();
    canvas.hidden = true;
    delete root.dataset.generationAnimation;
    cycle = null;
    completed = false;
    save();
  }

  function allowed() {
    return root.dataset.theme === animationTheme && !motion?.matches;
  }

  function render() {
    frameId = null;
    if (!cycle || !allowed()) { reset(); return; }
    try {
      const elapsed = Math.max(0, Date.now() - cycle.startedAt);
      if (elapsed >= scene.duration) {
        canvas.hidden = true;
        root.dataset.generationAnimation = 'finished';
        if (completed) reset();
        return;
      }
      scene.draw(elapsed / 1000);
      frameId = requestAnimationFrame(render);
    } catch { reset(); }
  }

  function show() {
    try {
      scene ||= window.X1TimeRing(canvas);
      canvas.hidden = false;
      scene.resize();
      root.dataset.generationAnimation = 'playing';
      cancelFrame();
      render();
    } catch { reset(); }
  }

  function start() {
    if (!allowed()) { reset(); return; }
    // Re-entrant starts belong to the same generation, never a second loop.
    if (cycle) return;
    cycle = { startedAt: Date.now(), resultPath: job ? location.pathname : null };
    completed = false;
    save();
    show();
  }

  function navigate(resultUrl = null) {
    if (!cycle) return;
    try {
      if (resultUrl) {
        const target = new URL(resultUrl, location.href);
        if (target.origin !== location.origin || !/^\/result\/[a-f0-9]{32}$/.test(target.pathname)) {
          reset(); return;
        }
        cycle.resultPath = target.pathname;
      } else {
        // The ordinary multipart form receives its result URL from Flask's redirect.
        cycle.nativeSubmit = true;
      }
      save();
    } catch { reset(); }
  }

  function resume() {
    if (!job || cycle) return;
    if (!allowed()) { reset(); return; }
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey));
      const age = Date.now() - saved?.startedAt;
      if (!saved || !Number.isFinite(saved.startedAt) || age < 0 || age >= 15000 ||
          (saved.resultPath !== location.pathname && !saved.nativeSubmit)) {
        reset(); return;
      }
      cycle = { startedAt: saved.startedAt, resultPath: location.pathname };
      save();
      show();
    } catch { reset(); }
  }

  function complete() {
    completed = true;
    // PDFs become available immediately; their completion never waits for the score.
    if (!cycle || Date.now() - cycle.startedAt >= 15000) reset();
  }

  new MutationObserver(() => {
    if (!allowed()) reset();
  }).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
  motion?.addEventListener?.('change', () => { if (motion.matches) reset(); });
  window.addEventListener('resize', () => {
    if (!cycle || canvas.hidden) return;
    try { scene.resize(); scene.draw(Math.min(15, Math.max(0, Date.now() - cycle.startedAt) / 1000)); }
    catch { reset(); }
  });
  window.addEventListener('pagehide', () => {
    cancelFrame();
    if (!cycle?.resultPath && !cycle?.nativeSubmit) reset();
  });
  window.addEventListener('pageshow', (event) => { if (event.persisted) reset(); });

  if (!job) reset();
  window.X1Scenery = Object.freeze({ start, navigate, resume, complete, reset });
})();
