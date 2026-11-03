import asyncio
import json
import pytest
import httpx
from fastapi.testclient import TestClient
from governor.app import create_app, Controller
from governor.config import Config
from governor.brain import Brain

HEADERS = {'X-Governor-Client': '1'}


def profile(client, name):
    return client.post('/api/people', json={'name': name, 'consent': True}).json()['id']


def test_demo_conversation_memory_and_forget(client):
    ident = profile(client, 'Sam')
    assert client.post('/api/select', json={'person_id': ident}).status_code == 200
    response = client.post('/api/turn', json={'text': 'remember that I love films'})
    assert response.status_code == 200
    assert client.get(f'/api/people/{ident}/memories').json()[0]['text'] == 'I love films'
    assert client.get('/api/people').json()[0]['turns'] == 1
    assert client.post('/api/playback/done', json={'turn_id': response.json()['turn_id']}).status_code == 200
    assert client.get('/api/state').json()['status'] == 'idle'
    assert client.delete(f'/api/people/{ident}').status_code == 200
    assert client.get('/api/state').json()['selected'] is None
    assert client.get('/api/people').json() == []


def test_first_turn_is_allowed_at_monotonic_clock_origin(client, monkeypatch):
    monkeypatch.setattr('governor.app.time.monotonic', lambda: 0.1)
    response = client.post('/api/turn', json={'text': 'Hello'})
    assert response.status_code == 200


def test_request_guard_consent_and_pause(client):
    assert client.post('/api/people', json={'name': 'A'}).status_code == 422
    assert client.post('/api/turn', json={'text': 'Hello'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/state', headers={'Host': 'evil.example'}).status_code == 400
    client.post('/api/power', json={'paused': True})
    assert client.post('/api/turn', json={'text': 'Hello'}).status_code == 409
    assert client.get('/').status_code == 200
    assert 'frame-ancestors' in client.get('/').headers['content-security-policy']


def test_no_cross_profile_context(client):
    a, b = profile(client, 'A'), profile(client, 'B')
    ctl = client.app.state.controller
    client.post('/api/select', json={'person_id': a})
    client.post('/api/turn', json={'text': 'My secret is purple'})
    assert ctl.history
    client.post('/api/select', json={'person_id': b})
    assert ctl.history == []
    assert ctl.caption == 'STANDING BY.'


async def test_pending_turn_invalidated_on_switch_and_busy_rejected(tmp_path):
    ctl = Controller(Config(data_dir=tmp_path))
    entered, finish = asyncio.Event(), asyncio.Event()
    async def slow_reply(*args):
        entered.set()
        await finish.wait()
        return {'text': 'Private response', 'emotion': 'happy'}
    ctl.brain.reply = slow_reply
    task = asyncio.create_task(ctl.turn(text='Private question'))
    await entered.wait()
    with pytest.raises(Exception) as busy:
        await ctl.turn(text='Another')
    assert busy.value.status_code == 409
    ctl.invalidate()
    finish.set()
    with pytest.raises(Exception) as cancelled:
        await task
    assert cancelled.value.status_code == 409
    assert not ctl.history
    assert ctl.caption == 'STANDING BY.'
    await ctl.brain.close()
    ctl.memory.close()


async def test_cloud_request_contract_and_secret_not_in_state(tmp_path):
    config = Config(provider='openai', api_key='test-secret', data_dir=tmp_path)
    brain = Brain(config)
    async def handler(request):
        assert request.headers['Authorization'] == 'Bearer test-secret'
        if request.url.path.endswith('/transcriptions'):
            assert b'gpt-transcribe' in request.content
            return httpx.Response(200, json={'text': ' Hello '})
        payload = json.loads(request.content)
        assert payload['store'] is False
        assert payload['text']['format']['type'] == 'json_schema'
        return httpx.Response(200, json={'output': [{'content': [{'type': 'output_text', 'text': '{"text":"Hello there","emotion":"happy"}'}]}]})
    await brain.http.aclose()
    brain.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert (await brain.reply('Hi', None, [], []))['text'] == 'Hello there'
    assert await brain.transcribe(b'audio', 'test.wav', 'audio/wav') == 'Hello'
    await brain.close()
    ctl = Controller(config)
    assert 'test-secret' not in json.dumps(ctl.state())
    await ctl.brain.close()
    ctl.memory.close()


async def test_provider_failure_recovers(tmp_path):
    ctl = Controller(Config(data_dir=tmp_path))
    async def fail(*args):
        raise httpx.ConnectError('network down')
    ctl.brain.reply = fail
    with pytest.raises(Exception) as error:
        await ctl.turn(text='Hello')
    assert error.value.status_code == 503
    assert ctl.status == 'idle'
    assert not ctl.lock.locked()
    assert ctl.history == []
    await ctl.brain.close()
    ctl.memory.close()


async def test_local_provider_uses_loopback_only(tmp_path):
    brain = Brain(Config(provider='local', data_dir=tmp_path))
    async def handler(request):
        assert request.url.host == '127.0.0.1'
        payload = json.loads(request.content)
        assert payload['stream'] is False
        return httpx.Response(200, json={'message': {'content': '{"text":"Greetings","emotion":"nonsense"}'}})
    await brain.http.aclose()
    brain.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await brain.reply('Hi', None, [], []) == {'text': 'Greetings', 'emotion': 'neutral'}
    await brain.close()
