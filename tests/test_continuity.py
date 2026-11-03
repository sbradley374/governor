import asyncio
import json
import sqlite3

import httpx
import pytest

from governor.app import Controller
from governor.brain import Brain
from governor.config import Config
from governor.memory import Memory
from governor.room import ArrivalPolicy
from governor.wake import is_wake


def note(text, replace_id='', kind='preference'):
    return {'text': text, 'replace_id': replace_id, 'kind': kind}


def person(client, name='Sam'):
    return client.post('/api/people', json={'name': name, 'consent': True}).json()['id']


def test_existing_database_migrates_without_losing_facts(tmp_path):
    db = sqlite3.connect(tmp_path / 'governor.sqlite3')
    db.executescript("""
    CREATE TABLE people(id TEXT PRIMARY KEY,name TEXT,created TEXT,turns INTEGER DEFAULT 0,last_seen TEXT);
    CREATE TABLE facts(id TEXT PRIMARY KEY,person_id TEXT,text TEXT,created TEXT);
    INSERT INTO people(id,name,created) VALUES('p','Sam','2026');
    INSERT INTO facts VALUES('f','p','Likes CRTs','2026');
    """)
    db.close()
    store = Memory(tmp_path)
    assert store.person('p')['auto_memory'] == 0
    assert store.facts('p')[0]['source'] == 'explicit'
    store.remember('p', 'Another fact')
    store.close()
    store = Memory(tmp_path)
    assert len(store.facts('p')) == 2
    store.close()


def test_automatic_notes_require_opt_in_and_cannot_cross_owners_or_manual_edits(tmp_path):
    store = Memory(tmp_path)
    a, b = store.create('A')['id'], store.create('B')['id']
    payload = {'updates': [note('Likes jazz')], 'summary': 'Discussed music.'}
    store.absorb(a, 'session', payload)
    assert store.archive(a) == []
    store.automatic(a, True)
    store.absorb(a, 'session', payload)
    original = store.facts(a)[0]
    store.automatic(b, True)
    store.absorb(b, 'session', {'updates': [note('Corrupted', original['id'])], 'summary': 'B only'})
    assert not store.facts(b)
    assert store.facts(a)[0]['text'] == 'Likes jazz'
    store.absorb(a, 'session', {'updates': [note('Likes blues', original['id'])], 'summary': 'Corrected music preference.'})
    assert len(store.facts(a)) == 1
    assert store.facts(a)[0]['text'] == 'Likes blues'
    store.edit(a, original['id'], 'Likes soul music')
    store.absorb(a, 'session', {'updates': [note('Model overwrote me', original['id'])]})
    assert store.facts(a)[0]['text'] == 'Likes soul music'
    assert len(store.archive(a)) == 1  # Old summaries removed on manual correction.
    assert store.archive(b)[0]['text'] == 'B only'
    store.close()


def test_retrieval_is_relevant_bounded_and_persistent(tmp_path):
    store = Memory(tmp_path)
    a, b = store.create('A')['id'], store.create('B')['id']
    store.remember(a, 'Building a telescope observatory')
    for i in range(20):
        store.remember(a, f'Ordinary note {i}')
    store.remember(b, 'Secret telescope password')
    store.automatic(a, True)
    for i in range(35):
        store.absorb(a, str(i), {'summary': f'Discussed shared activity {i}', 'updates': []})
    store.close()
    store = Memory(tmp_path)
    selected = store.retrieve(a, 'How is the telescope going?')
    assert selected[0]['text'] == 'Building a telescope observatory'
    assert len(selected) == 10
    assert all(item['person_id'] == a for item in selected)
    assert len([f for f in store.archive(a) if f['kind'] == 'conversation']) == 30
    store.delete(a)
    assert store.archive(a) == []
    store.close()


def test_erase_disables_saving_and_forget_removes_summary_copies(client):
    ident = person(client)
    client.post('/api/select', json={'person_id': ident})
    client.post(f'/api/people/{ident}/automatic-memory', json={'enabled': True})
    reply = client.post('/api/turn', json={'text': 'I like jazz'})
    assert reply.status_code == 200
    archive = client.get(f'/api/people/{ident}/memories').json()
    assert {f['kind'] for f in archive} == {'preference', 'conversation'}
    fact = next(f for f in archive if f['kind'] == 'preference')
    client.delete(f'/api/people/{ident}/memories/{fact["id"]}')
    assert client.get(f'/api/people/{ident}/memories').json() == []
    assert client.app.state.controller.history == []
    client.delete(f'/api/people/{ident}/memories')
    assert client.get('/api/people').json()[0]['auto_memory'] == 0


