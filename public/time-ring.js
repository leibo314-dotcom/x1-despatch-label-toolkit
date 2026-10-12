/* Drawing score exported from the user's Claude artifact, unchanged.
 * Source and original HTML: docs/TIME_RING_SOURCE.md, docs/time-ring-original.html.
 * Playback, theme eligibility and page navigation are owned by generation-animation.js.
 */
window.X1TimeRing = (cv) => {
  const DUR = 15;
  const SCALE = 10 / DUR;
  const ctx = cv.getContext('2d');
  if (!ctx) throw new Error('Canvas is unavailable');
  const C = { bg: '#ffffff', inkRGB: [29, 40, 52] };
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${Math.max(0, Math.min(1, a))})`;
  const hsla = (h, a, s = 78, l = 52) => `hsla(${((h % 360) + 360) % 360},${s}%,${l}%,${Math.max(0, Math.min(1, a))})`;
  let W = 0, H = 0;
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  // ---------- easing ----------
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const ramp = (t, a, b) => clamp((t - a) / (b - a));
  const easeOut = x => 1 - Math.pow(1 - x, 3);
  const easeInOut = x => x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
  const smooth = x => x * x * (3 - 2 * x);

  // ---------- warped time: the clock speeds up, then lets go ----------
  // tau(t) = integral of speed; speed rises from 1 to ~2.8 between 5.2s and 7.9s
  const STEP = 0.005;
  const tauTable = [0];
  const speed = t => {
    if (t < 5.2 || t > 7.9) return 1;
    const x = (t - 5.2) / 2.7;
    return 1 + 1.8 * Math.pow(Math.sin(Math.PI * x), 2);
  };
  // built over real seconds, so rotation keeps its pace while the phases last longer
  for (let t = STEP; t <= DUR + STEP; t += STEP) tauTable.push(tauTable[tauTable.length - 1] + speed(t * SCALE) * STEP);
  const tauReal = t => {
    const i = clamp(t / STEP, 0, tauTable.length - 2);
    const k = Math.floor(i), f = i - k;
    return tauTable[k] * (1 - f) + tauTable[k + 1] * f;
  };
  const tau = s => tauReal(s / SCALE);   // takes a score time, returns warped real time

  // ---------- scene ----------
  const RINGS = 7;
  const rings = Array.from({ length: RINGS }, (_, i) => ({
    frac: (i + 1) / RINGS,
    appear: 2.0 + i * 0.22,
    omega: Math.PI * 2 * 1.05 / (1 + i * 0.6),    // inner turns fast, outer slow
    hue: 345 - i * (300 / (RINGS - 1))            // rose → orange → gold → green → teal → blue → violet
  }));

  // seeded particles: "dust" of moments drifting outward
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const DUST = Array.from({ length: 150 }, () => ({
    born: 2.6 + rnd() * 4.6,
    a0: rnd() * Math.PI * 2,
    v: 0.05 + rnd() * 0.1,
    spin: (rnd() - .5) * 0.9,
    size: 0.9 + rnd() * 1.6,
    hue: rnd() * 360
  }));

  function draw(tReal) {
    const t = tReal * SCALE;              // position in the 10-beat score
    const cx = W / 2, cy = H / 2;
    const R = Math.min(W, H) * 0.42;
    const unit = Math.max(1, Math.min(W, H) / 600);

    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = C.bg;
    ctx.fillRect(0, 0, W, H);
    if (t <= 0.5 || t >= 9.5) return;          // empty frames at both ends

    const collapse = easeInOut(ramp(t, 7.6, 8.9));   // everything folds back to the point
    const shrink = 1 - collapse;
    const T = tau(t);

    // --- the long hand: one slow turn across the whole middle ---
    const handIn = smooth(ramp(t, 2.4, 3.4));
    if (handIn > 0 && shrink > 0) {
      const p = (T - tau(2.4)) / (tau(7.8) - tau(2.4));
      const ang = -Math.PI / 2 + Math.PI * 2 * p;
      const len = R * 1.06 * handIn * shrink;
      const g = ctx.createLinearGradient(cx, cy, cx + Math.cos(ang) * len, cy + Math.sin(ang) * len);
      g.addColorStop(0, rgba(C.inkRGB, 0.0));
      g.addColorStop(1, rgba(C.inkRGB, 0.28 * handIn * shrink));
      ctx.strokeStyle = g;
      ctx.lineWidth = 1 * unit;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(ang) * len, cy + Math.sin(ang) * len);
      ctx.stroke();
    }

    // --- rings, each with a travelling point and its memory trail ---
    for (let i = 0; i < RINGS; i++) {
      const rg = rings[i];
      const grow = easeOut(ramp(t, rg.appear, rg.appear + 0.9));
      if (grow <= 0) continue;
      const r = R * rg.frac * grow * shrink;
      if (r < 0.5) continue;

      const hue = rg.hue + 12 * T;          // colours drift slowly as time passes

      // faint guide circle
      ctx.strokeStyle = hsla(hue, 0.22 * grow * Math.sqrt(shrink), 70, 62);
      ctx.lineWidth = 0.8 * unit;
      ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();

      // head angle and trail length (the trail is the past, it grows then is reeled in)
      const travelled = rg.omega * (T - tau(rg.appear));
      const head = -Math.PI / 2 + travelled;
      const trail = Math.min(travelled, Math.PI * 1.45) * (1 - collapse * 0.7);
      const SEG = 48;
      for (let s = 0; s < SEG; s++) {
        const a1 = head - trail * (s / SEG);
        const a2 = head - trail * ((s + 1) / SEG);
        const k = 1 - s / SEG;
        ctx.strokeStyle = hsla(hue + 40 * (1 - k), 0.85 * k * k * grow * (0.4 + 0.6 * shrink));
        ctx.lineWidth = (0.6 + 2.2 * k) * unit;
        ctx.lineCap = 'round';
        ctx.beginPath(); ctx.arc(cx, cy, r, a2, a1); ctx.stroke();
      }

      // the point itself
      const hx = cx + Math.cos(head) * r, hy = cy + Math.sin(head) * r;
      ctx.fillStyle = hsla(hue, 0.18 * grow);
      ctx.beginPath(); ctx.arc(hx, hy, 7 * unit, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = hsla(hue, grow, 85, 48);
      ctx.beginPath(); ctx.arc(hx, hy, 3 * unit, 0, Math.PI * 2); ctx.fill();
    }

    // --- dust: moments released from the centre, pulled back at the end ---
    for (const d of DUST) {
      const age = t - d.born;
      if (age <= 0) continue;
      const rr = d.v * R * age * 3.2 * shrink;
      if (rr > R * 1.15) continue;
      const fadeIn = ramp(age, 0, 0.35);
      const fadeEdge = 1 - ramp(rr, R * 0.75, R * 1.15);
      const a = d.a0 + d.spin * age + 0.25 * (T - tReal);
      const alpha = 0.75 * fadeIn * fadeEdge * (0.3 + 0.7 * shrink);
      if (alpha <= 0.01) continue;
      ctx.fillStyle = hsla(d.hue + 20 * T, alpha, 80, 55);
      ctx.beginPath();
      ctx.arc(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, d.size * unit, 0, Math.PI * 2);
      ctx.fill();
    }

    // --- the present: a single point that beats, gathers everything, then is gone ---
    const born = smooth(ramp(t, 0.5, 1.2));
    const beat = t => Math.exp(-Math.pow((t) / 0.09, 2));
    const pulse = beat(t - 1.45) + 0.8 * beat(t - 1.85) + 0.25 * Math.max(0, Math.sin(T * 2.2)) * ramp(t, 2.2, 3);
    const gather = Math.exp(-Math.pow((t - 8.95) / 0.22, 2));       // flare as all paths arrive
    const vanish = 1 - smooth(ramp(t, 9.0, 9.42));
    const coreR = (3.2 + 2.4 * pulse + 5 * gather) * unit * born * vanish;
    if (coreR > 0.05) {
      const glowR = coreR * (5 + 4 * gather);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowR);
      const coreHue = 30 + 45 * T;          // the present keeps changing colour
      g.addColorStop(0, hsla(coreHue, 0.45 * born * vanish, 90, 60));
      g.addColorStop(0.5, hsla(coreHue + 60, 0.18 * born * vanish, 90, 60));
      g.addColorStop(1, hsla(coreHue + 120, 0));
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx, cy, glowR, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = hsla(coreHue, born * vanish, 90, 50);
      ctx.beginPath(); ctx.arc(cx, cy, coreR, 0, Math.PI * 2); ctx.fill();
    }
  }


  return { duration: DUR * 1000, resize, draw };
};
