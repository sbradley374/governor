/* Hardware rehearsal never sends microphone samples to the server. */
(() => {
  let microphone = null, meterContext = null, timer = null, checking = false, generation = 0;
  let peak = 0;
  const message = text => $('bench-notice').textContent = text;
  const report = async fn => { try { message(''); await fn(); } catch (e) { message(e.message); } };

  async function refresh() {
    const info = await api('/setup', undefined, 'GET');
    $('setup-checks').replaceChildren();
    for (const check of info.checks) {
      const row = document.createElement('div');
      row.className = 'setup-check';
      const name = document.createElement('strong'); name.textContent = check.name;
      const badge = document.createElement('span'); badge.className = 'setup-status';
      badge.textContent = ({ready:'READY', demo:'DEMO', optional:'OPTIONAL', manual:'CHECK', attention:'CHECK SETUP'})[check.status];
      const detail = document.createElement('p'); detail.textContent = check.detail;
      row.append(name, badge, detail); $('setup-checks').append(row);
    }
    if (state.display) {
      $('palette').value = state.display.palette;
      $('brightness').value = Math.round(state.display.brightness * 100);
      $('inset').value = Math.round(state.display.inset * 100);
      const seconds = String(state.display.idle_seconds);
      if (![...$('idle-time').options].some(o => o.value === seconds)) {
        $('idle-time').add(new Option(`After ${seconds} seconds`, seconds));
      }
      $('idle-time').value = seconds;
      updateLabels();
    }
  }
  function updateLabels() {
    $('brightness-value').value = $('brightness').value + '%';
    $('inset-value').value = $('inset').value + '%';
  }
  function stopMic() {
    generation++;
    checking = false;
    clearTimeout(timer);
    if (microphone) microphone.getTracks().forEach(track => track.stop());
    microphone = null;
    if (meterContext) meterContext.close().catch(() => {});
    meterContext = null;
    $('mic-level').value = 0;
    $('test-mic').textContent = 'Check microphone';
  }
  window.governorWorkbench = {stopMic, get checking() { return checking; }};
  $('test-mic').onclick = () => report(async () => {
    if (checking) { stopMic(); $('mic-note').textContent = 'Microphone check stopped.'; return; }
    if (busy || recording || (state.status && state.status !== 'idle')) throw Error('Finish the current turn or resume before checking the microphone.');
    if (!navigator.mediaDevices) throw Error('Open this console on localhost in a browser with microphone support.');
    checking = true;
    const currentGeneration = ++generation;
    $('test-mic').textContent = 'Cancel check';
    try {
      const incoming = await navigator.mediaDevices.getUserMedia({audio: {echoCancellation: true, noiseSuppression: true}});
      if (currentGeneration !== generation) { incoming.getTracks().forEach(t => t.stop()); return; }
      microphone = incoming;
      meterContext = new AudioContext();
      await meterContext.resume();
      if (currentGeneration !== generation) return;
      const source = meterContext.createMediaStreamSource(microphone);
      const analyser = meterContext.createAnalyser(); analyser.fftSize = 1024;
      source.connect(analyser); // Intentionally not connected to speakers; prevents feedback.
      const samples = new Float32Array(analyser.fftSize);
      peak = 0;
      $('mic-note').textContent = 'Speak normally for ten seconds. Audio stays in this browser.';
      function measure() {
        if (currentGeneration !== generation) return;
        analyser.getFloatTimeDomainData(samples);
        const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
        peak = Math.max(peak, rms);
        $('mic-level').value = Math.min(1, rms * 8);
        requestAnimationFrame(measure);
      }
      measure();
      timer = setTimeout(() => {
        const detected = peak > .005;
        stopMic();
        $('mic-note').textContent = detected ? 'Sound detected. Check complete; microphone released.' : 'Little or no sound detected. Check the selected microphone and input volume.';
      }, 10000);
    } catch (e) { stopMic(); throw e; }
  });
  $('test-voice').onclick = () => report(async () => {
    if (busy || recording) throw Error('Finish the current turn first.');
    stopMic();
    if (muted) { $('sound').click(); }
    await submit('/test-voice', {session_id: state.session_id});
  });
  $('expressions').onclick = event => report(async () => {
    const emotion = event.target.dataset.emotion;
    if (!emotion) return;
    await api('/preview', {emotion});
    message(`${emotion[0].toUpperCase() + emotion.slice(1)} expression — eight-second preview.`);
  });
  $('display-form').onsubmit = event => {
    event.preventDefault();
    report(async () => {
      await api('/display', {palette: $('palette').value, brightness: Number($('brightness').value) / 100,
        inset: Number($('inset').value) / 100, idle_seconds: Number($('idle-time').value)});
      message('Display settings saved. The CRT view updates automatically.');
    });
  };
  $('brightness').oninput = updateLabels;
  $('inset').oninput = updateLabels;
  $('refresh-setup').onclick = () => report(refresh);
  $('face').onclick = () => report(() => api('/wake', {}));
  $('face').onkeydown = event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); $('face').click(); }
  };
  window.addEventListener('pagehide', stopMic);
  document.addEventListener('visibilitychange', () => { if (document.hidden) stopMic(); });
  if (!kiosk) report(async () => {
    // Read state here too so settings load correctly regardless of initial request order.
    const initial = await api('/state', undefined, 'GET');
    if (!state.session_id) state = initial;
    await refresh();
  });
})();