def test_bad_memory_output_does_not_break_valid_notes(tmp_path):
    store = Memory(tmp_path)
    ident = store.create('A')['id']
    store.automatic(ident, True)
    store.absorb(ident, 's', {'updates': [note('x', kind={}), note('x' * 501), note('Good note')], 'summary': 42})
    assert [f['text'] for f in store.archive(ident)] == ['Good note']
    store.close()


async def test_pending_auto_save_is_cancelled_when_profile_changes(tmp_path):
    c = Controller(Config(data_dir=tmp_path))
    a, b = c.memory.create('A')['id'], c.memory.create('B')['id']
    c.memory.automatic(a, True)
    c.selected = a
    entered, finish = asyncio.Event(), asyncio.Event()
    async def reply(*args):
        entered.set()
        await finish.wait()
        return {'text': 'Hello', 'emotion': 'happy', 'memory': {'updates': [note('Private')], 'summary': 'Private'}}
    c.brain.reply = reply
    task = asyncio.create_task(c.turn(text='A private statement'))
    await entered.wait()
    c.selected = b
    c.invalidate()
    finish.set()
    with pytest.raises(Exception) as error:
        await task
    assert error.value.status_code == 409
    assert c.memory.archive(a) == c.memory.archive(b) == []
    await c.brain.close()
    c.memory.close()


async def test_cloud_memory_schema_shares_one_request(tmp_path):
    brain = Brain(Config(provider='openai', api_key='fake', data_dir=tmp_path))
    calls = []
    async def handler(request):
        payload = json.loads(request.content)
        calls.append(payload)
        schema = payload['text']['format']['schema']
        assert 'memory' in schema['required']
        assert payload['store'] is False
        assert payload['max_output_tokens'] == 1000
        return httpx.Response(200, json={'output': [{'content': [{'type': 'output_text', 'text': json.dumps({
            'text': 'How is the telescope going?', 'emotion': 'curious',
            'memory': {'updates': [note('Building a telescope', kind='project')], 'summary': 'Discussed a telescope.'}})}]}]})
    await brain.http.aclose()
    brain.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await brain.reply('I am building a telescope', {'name': 'A', 'auto_memory': 1}, [], [])
    assert result['memory']['updates'][0]['kind'] == 'project'
    assert len(calls) == 1
    await brain.close()


def test_wake_requires_exact_confident_phrase():
    assert is_wake({'text': 'hey governor', 'result': [{'conf': .9}, {'conf': .9}]})
    assert not is_wake({'text': 'governor', 'result': [{'conf': .4}]})
    assert not is_wake({'text': 'the governor called', 'result': [{'conf': 1}]})
    assert not is_wake({'text': 'governor'})


def test_arrivals_are_debounced_cooldown_limited_and_rearm_after_departure():
    policy = ArrivalPolicy()
    present = {'status': 'running', 'face_count': 1, 'present': ['sam']}
    absent = {'status': 'running', 'face_count': 0, 'present': []}
    assert not policy.observe(present, 0)
    assert policy.observe(present, 3)
    assert not policy.observe(present, 1000)
    assert not policy.observe(absent, 1005)
    assert not policy.observe(present, 1006)  # Brief camera dropout.
    policy.observe(absent, 1022)
    assert not policy.observe(present, 1023)
    assert policy.observe(present, 1026)
    policy.observe(absent, 1042)
    policy.observe(present, 1043)
    assert not policy.observe(present, 1046)  # Return inside cooldown.
    assert not policy.observe(present, 2000)  # No delayed interruption.


def test_paused_arrival_does_not_greet_on_resume():
    policy = ArrivalPolicy()
    room = {'status': 'running', 'face_count': 2, 'present': []}
    policy.observe(room, 0, allowed=False)
    policy.observe(room, 3, allowed=False)
    assert not policy.observe(room, 100, allowed=True)


