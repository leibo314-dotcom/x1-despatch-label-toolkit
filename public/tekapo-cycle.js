(() => {
  const root = document.documentElement;
  const page = document.body.dataset.page;
  const scenes = {
    'tekapo-minimal': { key: 'x1-tekapo-cycle', video: document.querySelector('.scenery-video'), duration: 24000 },
    'city-night': { key: 'x1-city-cycle', video: document.querySelector('.city-video'), duration: null },
  };
  let activeTheme = root.dataset.theme;
  let scene = scenes[activeTheme];
  let cycle = null;
  let finishTimer;
  let playAttempt = 0;
  const prepared = new Set();
  const motionPreference = window.matchMedia?.('(prefers-reduced-motion: reduce)');

  const save = () => {
    if (!scene) return;
    try {
      if (cycle) sessionStorage.setItem(scene.key, JSON.stringify(cycle));
      else sessionStorage.removeItem(scene.key);
    } catch {
      // Scenery never makes uploading or PDF generation depend on storage.
    }
  };

  const elapsed = () => cycle ? Math.max(0, Date.now() - cycle.startedAt) : 0;

  const pauseVideo = () => {
    playAttempt += 1;
    try { scene?.video?.pause(); } catch { /* Decorative media is optional. */ }
  };

  const syncVideo = () => {
    const video = scene?.video;
    if (!video || !cycle || root.dataset.theme !== activeTheme) return;
    if (motionPreference?.matches) {
      pauseVideo();
      root.dataset.sceneryVideo = 'fallback';
      return;
    }
    if (video.readyState < 1) return;
    const atNight = scene.duration && elapsed() >= scene.duration;
    const paused = atNight || cycle.paused;
    const mediaLength = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 24;
    let target;
    if (scene.duration) target = Math.min(elapsed() / 1000, Math.max(0, mediaLength - 1 / 30));
    else {
      target = cycle.paused ? cycle.mediaTime % mediaLength : (elapsed() / 1000) % mediaLength;
      if (cycle.paused && cycle.mediaTime !== target) {
        // Completion may precede metadata, when only a fallback duration was known.
        cycle.mediaTime = target;
        save();
      }
    }
    try {
      if (Math.abs(video.currentTime - target) > (paused ? 0.01 : 0.35)) video.currentTime = target;
      if (video.readyState >= 2) root.dataset.sceneryVideo = 'ready';
      if (paused) pauseVideo();
      else {
        const attempt = ++playAttempt;
        const playing = video.play();
        playing?.catch(() => {
          if (attempt === playAttempt && cycle && root.dataset.theme === activeTheme) {
            root.dataset.sceneryVideo = 'fallback';
          }
        });
      }
    } catch {
      root.dataset.sceneryVideo = 'fallback';
    }
  };

  const prepareVideo = () => {
    const video = scene?.video;
    if (motionPreference?.matches) {
      if (scene) root.dataset.sceneryVideo = 'fallback';
      return;
    }
    if (!video || prepared.has(video)) return;
    prepared.add(video);
    try {
      video.muted = true;
      video.defaultMuted = true;
      video.playsInline = true;
      video.loop = !scene.duration;
      video.preload = 'auto';
      if (video.dataset.src) video.src = video.dataset.src;
      video.load();
    } catch {
      root.dataset.sceneryVideo = 'fallback';
    }
  };

  const clear = () => {
    clearTimeout(finishTimer);
    cycle = null;
    pauseVideo();
    try { if (scene?.video?.readyState >= 1) scene.video.currentTime = 0; } catch { /* Ignore unavailable media. */ }
    delete root.dataset.scenery;
    delete root.dataset.sceneryVideo;
    root.style.removeProperty('--scenery-delay');
    save();
  };

  const render = (restartStyles = false) => {
    if (!cycle || !scene) return;
    clearTimeout(finishTimer);
    if (scene.duration) {
      const phase = Math.min(scene.duration, elapsed());
      // CSS keeps advancing after it starts. Reapplying the elapsed offset to
      // that running animation would count time twice after a tab restore.
      if (restartStyles || root.dataset.scenery !== 'running' || phase === scene.duration) {
        root.style.setProperty('--scenery-delay', `${-phase / 1000}s`);
      }
      root.dataset.scenery = phase < scene.duration ? 'running' : 'night';
      if (phase < scene.duration) finishTimer = setTimeout(render, scene.duration - phase);
    } else root.dataset.scenery = cycle.paused ? 'paused' : 'running';
    prepareVideo();
    syncVideo();
  };

  const selectScene = () => {
    if (activeTheme === root.dataset.theme) return;
    clear();
    activeTheme = root.dataset.theme;
    scene = scenes[activeTheme];
    cycle = null;
    prepareVideo();
  };

  const start = () => {
    selectScene();
    if (!scene) return;
    // Uploads start fresh. Result requests resume the same background timeline.
    if (!cycle || page === 'upload') cycle = { version: 2, startedAt: Date.now() };
    else if (cycle.paused) {
      cycle.startedAt = Date.now() - cycle.mediaTime * 1000;
      delete cycle.paused;
      delete cycle.mediaTime;
    }
    save();
    render();
  };

  const complete = () => {
    if (!cycle || !scene || root.dataset.theme !== activeTheme) return;
    if (!scene.duration && !cycle.paused) {
      const video = scene.video;
      const mediaLength = Number.isFinite(video?.duration) && video.duration > 0 ? video.duration : 24;
      cycle.mediaTime = video?.readyState >= 1 ? video.currentTime : (elapsed() / 1000) % mediaLength;
      cycle.paused = true;
      // Pause this exact frame before persisting, without waiting for media.
      pauseVideo();
      root.dataset.scenery = 'paused';
    }
    // Tekapo independently reaches night once; a ready PDF never waits for it.
    save();
  };

  const reset = () => {
    if (activeTheme === 'city-night' && cycle) complete();
    else clear();
  };

  window.X1Scenery = { start, complete, reset };

  for (const candidate of Object.values(scenes)) {
    const video = candidate.video;
    if (!video) continue;
    for (const name of ['loadedmetadata', 'loadeddata', 'canplay']) {
      video.addEventListener(name, () => { if (scene === candidate) syncVideo(); });
    }
    video.addEventListener('error', () => {
      if (scene === candidate) root.dataset.sceneryVideo = 'fallback';
    });
  }

  if (scene && page === 'result') {
    try {
      const saved = JSON.parse(sessionStorage.getItem(scene.key));
      if (saved?.version === 2 && Number.isFinite(saved.startedAt) && saved.startedAt <= Date.now() &&
          (!saved.paused || (Number.isFinite(saved.mediaTime) && saved.mediaTime >= 0))) {
        cycle = { version: 2, startedAt: saved.startedAt };
        if (!scene.duration && saved.paused) Object.assign(cycle, { paused: true, mediaTime: saved.mediaTime });
      }
    } catch { /* A blocked or damaged storage entry is harmless. */ }
    const cards = [...document.querySelectorAll('[data-output]')];
    const allReady = cards.length && cards.every((card) => card.dataset.ready === 'true');
    if (!cycle && scene.duration && allReady) {
      // An already-completed result stays at night even without session data.
      cycle = { version: 2, startedAt: Date.now() - scene.duration };
      save();
    }
    if (cycle) {
      render();
      if (allReady && !scene.duration) complete();
    } else clear();
  } else clear();
  prepareVideo();

  new MutationObserver(selectScene).observe(root, { attributes: true, attributeFilter: ['data-theme'] });

  const form = document.querySelector('.upload-form');
  if (form) {
    form.querySelector('input[type="file"]')?.addEventListener('change', clear);
    if (form.dataset.blobUploadEnabled !== 'true') {
      form.addEventListener('submit', (event) => {
        const file = form.querySelector('input[type="file"]')?.files?.[0];
        const configuredLimit = Number(form.dataset.maxUploadBytes);
        const maxBytes = Number.isFinite(configuredLimit) && configuredLimit > 0 ? configuredLimit : Infinity;
        if (!event.defaultPrevented && form.checkValidity() && file?.name.toLowerCase().endsWith('.pdf') &&
            file.size <= maxBytes) start();
      });
    }
  }

  // Clamp Tekapo at night after navigation or a backgrounded tab; never wrap.
  window.addEventListener('pageshow', (event) => {
    if (!event.persisted) return;
    selectScene();
    if (page !== 'result') clear();
    else render();
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) { selectScene(); render(); }
  });
  motionPreference?.addEventListener?.('change', () => {
    if (motionPreference.matches) {
      pauseVideo();
      if (scene) root.dataset.sceneryVideo = 'fallback';
    } else prepareVideo();
    render(true);
  });
})();
