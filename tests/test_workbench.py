import json
import pytest
import httpx
from fastapi.testclient import TestClient
from governor.app import create_app
from governor.config import Config
from governor.demo import reply

HEADERS = {'X-Governor-Client': '1'}


def test_display_settings_survive_restart_and_reject_bad_values(tmp_path):
    config = Config(data_dir=tmp_path)
    settings = {'palette': 'amber', 'brightness': .5, 'inset': .12, 'idle_seconds': 60}
    with TestClient(create_app(config), headers=HEADERS) as client:
        assert client.post('/api/display', json=settings).status_code == 200
        assert client.post('/api/display', json={**settings, 'brightness': 4}).status_code == 422
        assert client.post('/api/display', json={**settings, 'palette': '<script>'}).status_code == 422
    with TestClient(create_app(config), headers=HEADERS) as client:
        assert client.get('/api/state').json()['display'] == settings


def test_preview_expires_and_does_not_replace_conversation(client, monkeypatch):
    monkeypatch.setattr('governor.app.time.monotonic', lambda: 100)
    original = client.get('/api/state').json()['caption']
    response = client.post('/api/preview', json={'emotion': 'surprised'})
    assert response.json()['preview'] == 'surprised'
    assert response.json()['caption'] == original
    assert client.app.state.controller.history == []
    monkeypatch.setattr('governor.app.time.monotonic', lambda: 109)
    assert client.get('/api/state').json()['preview'] is None
    client.post('/api/power', json={'paused': True})
    assert client.post('/api/preview', json={'emotion': 'happy'}).status_code == 409


def test_idle_dimming_and_wake(client, monkeypatch):
    ctl = client.app.state.controller
    ctl.last_activity = 100
    monkeypatch.setattr('governor.app.time.monotonic', lambda: 221)
    assert client.get('/api/state').json()['dimmed'] is True
    client.post('/api/wake', json={})
    assert client.get('/api/state').json()['dimmed'] is False


def test_old_recording_rejected_before_transcription(client):
    old_session = client.get('/api/state').json()['session_id']
    client.post('/api/select', json={'person_id': None})
    async def forbidden(*args):
        pytest.fail('A stale recording must never reach the transcription provider')
    client.app.state.controller.brain.transcribe = forbidden
    response = client.post('/api/audio', data={'session_id': old_session}, files={'file': ('speech.wav', b'audio', 'audio/wav')})
    assert response.status_code == 409
    assert client.app.state.controller.history == []
    assert client.post('/api/turn', json={'text': 'Hello', 'session_id': old_session}).status_code == 409


def test_setup_has_no_key_or_private_memories_and_never_opens_camera(client):
    ctl = client.app.state.controller
    ctl.config.api_key = 'never-show-this-secret'
    person = ctl.memory.create('Private Name')
    ctl.memory.remember(person['id'], 'Private fact')
    result = client.get('/api/setup')
    assert result.status_code == 200
    text = result.text
    assert all(value not in text for value in ['never-show-this-secret', 'Private Name', 'Private fact'])
    assert ctl.camera.thread is None


def test_voice_check_does_not_call_llm_or_change_relationship(client):
    ctl = client.app.state.controller
    person = ctl.memory.create('Sam')
    client.post('/api/select', json={'person_id': person['id']})
    async def forbidden(*args):
        pytest.fail('Hardware voice tests must not call the LLM')
    ctl.brain.reply = forbidden
    ctl.config.provider = 'openai'
    result = client.post('/api/test-voice', json={'session_id': ctl.session_id})
    assert result.status_code == 200
    assert 'local speaker test' in result.json()['text']
    assert ctl.memory.person(person['id'])['turns'] == 0
    assert ctl.history == []


async def test_demo_never_requests_network(tmp_path):
    from governor.brain import Brain
    brain = Brain(Config(data_dir=tmp_path))
    async def forbidden(request):
        pytest.fail('Demo must not make network requests')
    await brain.http.aclose()
    brain.http = httpx.AsyncClient(transport=httpx.MockTransport(forbidden))
    for text in ['hello', 'tell me a joke', 'who are you?', 'wow', 'I am tired', 'how does this work?', 'bye']:
        result = await brain.reply(text, None, [], [])
        assert result['text'].endswith('[Demo mode]')
    await brain.close()


def test_demo_memory_is_bounded_and_does_not_invent_facts():
    facts = [{'text': 'x' * 500}] * 50
    assert len(reply('what do you remember?', None, facts, [])['text']) < 1200
    result = reply('what do you remember?', None, [], [])
    assert 'Nothing on file yet' in result['text']