def test_wake_clears_previous_speaker_and_window_expires(client, monkeypatch):
    c = client.app.state.controller
    ident = person(client)
    client.post('/api/select', json={'person_id': ident})
    session = c.session_id
    activated = client.post('/api/activate', json={'session_id': session}).json()
    assert activated['selected'] is None and activated['awake']
    assert activated['session_id'] != session
    assert client.post('/api/activate', json={'session_id': session}).status_code == 409
    c.selected = ident
    c.listen_until = 0
    expired = client.get('/api/state').json()
    assert expired['selected'] is None and not expired['awake']
    client.post('/api/power', json={'paused': True})
    assert client.post('/api/activate', json={'session_id': c.session_id}).status_code == 409


def test_spoken_introduction_selects_unique_profile_without_camera_guess(client):
    ident = person(client)
    response = client.post('/api/turn', json={'text': 'This is Sam'})
    assert response.status_code == 200
    assert client.get('/api/state').json()['selected'] == ident
    assert response.json()['session_id'] == client.get('/api/state').json()['session_id']


def test_room_greeting_does_not_read_or_write_personal_memories(client, monkeypatch):
    c = client.app.state.controller
    ident = person(client)
    c.memory.remember(ident, 'Secret personal details')
    c.selected = ident
    c.interaction.greetings = True
    c.last_activity = -100
    c.camera.snapshot = lambda: {'status': 'running', 'face_count': 1, 'present': [ident]}
    clock = [100.0]
    monkeypatch.setattr('governor.app.time.monotonic', lambda: clock[0])
    assert client.post('/api/room/check').json()['greeting'] is None
    clock[0] = 104
    result = client.post('/api/room/check').json()['greeting']
    assert 'Sam' in result['text'] and 'Secret' not in result['text']
    assert c.selected is None and c.history == []
    assert c.memory.person(ident)['turns'] == 0
    assert client.post('/api/room/check').json()['greeting'] is None
    client.post('/api/playback/done', json={'turn_id': result['turn_id']})
    assert client.get('/api/state').json()['awake']


def test_rehearsal_and_room_preferences_without_hardware(client):
    response = client.post('/api/interaction', json={'greetings': True, 'followup_seconds': 30, 'greeting_cooldown': 900})
    assert response.status_code == 200
    assert client.app.state.controller.memory.setting('interaction')['greetings']
    assert client.post('/api/interaction', json={'followup_seconds': 600}).status_code == 422
    result = client.post('/api/room/rehearse', json={})
    assert result.status_code == 200
    assert client.app.state.controller.history == []


def test_speech_start_reserves_full_utterance_without_unbounded_extension(client, monkeypatch):
    c = client.app.state.controller
    clock = [100.0]
    monkeypatch.setattr('governor.app.time.monotonic', lambda: clock[0])
    session = client.post('/api/activate', json={'session_id': c.session_id}).json()['session_id']
    clock[0] = 119
    assert client.post('/api/capture', json={'session_id': session}).status_code == 200
    assert c.listen_until == 154
    clock[0] = 140
    assert client.get('/api/state').json()['awake']
    client.post('/api/capture', json={'session_id': session})
    assert c.listen_until == 154
    clock[0] = 155
    assert client.post('/api/capture', json={'session_id': session}).status_code == 409


def test_corrected_summary_becomes_manual_note(tmp_path):
    store = Memory(tmp_path)
    ident = store.create('Sam')['id']
    store.automatic(ident, True)
    store.absorb(ident, 's', {'summary': 'We discussed jazz.', 'updates': []})
    store.edit(ident, ident + ':s', 'We discussed soul music.')
    assert store.summary(ident, 's') == ''
    assert store.facts(ident)[0]['source'] == 'explicit'
    store.absorb(ident, 's', {'summary': 'New discussion', 'updates': []})
    assert store.facts(ident)[0]['text'] == 'We discussed soul music.'
    store.close()


def test_console_selection_preserves_an_active_native_reply_window(client):
    ident = person(client)
    c = client.app.state.controller
    client.post('/api/activate', json={'session_id': c.session_id})
    selected = client.post('/api/select', json={'person_id': ident}).json()
    assert selected['selected'] == ident and selected['awake']
    assert c.audio_session


def test_unknown_introduction_cannot_continue_the_previous_persons_archive(client):
    ident = person(client)
    client.post('/api/select', json={'person_id': ident})
    response = client.post('/api/turn', json={'text': 'This is Someone Else'})
    assert response.status_code == 200
    c = client.app.state.controller
    assert c.selected is None
    assert c.memory.person(ident)['turns'] == 0
    assert c.memory.archive(ident) == []
