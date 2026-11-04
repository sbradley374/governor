/* Standalone local-file mode: no fetch, microphone, camera, audio, or API. */
(() => {
  const palettes = ['green', 'amber', 'ice'];
  const colors = {green:'#b8efa0', amber:'#ffcb75', ice:'#a4e8f5'};
  const routines = [
    {emotion:'neutral', gaze:[-20,0], caption:'OBSERVING THE GENERAL SITUATION.'},
    {emotion:'curious', gaze:[22,-9], caption:'A MATTER WORTH CONSIDERING.'},
    {emotion:'happy', gaze:[0,0], caption:'EVERYTHING APPEARS TO BE IN ORDER.'},
    {emotion:'thinking', gaze:[-12,-12], caption:'DELIBERATIONS ARE UNDER WAY.'},
    {emotion:'neutral', gaze:[18,5], caption:''},
    {emotion:'surprised', gaze:[0,-5], caption:'OH. INTERESTING.'},
    {emotion:'happy', gaze:[5,0], wink:'left', caption:'CARRY ON.'},
    {emotion:'neutral', gaze:[0,8], sleepy:true, caption:'A BRIEF ADMINISTRATIVE RECESS.'},
    {emotion:'curious', gaze:[-24,3], caption:''},
  ];
  let paused = false, palette = 'green', current = -1, nextAt = 0;
  let winkUntil = 0, holdUntil = 0, lastTime = performance.now(), gaze = [0,0], target = [0,0];
  let routine = {emotion:'neutral', caption:'THE GOVERNOR IS IN RESIDENCE.'};
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  try { const saved = localStorage.getItem('governor-ambient-palette'); if (palettes.includes(saved)) palette = saved; } catch {}
  const randomBetween = (a,b) => a + Math.random() * (b-a);
  function choose(now) {
    const offset = 1 + Math.floor(Math.random() * (routines.length - 1));
    current = (Math.max(0,current) + offset) % routines.length;
    routine = routines[current];
    winkUntil = now + 350;
    target = routine.gaze;
    holdUntil = now + randomBetween(3500,7500);
    nextAt = holdUntil + randomBetween(8000,18000);
  }
  function update() {
    const now = performance.now();
    const elapsed = Math.min(1000, now - lastTime); lastTime = now;
    if (document.hidden) return;
    if (!paused && !reduced && now >= nextAt) choose(now);
    const acting = now < holdUntil && !paused;
    if (!acting) target = [0,0];
    const blend = 1 - Math.exp(-elapsed / 550);
    gaze = gaze.map((v,i) => v + ((reduced ? 0 : target[i]) - v) * blend);
    const resting = paused || (acting && routine.sleepy);
    const caption = paused ? 'RESTING. SPACE TO WAKE.' : acting ? routine.caption : '';
    document.getElementById('caption').textContent = caption;
    document.documentElement.style.color = colors[palette];
    document.getElementById('face').style.opacity = resting ? '.35' : '1';
    window.governorFace.setState({status:'idle', emotion:acting ? routine.emotion : 'neutral', paused,
      dimmed:!!resting, pose:{x:gaze[0],y:gaze[1],wink:acting && now < winkUntil ? routine.wink : null},
      display:{palette,inset:.07}});
  }
  nextAt = performance.now() + 4000;
  // State updates are intentionally sparse; the renderer owns the animation loop.
  setInterval(update, 100);
  update();
  document.addEventListener('keydown', event => {
    const key = event.key.toLowerCase();
    if (event.repeat) return;
    if (key === ' ') { event.preventDefault(); paused = !paused; }
    else if (key === 'c') {
      palette = palettes[(palettes.indexOf(palette)+1)%palettes.length];
      try { localStorage.setItem('governor-ambient-palette',palette); } catch {}
    } else if (key === 'r') { paused = false; choose(performance.now()); }
    else if (key === 'h') { const help=document.getElementById('help'); help.hidden=!help.hidden; }
    else if (key === 'f') {
      if (document.fullscreenElement) document.exitFullscreen().catch(()=>{});
      else document.documentElement.requestFullscreen?.().catch(()=>{});
    }
    update();
  });
})();
