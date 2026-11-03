/* Room preferences and a hardware-free arrival rehearsal. */
(() => {
  $('interaction-form').onsubmit = event => {
    event.preventDefault();
    guard(async () => {
      await api('/interaction', {greetings: $('room-greetings').checked,
        followup_seconds: Number($('followup-seconds').value),
        greeting_cooldown: Number($('greeting-cooldown').value) * 60});
      $('room-note').textContent = 'Room manners saved. Start governor listen on the Pi to enable wake detection and camera greetings.';
    });
  };
  $('rehearse-greeting').onclick = () => guard(async () => {
    if (busy || recording || state.status !== 'idle') throw Error('Finish the current conversation first.');
    await submit('/room/rehearse', {session_id: state.session_id});
  });
  if (!kiosk) guard(async () => {
    const current = await api('/state', undefined, 'GET');
    const options = current.interaction;
    $('room-greetings').checked = options.greetings;
    $('followup-seconds').value = options.followup_seconds;
    $('greeting-cooldown').value = options.greeting_cooldown / 60;
  });
})();
