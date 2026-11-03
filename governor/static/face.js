/* Broad pixel shapes survive composite video. Rendering is capped at 30 fps. */
(() => {
  const canvas = document.getElementById('face');
  const ctx = canvas.getContext('2d');
  const palettes = {green: '#b8efa0', amber: '#ffcb75', ice: '#a4e8f5'};
  let state = {status: 'idle', emotion: 'neutral', paused: false};
  let level = 0, nextBlink = 3, blinkUntil = 0, lastFrame = -Infinity;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.governorFace = {setState: s => { state = s; render(performance.now(), true); }, setLevel: v => level = v};

  function rect(x, y, w, h) {
    ctx.fillRect(Math.round(x / 2) * 2, Math.round(y / 2) * 2,
      Math.round(w / 2) * 2, Math.round(h / 2) * 2);
  }

  function render(ms, force = false) {
    if (!force && (document.hidden || ms - lastFrame < 1000 / 30)) return;
    lastFrame = ms;
    const t = ms / 1000;
    const speaking = state.status === 'speaking';
    const mood = state.preview || state.emotion;
    const palette = state.display?.palette || 'green';
    const ink = palettes[palette] || palettes.green;
    const inset = state.display?.inset ?? .04;
    if (t > nextBlink) { blinkUntil = t + .13; nextBlink = t + 3 + Math.random() * 5; }
    ctx.fillStyle = '#0b180f';
    ctx.fillRect(0, 0, 640, 480);
    ctx.save();
    ctx.translate(640 * inset, 480 * inset);
    ctx.scale(1 - 2 * inset, 1 - 2 * inset);
    ctx.fillStyle = ink;
    ctx.shadowColor = ink;
    ctx.shadowBlur = state.paused ? 2 : 10;
    const dx = reduced ? 0 : Math.sin(t * .47) * 7;
    const dy = reduced ? 0 : Math.sin(t * .8) * 3;
    const blink = t < blinkUntil || state.paused || state.dimmed;
    const eyeH = blink ? 7 : mood === 'surprised' ? 76 : mood === 'happy' ? 42 : 60;
    const y = 178 + dy;
    for (const x of [190 + dx, 374 + dx]) {
      rect(x, y + (60 - eyeH) / 2, 76, eyeH);
      if (!blink && mood === 'happy') {
        ctx.clearRect(x - 2, y + 35, 12, 23);
        ctx.clearRect(x + 66, y + 35, 12, 23);
      }
    }
    if (!blink) {
      if (mood === 'curious' || mood === 'thinking') rect(372 + dx, 148 + dy, 80, 8);
      else if (mood === 'sad') { rect(188 + dx, 157 + dy, 50, 7); rect(404 + dx, 157 + dy, 50, 7); }
    }
    if (speaking) {
      const amplitude = Math.max(level, .1 + Math.abs(Math.sin(t * 12)) * .25);
      for (let i = 0; i < 9; i++) {
        const h = 8 + Math.abs(Math.sin(t * 14 + i * .9)) * amplitude * 62;
        rect(248 + i * 17, 318 - h / 2, 10, h);
      }
    } else if (state.status === 'listening') {
      for (let i = 0; i < 7; i++) {
        const h = 8 + Math.abs(Math.sin(t * 8 + i)) * 27;
        rect(265 + i * 17, 320 - h / 2, 9, h);
      }
    } else if (mood === 'surprised') rect(302, 300, 36, 40);
    else if (mood === 'sad') {
      rect(272, 318, 96, 8); rect(264, 326, 8, 10); rect(368, 326, 8, 10);
    } else {
      rect(264, 320, 112, 9); rect(252, 308, 12, 12); rect(376, 308, 12, 12);
    }
    ctx.shadowBlur = 0;
    ctx.globalAlpha = .15;
    for (let i = 0; i < 3; i++) rect(304 + i * 13, 387, 5, 5);
    ctx.restore();
  }
  function tick(ms) { render(ms); requestAnimationFrame(tick); }
  render(performance.now(), true);
  requestAnimationFrame(tick);
})();
