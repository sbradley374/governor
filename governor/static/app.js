const $=id=>document.getElementById(id);
let state={}, people=[], busy=false, muted=false, recorder=null, stream=null, recordTimer=null, recording=false, audio=null, audioContext=null, analyser=null, playbackGeneration=0,captureGeneration=0,controlGeneration=0,disconnected=false;
const kiosk=new URLSearchParams(location.search).has('display');
if(kiosk)document.body.classList.add('kiosk');
async function api(path,body,method='POST'){
  const options={method,headers:{'X-Governor-Client':'1'}};
  if(body instanceof FormData)options.body=body;
  else if(body!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body)}
  const response=await fetch('/api'+path,options);
  const data=await response.json();
  if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:'Please check the entered information.');
  return data;
}
function notice(text=''){$('notice').textContent=text}
function stopPlayback(){playbackGeneration++;if(audio){audio.pause();audio=null}if('speechSynthesis'in window)speechSynthesis.cancel();governorFace.setLevel(0)}
function stopRecording(discard=false){captureGeneration++;if(recorder&&recorder.state==='recording'){recorder.discard=discard;recorder.stop()}if(stream){stream.getTracks().forEach(t=>t.stop());stream=null}clearTimeout(recordTimer);recording=false;$('record').classList.remove('recording');$('record').textContent='● Talk to the Governor'}
async function poll(){
  try{
    const pollGeneration=controlGeneration;
    const next=await api('/state',undefined,'GET');
    if(pollGeneration!==controlGeneration){setTimeout(poll,500);return}
    if(next.paused||(state.session_id&&next.session_id!==state.session_id)||next.selected!==state.selected||(state.turn_id&&next.turn_id!==state.turn_id)){stopPlayback();stopRecording(true);window.governorWorkbench?.stopMic()}
    state=next;
    if(disconnected){notice();disconnected=false}
    document.body.dataset.palette=state.display?.palette||'green';
    document.documentElement.style.setProperty('--screen-brightness',String((state.display?.brightness??.85)*(state.dimmed ? .18 : 1)));
    if(state.dimmed)$('kiosk-caption').textContent='Resting. Click the face to wake.';
    $('connection').textContent='CONNECTED';
    governorFace.setState(recording?{...state,status:'listening'}:state);
    $('mode').textContent=state.provider==='demo'?'DEMO / OFFLINE':state.provider==='local'?'LOCAL / AI':'CLOUD / AI';
    $('provider-footer').textContent=state.provider==='demo'?'LOCAL DEMONSTRATION':state.provider==='local'?'LOCAL REASONING · LOCAL MEMORY':'CLOUD REASONING · LOCAL MEMORY';
    const label=recording?'LISTENING':({idle:'STANDING BY',speaking:'ON AIR',thinking:'CONSIDERING',listening:'TRANSCRIBING',paused:'RESTING'}[state.status]||state.status.toUpperCase());
    $('face-state').textContent='● '+label;$('activity').textContent=label;
    $('caption').textContent='“'+state.caption+'”';$('kiosk-caption').textContent=state.dimmed?'Resting. Click the face to wake.':state.error||state.caption;$('transcript').textContent=state.transcript?'YOU / '+state.transcript:'';
    $('pause').textContent=state.paused?'Resume':'Pause';
    $('send').disabled=busy||recording||state.paused||state.status!=='idle';
    $('record').disabled=!recording&&(busy||state.paused||state.status!=='idle'||state.provider==='demo');
    $('voice-note').textContent=state.provider==='demo'?'Demo uses scripted replies. Enable cloud or local AI mode for microphone conversation.':'Click to record, click again to send. Maximum 30 seconds.';
    $('camera-status').textContent=state.camera.status==='running'?'CAMERA ON':state.camera.status==='disabled'?'CAMERA OFF':'CAMERA NEEDS ATTENTION';
    $('camera-status').title=state.camera.status;
    const present=state.camera.present.map(id=>people.find(p=>p.id===id)?.name).filter(Boolean);
    $('presence').textContent=present.length?'Possibly present: '+present.join(', ')+'. Select the speaker above.':state.camera.status==='running'?`${state.camera.face_count} face(s) visible. Select who is speaking.`:'Camera recognition suggests presence; choose who is speaking.';
    const profile=people.find(p=>p.id===state.selected);
    $('speaker-label').textContent=profile?'SPEAKING WITH '+profile.name.toUpperCase():'SPEAKING WITH A VISITOR';
    if($('person').value!==(state.selected||'')){$('person').value=state.selected||'';await loadMemories()}
    $('clock').textContent=new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',hour12:false});
    if(state.error)notice(state.error);
  }catch(e){disconnected=true;$('connection').textContent='RECONNECTING';notice('Connection lost. Retrying…');stopPlayback();stopRecording(true);window.governorWorkbench?.stopMic()}
  setTimeout(poll,500);
}
async function loadPeople(){people=await api('/people',undefined,'GET');const selected=state.selected||$('person').value;$('person').replaceChildren(new Option('Visitor · no lasting memory',''));people.forEach(p=>$('person').add(new Option(p.name,p.id)));$('person').value=selected;await loadMemories()}
async function loadMemories(){const id=$('person').value;$('profile-details').hidden=!id;if(!id)return;const profile=people.find(p=>p.id===id);$('familiarity').textContent=`${profile?.turns||0} conversations · ${(profile?.turns||0)>10?'a familiar presence':'getting acquainted'}`;const facts=await api(`/people/${id}/memories`,undefined,'GET');if($('person').value!==id)return;$('memories').replaceChildren();facts.forEach(f=>{const row=document.createElement('div');row.className='memory';const text=document.createElement('span');text.textContent=f.text;const button=document.createElement('button');button.className='text-button';button.textContent='Forget';button.onclick=()=>guard(async()=>{await api(`/people/${id}/memories/${f.id}`,undefined,'DELETE');await loadMemories()});row.append(text,button);$('memories').append(row)})}
async function guard(fn){try{notice();await fn()}catch(e){notice(e.message)}}
async function done(turnId){try{await api('/playback/done',{turn_id:turnId})}catch(e){notice('Playback ended; reconnecting to the Governor.')}}
async function play(result){
  stopPlayback();const generation=playbackGeneration;
  if(muted){await done(result.turn_id);return}
  const complete=()=>{if(generation===playbackGeneration){governorFace.setLevel(0);done(result.turn_id)}};
  if(result.audio){
    audio=new Audio('data:audio/wav;base64,'+result.audio);audio.onended=complete;audio.onerror=complete;
    try{
      audioContext=audioContext||new AudioContext();await audioContext.resume();
      const source=audioContext.createMediaElementSource(audio);analyser=audioContext.createAnalyser();analyser.fftSize=256;source.connect(analyser);analyser.connect(audioContext.destination);
      const samples=new Uint8Array(analyser.frequencyBinCount);
      function levels(){if(generation!==playbackGeneration||!audio||audio.paused)return;analyser.getByteFrequencyData(samples);governorFace.setLevel(samples.reduce((a,b)=>a+b,0)/samples.length/100);requestAnimationFrame(levels)}
      await audio.play();levels();
    }catch(e){notice('Sound could not start. Click Sound on to enable audio.');complete()}
  }else if('speechSynthesis'in window){
    const utterance=new SpeechSynthesisUtterance(result.text);utterance.lang='en-GB';utterance.rate=.85;utterance.pitch=.65;utterance.onend=complete;utterance.onerror=complete;speechSynthesis.speak(utterance);
  }else{notice('No speech engine found. Install espeak-ng on the Pi.');complete()}
}
async function submit(path,body){
  if(busy)return;
  busy=true;controlGeneration++;stopRecording(true);window.governorWorkbench?.stopMic();notice();
  const submittedSession=body instanceof FormData?body.get('session_id'):body.session_id;
  try{
    const result=await api(path,body);
    const current=await api('/state',undefined,'GET');
    controlGeneration++;
    if((submittedSession&&current.session_id!==submittedSession)||current.turn_id!==result.turn_id)return;
    state=current;
    await play(result);await loadPeople();
  }catch(e){notice(e.message)}finally{busy=false}
}
$('talk-form').onsubmit=e=>{e.preventDefault();if(busy||recording)return;const text=$('message').value.trim();if(text){$('message').value='';submit('/turn',{text,session_id:state.session_id})}};
$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('talk-form').requestSubmit()}};
$('record').onclick=()=>guard(async()=>{
  if(recording){stopRecording();return}
  if(!navigator.mediaDevices||!window.MediaRecorder)throw Error('This browser cannot record audio. Use localhost in Chromium, or the native microphone worker.');
  window.governorWorkbench?.stopMic();stopPlayback();
  const session=state.session_id,generation=++captureGeneration;
  const incoming=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
  if(generation!==captureGeneration||session!==state.session_id||state.paused){incoming.getTracks().forEach(t=>t.stop());return}
  stream=incoming;
  const type=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(t=>MediaRecorder.isTypeSupported(t));
  try{recorder=new MediaRecorder(stream,type?{mimeType:type}:{});const current=recorder,chunks=[];
    current.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};
    current.onstop=()=>{if(current.discard)return;const blob=new Blob(chunks,{type:current.mimeType.split(';')[0]});const form=new FormData();form.append('file',blob,'speech');form.append('session_id',session);submit('/audio',form)};
    current.start();recording=true;$('record').classList.add('recording');$('record').textContent='■ Finish speaking';recordTimer=setTimeout(()=>stopRecording(),30000);
  }catch(e){stopRecording(true);throw e}
});
$('sound').onclick=()=>{muted=!muted;$('sound').textContent=muted?'Sound off':'Sound on';$('sound').setAttribute('aria-pressed',String(!muted));if(muted){stopPlayback();if(state.turn_id)done(state.turn_id)}};
$('pause').onclick=()=>guard(async()=>{controlGeneration++;stopRecording(true);stopPlayback();state=await api('/power',{paused:!state.paused});controlGeneration++});
$('fullscreen').onclick=()=>{window.open('/?display=1','governor-display')};
$('person').onchange=()=>guard(async()=>{controlGeneration++;stopPlayback();stopRecording(true);state=await api('/select',{person_id:$('person').value||null});controlGeneration++;await loadMemories()});
$('new-person').onclick=()=>$('intro-dialog').showModal();$('cancel-intro').onclick=()=>$('intro-dialog').close();
$('intro-form').onsubmit=e=>{e.preventDefault();guard(async()=>{const p=await api('/people',{name:$('name').value,consent:$('consent').checked});state=await api('/select',{person_id:p.id});$('intro-dialog').close();$('intro-form').reset();await loadPeople()})};
$('memory-form').onsubmit=e=>{e.preventDefault();guard(async()=>{await api(`/people/${$('person').value}/memories`,{text:$('memory-input').value});$('memory-input').value='';await loadMemories()})};
$('delete-person').onclick=()=>{if(confirm('Erase this profile, its memories, and its face template?'))guard(async()=>{await api(`/people/${$('person').value}`,undefined,'DELETE');state.selected=null;await loadPeople()})};
$('enroll').onclick=()=>{if(confirm('Does this person agree to local face recognition? Make sure only their face is visible. A face template will be saved on this device.'))guard(async()=>{await api(`/people/${$('person').value}/face`,{consent:true});notice('Face enrolled. Recognition is an estimate, not proof of identity.');await loadPeople()})};
$('forget-face').onclick=()=>guard(async()=>{await api(`/people/${$('person').value}/face`,undefined,'DELETE');notice('Face template removed.');await loadPeople()});
window.addEventListener('pagehide',()=>{stopRecording(true);stopPlayback()});
(async()=>{await guard(loadPeople);poll()})();
