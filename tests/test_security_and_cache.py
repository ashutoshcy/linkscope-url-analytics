from unittest.mock import patch
from app.core import cache
from tests.conftest import add_link


class FakeRedis:
    def __init__(self): self.values={};self.limits={}
    def get(self,key): return self.values.get(key)
    def setex(self,key,ttl,value): self.values[key]=value
    def delete(self,key): self.values.pop(key,None)
    def incr(self,key): self.limits[key]=self.limits.get(key,0)+1;return self.limits[key]
    def expire(self,key,ttl): pass


def test_redis_lookup_and_invalidation(signed_in, monkeypatch):
    c,csrf=signed_in
    fake=FakeRedis()
    monkeypatch.setattr(cache,'client',lambda:fake)
    l=add_link(c,csrf,slug='cache-flow').json()
    assert not fake.values
    for _ in range(2):
        assert c.get('/r/cache-flow',follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 Chrome/121'}).status_code==302
    assert 'linkscope:slug:cache-flow' in fake.values
    c.patch(f"/api/links/{l['id']}",json={'is_active':False},headers={'X-CSRF-Token':csrf})
    assert not fake.values
    assert c.get('/r/cache-flow',follow_redirects=False).status_code==410
    c.delete(f"/api/links/{l['id']}",headers={'X-CSRF-Token':csrf})
    assert not fake.values
    assert c.get('/r/cache-flow',follow_redirects=False).status_code==404


def test_distributed_auth_rate_limit(client,monkeypatch):
    fake=FakeRedis()
    monkeypatch.setattr(cache,'client',lambda:fake)
    for n in range(15):
        assert client.post('/api/auth/login',json={'email':'nobody@example.com','password':'bad'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'nobody@example.com','password':'bad'}).status_code==429


def test_production_requires_real_secret(monkeypatch):
    from app.main import create_app
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('SECRET_KEY','dev-only-insecure-replace-before-deployment')
    try:
        create_app('sqlite://')
    except RuntimeError as e:
        assert 'SECRET_KEY' in str(e)
    else: assert False, 'Expected startup guard'


def test_clean_name_rejected(client):
    r=client.post('/api/auth/register',json={'name':'  ','email':'test@example.com','password':'SafePassword123!'})
    assert r.status_code==422
