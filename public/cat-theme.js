/* Decorative cat theme. Independent of uploads, PDF generation, and results. */
(() => {
  'use strict';

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const sleepRange = ([a, b]) => a + Math.random() * (b - a);
  const defaults = {
    width: 250, minWidth: 110, clearance: 16, aspect: 1280 / 704,
    restMs: [2200, 5500], meowGapMs: [70000, 140000], loadTimeoutMs: 18000,
    obstacles: '.test-banner, .card, .flash-list, .back-link, button, input, select, a[href]',
    actions: {}, poster: '', meow: '', onState: () => {},
  };

  // Curves describe root displacement in source-facing direction. Runtime
  // validates structure; visual calibration and quality live in the QA record.
  function displacement(clip, t) {
    const points = clip.motion?.samples || [[0, 0]];
    if (t <= points[0][0]) return points[0][1];
    for (let i = 1; i < points.length; i++) {
      const [tb, xb] = points[i];
      const [ta, xa] = points[i - 1];
      if (t <= tb) return xa + (xb - xa) * (t - ta) / (tb - ta);
    }
    return points[points.length - 1][1];
  }

  function validClip(clip, kind) {
    if (typeof clip?.src !== 'string' || !clip.src.trim()) return false;
    if (kind === 'walk' && !clip.loop) return false;
    if (kind !== 'idle') {
      const m = clip.motion;
      if (!m || !(m.referenceWidth > 0) || !Array.isArray(m.samples) || m.samples.length < 2) return false;
      if (!m.samples.every((point) => Array.isArray(point) && point.length === 2 && point.every(Number.isFinite))) return false;
      if (m.samples[0][0] !== 0 || m.samples[0][1] !== 0) return false;
      for (let i = 1; i < m.samples.length; i++) {
        if (!(m.samples[i][0] > m.samples[i - 1][0]) || m.samples[i][1] < m.samples[i - 1][1]) return false;
      }
      if (kind === 'walk' && m.samples[m.samples.length - 1][1] <= 0) return false;
    }
    return true;
  }

  function create(options = {}) {
    const cfg = { ...defaults, ...options };
    const layer = document.createElement('div');
    layer.className = 'x1-cat-layer';
    layer.setAttribute('aria-hidden', 'true');
    layer.hidden = true;
    const actor = document.createElement('div');
    actor.className = 'x1-cat-actor';
    layer.append(actor);
    document.body.append(layer);

    let poster;
    if (cfg.poster) {
      poster = document.createElement('img');
      poster.src = cfg.poster;
      poster.alt = '';
      poster.className = 'x1-cat-poster';
      poster.hidden = true;
      actor.append(poster);
    }
    const audio = cfg.meow ? new Audio(cfg.meow) : null;
    if (audio) { audio.preload = 'none'; audio.volume = 0.22; audio.muted = true; }
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const clips = new Map();
    const buttons = new Set();
    const mediaCancels = new Set();
    const selectionCancels = new Set();
    let selectionSerial = 0;
    let active = false, destroyed = false, audioEnabled = false, epoch = 0;
    let state = 'inactive', direction = 'right', geometry = null;
    let x = 0, y = 0, lastTime = 0, raf = 0, waitUntil = 0, current = null;
    let nextMeow = performance.now() + sleepRange(cfg.meowGapMs);
    let nextGreeting = 0, passWalkLoops = 0, passGreeted = false;
    let restAt = Infinity, rested = false, meowed = false, layoutQueued = false;
    const telemetry = { loopCount: 0, greetingCount: 0, greetingEdgeViolations: 0, stallCount: 0, activeStallMs: 0, longestStallMs: 0 };
    let lastProgressAt = 0, currentlyStalled = false;

    function report(next, reason = '') {
      state = next;
      cfg.onState({ state, reason, direction, active, audioEnabled });
    }
    function visible(on) {
      actor.style.visibility = on ? 'visible' : 'hidden';
      // Child video visibility may override inherited visibility. Composite
      // opacity ensures no old frame survives a no-space/relayout hide.
      actor.style.opacity = on ? '1' : '0';
    }
    function position() { actor.style.transform = `translate3d(${x}px, ${y}px, 0)`; }
    function syncButtons() {
      for (const button of buttons) {
        button.hidden = !active;
        button.disabled = !audio;
        button.title = audioEnabled ? 'Mute cat sounds' : 'Enable cat sounds';
        button.setAttribute('aria-pressed', String(audioEnabled));
        button.setAttribute('aria-label', button.title);
        button.querySelector('[data-sound-on]')?.toggleAttribute('hidden', !audioEnabled);
        button.querySelector('[data-sound-off]')?.toggleAttribute('hidden', audioEnabled);
      }
    }
    function pauseAll() {
      for (const cancel of [...selectionCancels]) cancel();
      cancelAnimationFrame(raf);
      raf = 0;
      for (const entry of clips.values()) { entry.video.pause(); entry.video.classList.remove('is-preparing'); }
      audio?.pause();
    }

    // A full-width empty horizontal corridor ensures the alpha actor never
    // covers controls, the avatar, or text, even while crossing the viewport.
    function measure() {
      const width = document.documentElement.clientWidth;
      const height = document.documentElement.clientHeight;
      const blocked = [];
      document.querySelectorAll(cfg.obstacles).forEach((node) => {
        if (layer.contains(node)) return;
        const r = node.getBoundingClientRect();
        if (r.width && r.height && r.bottom > 0 && r.top < height) {
          blocked.push([Math.max(0, r.top - cfg.clearance), Math.min(height, r.bottom + cfg.clearance)]);
        }
      });
      blocked.sort((a, b) => a[0] - b[0]);
      const spaces = [];
      let edge = cfg.clearance;
      for (const [a, b] of blocked) { if (a > edge) spaces.push([edge, a]); edge = Math.max(edge, b); }
      if (edge < height - cfg.clearance) spaces.push([edge, height - cfg.clearance]);
      const desired = Math.min(cfg.width, width * 0.6);
      // Prefer lower free space, but do not move the page/card to make room.
      const candidates = spaces.map(([top, bottom]) => ({ top, bottom, size: Math.min(desired, (bottom - top) * cfg.aspect) }))
        .filter((g) => g.size >= cfg.minWidth).sort((a, b) => b.bottom - a.bottom);
      const best = candidates.find((g) => g.size >= desired * 0.85) || candidates[0];
      if (!best) return null;
      return { viewportWidth: width, width: best.size, height: best.size / cfg.aspect,
        y: best.bottom - best.size / cfg.aspect };
    }

    function applyGeometry(next) {
      geometry = next;
      if (!next) { visible(false); return; }
      y = next.y;
      actor.style.width = `${next.width}px`;
      actor.style.height = `${next.height}px`;
      position();
    }
    function showPoster(reason) {
      pauseAll();
      current = null;
      for (const entry of clips.values()) entry.video.classList.remove('is-current', 'is-preparing');
      if (poster && geometry) {
        x = clamp(geometry.viewportWidth - geometry.width - cfg.clearance, 0, geometry.viewportWidth - geometry.width);
        poster.hidden = false;
        visible(true);
        position();
      } else visible(false);
      report('static', reason);
    }

    function makeEntry(key, clip) {
      const video = document.createElement('video');
      video.className = 'x1-cat-video';
      video.muted = true;
      video.defaultMuted = true;
      video.playsInline = true;
      video.disablePictureInPicture = true;
      video.setAttribute('tabindex', '-1');
      video.setAttribute('aria-hidden', 'true');
      video.preload = 'auto';
      video.loop = !!clip.loop;
      actor.append(video);
      const entry = { clip, video, ready: null, alphaSupported: null };
      clips.set(key, entry);
      entry.ready = new Promise((resolve, reject) => {
        let timer;
        const cleanup = () => {
          clearTimeout(timer);
          video.removeEventListener('canplay', done);
          video.removeEventListener('error', fail);
          mediaCancels.delete(cancel);
        };
        const fail = () => { cleanup(); reject(new Error(`Cannot decode ${key}`)); };
        const cancel = () => { cleanup(); reject(new Error('Cancelled')); };
        const done = () => {
          if (!Number.isFinite(video.duration) || video.duration <= 0 || !video.videoWidth || !video.videoHeight) return fail();
          const samples = clip.motion?.samples;
          if (samples && Math.abs(samples[samples.length - 1][0] - video.duration) > 0.08) return fail();
          cleanup(); resolve(entry);
        };
        video.addEventListener('canplay', done, { once: true });
        video.addEventListener('error', fail, { once: true });
        mediaCancels.add(cancel);
        timer = setTimeout(fail, cfg.loadTimeoutMs);
        video.src = clip.src;
        video.load();
      });
      // Errors after load also become a quiet static fallback.
      video.addEventListener('error', () => { if (active && current === entry) showPoster('media-error'); });
      return entry;
    }

    function bundle(dir) { return cfg.actions[dir]; }
    function canRest(dir) {
      const set = bundle(dir);
      if (!set || !['stop', 'idle', 'start'].every((kind) => clips.has(`${dir}:${kind}`) && !set[kind].loop)) return false;
      // Pose IDs provide a structural transition contract, not proof of
      // visual continuity. That must still be inspected independently.
      return !!set.walk.startPose && set.stop.startPose === set.walk.startPose &&
        !!set.stop.endPose && set.idle.startPose === set.stop.endPose &&
        !!set.idle.endPose && set.start.startPose === set.idle.endPose && set.start.endPose === set.walk.startPose;
    }
    function checkAlpha(entry) {
      const video = entry.video;
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 1;
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      if (!ctx) return false;
      const sample = (px, py) => {
        ctx.clearRect(0, 0, 1, 1);
        ctx.drawImage(video, Math.floor(px * (video.videoWidth - 1)), Math.floor(py * (video.videoHeight - 1)), 1, 1, 0, 0, 1, 1);
        return ctx.getImageData(0, 0, 1, 1).data[3];
      };
      try {
        // Known empty canvas corners plus opaque torso rule out browsers
        // decoding an alpha WebM as a black opaque rectangle or blank frame.
        return sample(.98, .02) < 24 && sample(.02, .02) < 24 && sample(.98, .98) < 24 &&
          Math.max(sample(.50, .40), sample(.65, .50)) > 160;
      } catch { return false; }
    }
    function seekTo(video, target) {
      if (Math.abs(video.currentTime - target) < .001 && !video.seeking) return Promise.resolve();
      return new Promise((resolve, reject) => {
        let settled = false;
        const finish = (error) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer); video.removeEventListener('seeked', done); selectionCancels.delete(cancel);
          error ? reject(error) : resolve();
        };
        const done = () => finish();
        const cancel = () => finish(new Error('Cancelled'));
        const timer = setTimeout(() => finish(new Error('Seek unavailable')), 4000);
        selectionCancels.add(cancel);
        video.addEventListener('seeked', done, { once: true });
        video.currentTime = target;
      });
    }
    function presentTwoFrames(video, target) {
      return new Promise((resolve, reject) => {
        let count = 0, previous = -1, callbackId = 0, fallbackRaf = 0;
        let settled = false;
        const finish = (error) => {
          if (settled) return;
          settled = true;
          clearTimeout(timer);
          if (callbackId && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(callbackId);
          cancelAnimationFrame(fallbackRaf);
          selectionCancels.delete(cancel);
          error ? reject(error) : resolve();
        };
        const cancel = () => finish(new Error('Cancelled'));
        const accept = (time) => {
          if (settled) return true;
          if (!video.seeking && video.readyState >= 2 && time >= target - .001 &&
              (count > 0 || time < target + .75) && time > previous + .001) { count++; previous = time; }
          if (count >= 2) { finish(); return true; }
          return false;
        };
        const next = () => {
          if (settled) return;
          if (video.requestVideoFrameCallback) callbackId = video.requestVideoFrameCallback((_, metadata) => {
            if (!accept(metadata.mediaTime)) next();
          });
          else fallbackRaf = requestAnimationFrame(() => { if (!accept(video.currentTime)) next(); });
        };
        const timer = setTimeout(() => finish(new Error('Frames not presented')), 4000);
        selectionCancels.add(cancel);
        next();
      });
    }
    function canGreet(now) {
      const entry = clips.get(`${direction}:greeting`);
      if (!entry || passGreeted || passWalkLoops !== 1 || now < nextGreeting) return false;
      const clip = entry.clip;
      if (clip.loop || !clip.entryOnly || !Number.isFinite(clip.resumeWalkAt)) return false;
      const distance = displacement(clip, entry.video.duration) * geometry.width / clip.motion.referenceWidth;
      const margin = Math.max(12, clip.entryMargin || 12);
      return direction === 'right' ? x + distance <= -margin : x + geometry.width - distance >= geometry.viewportWidth + margin;
    }
    async function select(kind, startAt = 0, offset = null) {
      const entry = clips.get(`${direction}:${kind}`);
      if (!entry) return false;
      const token = epoch, selection = ++selectionSerial;
      const ownsSelection = () => !destroyed && token === epoch && selection === selectionSerial && active && !document.hidden && !reduced.matches;
      try {
        await entry.ready;
        if (!ownsSelection()) return false;
        const old = current;
        old?.video.pause();
        entry.video.classList.add('is-preparing');
        await seekTo(entry.video, startAt);
        if (!ownsSelection()) return false;
        const frames = presentTwoFrames(entry.video, startAt).then(() => null, (error) => error);
        await entry.video.play();
        if (!ownsSelection()) return false;
        const frameError = await frames;
        if (!ownsSelection()) return false;
        if (frameError) throw frameError;
        if (entry.alphaSupported === null) entry.alphaSupported = checkAlpha(entry);
        if (!entry.alphaSupported) {
          entry.video.classList.remove('is-preparing'); entry.video.pause(); showPoster('alpha-unavailable'); return false;
        }
        for (const other of clips.values()) {
          if (other !== entry) { other.video.pause(); other.video.classList.remove('is-current', 'is-preparing'); }
        }
        current = entry;
        entry.video.classList.remove('is-preparing');
        entry.video.classList.add('is-current');
        poster && (poster.hidden = true);
        const scale = geometry.width / (entry.clip.motion?.referenceWidth || geometry.width);
        const sign = direction === 'right' ? 1 : -1;
        if (offset) { x += sign * offset[0] * scale; y += offset[1] * scale; }
        // Two buffered frames may advance the clip; carry their root motion
        // into the first visible frame rather than presenting a stale pose.
        x += sign * Math.max(0, displacement(entry.clip, entry.video.currentTime) - displacement(entry.clip, startAt)) * scale;
        lastTime = entry.video.currentTime;
        lastProgressAt = performance.now();
        currentlyStalled = false;
        telemetry.activeStallMs = 0;
        meowed = false;
        report(kind === 'walk' ? 'walking' : kind === 'greeting' ? 'greeting' : kind === 'idle' ? 'idle' : kind === 'stop' ? 'stopping' : 'starting');
        position();
        visible(true);
        return true;
      } catch {
        // A stale selection must never pause or clear a newer selection's frame.
        if (!ownsSelection()) return false;
        entry.video.classList.remove('is-preparing');
        showPoster('playback-unavailable');
        return false;
      }
    }

    async function beginPass() {
      if (!geometry || destroyed || !active || document.hidden || reduced.matches) return;
      x = direction === 'right' ? -geometry.width - 20 : geometry.viewportWidth + 20;
      y = geometry.y;
      position();
      visible(false);
      passWalkLoops = 0; passGreeted = false;
      rested = false;
      restAt = direction === 'right' ? geometry.viewportWidth * 0.45 : geometry.viewportWidth * 0.55 - geometry.width;
      if (await select('walk')) schedule();
    }

    function schedule() { if (!raf && active && !destroyed && !document.hidden && !reduced.matches) raf = requestAnimationFrame(tick); }
    function tick(now) {
      raf = 0;
      if (!active || destroyed || document.hidden || reduced.matches || !geometry) return;
      if (state === 'offscreen') {
        if (now >= waitUntil) {
          // Facing changes only when the entire video is beyond the viewport.
          const other = direction === 'right' ? 'left' : 'right';
          if (clips.has(`${other}:walk`)) direction = other;
          report('loading');
          void beginPass();
        } else schedule();
        return;
      }
      if (!current) return;
      const { video, clip } = current;
      const t = video.currentTime;
      const justWrapped = t + 0.001 < lastTime && clip.loop;
      if (justWrapped) { telemetry.loopCount++; if (state === 'walking') passWalkLoops++; }
      if (Math.abs(t - lastTime) > 0.0001) {
        lastProgressAt = now; currentlyStalled = false; telemetry.activeStallMs = 0;
      } else if (!video.paused && !video.ended && now - lastProgressAt > 250) {
        if (!currentlyStalled) { telemetry.stallCount++; currentlyStalled = true; }
        telemetry.activeStallMs = Math.round(now - lastProgressAt);
        telemetry.longestStallMs = Math.max(telemetry.longestStallMs, telemetry.activeStallMs);
      }
      let delta = displacement(clip, t) - displacement(clip, lastTime);
      if (justWrapped) delta += displacement(clip, video.duration);
      // Media time is the clock: a stalled decoder cannot leave paws walking
      // at one speed while the element continues sliding at another speed.
      const scale = geometry.width / (clip.motion?.referenceWidth || geometry.width);
      x += (direction === 'right' ? 1 : -1) * Math.max(0, delta) * scale;
      lastTime = t;
      position();

      if ((state === 'greeting' || (state === 'idle' && now >= nextMeow)) && !meowed && Number.isFinite(clip.meowAt) && t >= clip.meowAt) {
        meowed = true;
        nextMeow = now + sleepRange(cfg.meowGapMs);
        if (audioEnabled && audio) {
          audio.currentTime = Math.max(0, t - clip.meowAt);
          void audio.play().catch(() => { audioEnabled = false; audio.muted = true; syncButtons(); });
        }
      }
      if (state === 'walking') {
        const leftScreen = direction === 'right' ? x > geometry.viewportWidth + 16 : x + geometry.width < -16;
        if (leftScreen) {
          video.pause(); visible(false); report('offscreen');
          waitUntil = now + sleepRange(cfg.restMs);
        } else if (justWrapped && canGreet(now)) {
          passGreeted = true; telemetry.greetingCount++;
          nextGreeting = now + sleepRange(cfg.meowGapMs);
          video.pause(); report('loading'); void select('greeting').then(schedule); return;
        } else if (!rested && canRest(direction) && (direction === 'right' ? x >= restAt : x <= restAt)) {
          // Only stop at the configured cycle boundary, not mid-stance.
          if (justWrapped) { rested = true; video.pause(); report('loading'); void select('stop').then(schedule); return; }
        }
      } else if (video.ended) {
        if (state === 'greeting') {
          audio?.pause();
          report('loading');
          void select('walk', clip.resumeWalkAt, clip.resumeOffset || [0, 0]).then(schedule);
          return;
        }
        const next = state === 'stopping' ? 'idle' : state === 'idle' ? 'start' : state === 'starting' ? 'walk' : null;
        if (next) { report('loading'); void select(next).then(schedule); return; }
      }
      if (state === 'greeting') {
        const margin = Math.max(12, clip.entryMargin || 12);
        const safe = direction === 'right' ? x <= -margin : x + geometry.width >= geometry.viewportWidth + margin;
        if (!safe) {
          telemetry.greetingEdgeViolations++; video.pause(); audio?.pause(); visible(false);
          report('offscreen', 'greeting-edge-guard'); waitUntil = now + sleepRange(cfg.restMs);
        }
      }
      schedule();
    }

    async function start() {
      const token = ++epoch;
      pauseAll();
      applyGeometry(measure());
      if (!geometry) { report('no-space'); return; }
      if (reduced.matches) return showPoster('reduced-motion');
      if (document.hidden) { report('suspended'); return; }
      report('loading');
      visible(false);
      const jobs = [];
      for (const dir of ['right', 'left']) {
        const set = bundle(dir);
        if (!validClip(set?.walk, 'walk')) continue;
        for (const kind of ['walk', 'greeting', 'stop', 'idle', 'start']) {
          if (!validClip(set[kind], kind)) continue;
          const key = `${dir}:${kind}`;
          const entry = clips.get(key) || makeEntry(key, set[kind]);
          jobs.push(entry.ready.catch(() => { if (clips.get(key) === entry) clips.delete(key); entry.video.remove(); }));
        }
      }
      await Promise.all(jobs);
      if (destroyed || token !== epoch || !active) return;
      if (!clips.has('right:walk') && !clips.has('left:walk')) return showPoster('no-valid-walk');
      direction = clips.has('right:walk') ? 'right' : 'left';
      await beginPass();
    }

    function setActive(value) {
      if (destroyed || active === !!value) return;
      active = !!value;
      layer.hidden = !active;
      syncButtons();
      if (active) void start();
      else { ++epoch; pauseAll(); visible(false); report('inactive'); }
    }
    async function setAudioEnabled(value) {
      if (!value || !audio) { audioEnabled = false; if (audio) { audio.pause(); audio.muted = true; } syncButtons(); return false; }
      if (navigator.userActivation && !navigator.userActivation.isActive) return false;
      try {
        // Unlock silently from an explicit click; actual meows wait for a
        // matching mouth-motion cue in the greeting, never a PDF event.
        audio.muted = true;
        await audio.play();
        audio.pause(); audio.currentTime = 0; audio.muted = false;
        audioEnabled = true; syncButtons(); return true;
      } catch { audioEnabled = false; syncButtons(); return false; }
    }
    function attachSoundButton(host, options = {}) {
      if (!(host instanceof Element)) throw new TypeError('Provide an existing non-overlay control host');
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'x1-cat-sound';
      if (options.compact) { button.dataset.compact = 'true'; button.classList.add('is-compact'); }
      button.dataset.x1CatControl = '';
      button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M11 5 6 9H3v6h3l5 4Z"/><g data-sound-on><path d="M15 8a6 6 0 0 1 0 8M18 5a10 10 0 0 1 0 14"/></g><g data-sound-off><path d="m16 9 5 6m0-6-5 6"/></g></svg>';
      button.addEventListener('click', () => { void setAudioEnabled(!audioEnabled); });
      host.append(button); buttons.add(button); observer.observe(host); syncButtons(); relayout();
      return button;
    }
    function relayout() {
      if (!active || destroyed || layoutQueued) return;
      layoutQueued = true;
      requestAnimationFrame(() => {
        layoutQueued = false;
        if (!active || destroyed) return;
        const next = measure();
        const changed = !geometry || !next || Math.abs(next.width - geometry.width) > 1 || Math.abs(next.y - geometry.y) > 1 || next.viewportWidth !== geometry.viewportWidth;
        if (!changed) return;
        // Geometry changes invalidate the route; hide before repositioning.
        // A transient absence is preferable to crossing a form or teleporting.
        ++epoch; pauseAll(); visible(false); current = null; applyGeometry(next);
        if (!next) report('no-space');
        else if (reduced.matches) showPoster('reduced-motion');
        else void start();
      });
    }
    function visibility() {
      if (!active) return;
      if (document.hidden) { ++epoch; pauseAll(); visible(false); report('suspended'); }
      else void start();
    }
    function motionPreference() { if (active) void start(); }
    const observer = new ResizeObserver(relayout);
    observer.observe(document.documentElement);
    document.querySelectorAll('.card, .test-banner, .flash-list, .back-link').forEach((node) => observer.observe(node));
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('scroll', relayout, { passive: true });
    window.addEventListener('resize', relayout, { passive: true });
    reduced.addEventListener('change', motionPreference);

    function destroy() {
      if (destroyed) return;
      destroyed = true; active = false; ++epoch; pauseAll();
      for (const cancel of [...mediaCancels]) cancel();
      observer.disconnect();
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('scroll', relayout);
      window.removeEventListener('resize', relayout);
      reduced.removeEventListener('change', motionPreference);
      for (const entry of clips.values()) { entry.video.removeAttribute('src'); entry.video.load(); }
      clips.clear(); layer.remove();
      for (const button of buttons) button.remove();
      buttons.clear();
      if (audio) { audio.removeAttribute('src'); audio.load(); }
    }
    function playbackTelemetry() {
      let totalVideoFrames = 0, droppedVideoFrames = 0;
      for (const entry of clips.values()) {
        const quality = entry.video.getVideoPlaybackQuality?.();
        totalVideoFrames += quality?.totalVideoFrames || entry.video.webkitDecodedFrameCount || 0;
        droppedVideoFrames += quality?.droppedVideoFrames || entry.video.webkitDroppedFrameCount || 0;
      }
      return { ...telemetry, totalVideoFrames, droppedVideoFrames };
    }
    return { setActive, setAudioEnabled, attachSoundButton, refreshLayout: relayout, destroy,
      getState: () => ({ state, active, direction, audioEnabled, geometry: geometry && { ...geometry },
        position: { x, y }, media: current ? { time: current.video.currentTime, duration: current.video.duration,
          width: current.video.videoWidth, height: current.video.videoHeight, paused: current.video.paused,
          readyState: current.video.readyState } : null, telemetry: playbackTelemetry() }) };
  }

  window.X1CatTheme = Object.freeze({ create });
})();

