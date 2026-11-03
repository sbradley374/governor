import pytest
from fastapi.testclient import TestClient
from governor.app import create_app
from governor.config import Config


@pytest.fixture
def client(tmp_path):
    app = create_app(Config(data_dir=tmp_path))
    with TestClient(app, headers={'X-Governor-Client': '1'}) as client:
        async def no_speech(text):
            return None
        app.state.controller.brain.speech = no_speech
        yield client
