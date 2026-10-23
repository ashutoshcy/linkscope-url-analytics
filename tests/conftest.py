import os
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('SECRET_KEY','a-testing-secret-with-at-least-32-characters')
    app = create_app(f"sqlite:///{tmp_path/'test.db'}")
    with TestClient(app) as c:
        yield c

@pytest.fixture
def signed_in(client):
    r=client.post('/api/auth/register',json={'name':'Test User','email':'person@example.com','password':'SafePassword123!'})
    assert r.status_code==201,r.text
    return client,r.json()['csrf_token']

@pytest.fixture
def second_user(client):
    r=client.post('/api/auth/register',json={'name':'Second User','email':'other@example.com','password':'SafePassword123!'})
    assert r.status_code==201
    return client,r.json()['csrf_token']


def add_link(client,csrf, **changes):
    payload={'target_url':'https://example.com/abc','title':'My campaign',**changes}
    return client.post('/api/links',json=payload,headers={'X-CSRF-Token':csrf})