(() => {
  'use strict';
  let controller;
  const root = document.documentElement;
  const greeting = {"loop":false,"entryOnly":true,"entryMargin":12,"resumeWalkAt":0,"resumeOffset":[-24,4],"meowAt":0.8,"motion":{"referenceWidth":896,"samples":[[0.0,0.0],[0.041666666666666664,12.8609],[0.08333333333333333,24.5567],[0.125,34.918],[0.16666666666666666,43.9175],[0.20833333333333334,53.2622],[0.25,63.6841],[0.2916666666666667,73.73],[0.3333333333333333,83.5334],[0.375,93.1625],[0.4166666666666667,102.6319],[0.4583333333333333,110.6387],[0.5,118.7054],[0.5416666666666666,126.9709],[0.5833333333333334,135.2724],[0.625,142.9558],[0.6666666666666666,150.5568],[0.7083333333333334,157.6982],[0.75,164.4448],[0.7916666666666666,171.2833],[0.8333333333333334,178.4791],[0.875,185.6657],[0.9166666666666666,192.9846],[0.9583333333333334,200.3504],[1.0,207.4807],[1.0416666666666667,214.7909],[1.0833333333333333,222.4044],[1.125,230.4299],[1.1666666666666667,238.8674],[1.2083333333333333,247.7169],[1.25,256.246],[1.2916666666666667,263.9995],[1.3333333333333333,271.0062],[1.375,277.1873],[1.4166666666666667,282.356],[1.4583333333333333,287.0244],[1.5,291.5735],[1.5416666666666667,295.9485],[1.5833333333333333,300.2788],[1.625,304.3389],[1.6666666666666667,307.8125],[1.7083333333333333,311.388],[1.75,315.2027],[1.7916666666666667,318.723],[1.8333333333333333,322.3355],[1.875,326.4403],[1.9166666666666667,330.3024],[1.9583333333333333,333.8256],[2.0,337.4722],[2.0416666666666665,341.2234],[2.0833333333333335,345.1878],[2.125,349.3849],[2.1666666666666665,353.9417],[2.2083333333333335,358.7867],[2.25,363.8992],[2.2916666666666665,369.2892],[2.3333333333333335,375.0734],[2.375,381.1476],[2.4166666666666665,387.3863],[2.4583333333333335,393.766514],[2.5,400.217957],[2.5416666666666665,406.637043],[2.5833333333333335,412.897686],[2.625,419.1294],[2.6666666666666665,425.332186],[2.7083333333333335,431.506043],[2.75,437.550557],[2.7916666666666665,443.862214],[2.8333333333333335,452.114],[2.875,460.653],[2.9166666666666665,469.2],[2.9583333333333335,477.8612],[3.0,486.2459],[3.0416666666666665,494.6306]]}};
  const motion = { referenceWidth: 896, samples: [[0, 0], [68 / 24, 68 * 5.8]] };
  function syncTheme() {
    const active = root.dataset.theme === 'cat';
    if (active && !controller) {
      if (!window.ResizeObserver || !window.MutationObserver) return;
      const actions = {};
      for (const direction of ['right', 'left']) {
        actions[direction] = {
          walk: { src: `/cat-theme/maine-coon-walk-${direction}.webm`, loop: true, motion },
          greeting: { ...greeting, src: `/cat-theme/maine-coon-greeting-${direction}.webm` },
        };
      }
      controller = window.X1CatTheme.create({
        width: 250, minWidth: 110, aspect: 640 / 366, restMs: [1200, 2200],
        actions, poster: '/cat-theme/maine-coon-poster.webp', meow: '/cat-theme/maine-coon-greeting-meow.mp3',
      });
      const host = document.querySelector('[data-cat-sound-host]');
      if (host) controller.attachSoundButton(host, { compact: true });
    }
    controller?.setActive(active);
  }
  function boot() {
    if (!window.MutationObserver) return;
    new MutationObserver(syncTheme).observe(root, { attributes: true, attributeFilter: ['data-theme'] });
    syncTheme();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
