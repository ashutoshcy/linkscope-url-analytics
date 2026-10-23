from tests.conftest import add_link


def test_health_and_home(client):
    assert client.get('/api/health').json()['status']=='ok'
    assert '<title>Linkscope' in client.get('/').text
    assert client.get('/static/styles.css').status_code==200


def test_registration_sets_httponly_cookie(client):
    r=client.post('/api/auth/register',json={'name':'Alex','email':'alex@example.com','password':'SecurePassword123!'})
    assert r.status_code==201
    assert 'httponly' in r.headers['set-cookie'].lower()
    assert r.json()['user']['email']=='alex@example.com'
    assert client.get('/api/auth/me').status_code==200


def test_password_length_and_bad_email(client):
    for email,password in [('not-email','SecurePassword123!'),('test@example.com','short')]:
        assert client.post('/api/auth/register',json={'name':'Alex','email':email,'password':password}).status_code==422


def test_duplicate_registration(signed_in):
    c,_=signed_in
    assert c.post('/api/auth/register',json={'name':'Test','email':'PERSON@EXAMPLE.COM','password':'SecurePassword123!'}).status_code==409


def test_login_logout_and_invalid_password(client,signed_in):
    c,csrf=signed_in
    assert c.post('/api/auth/login',json={'email':'person@example.com','password':'wrong'}).status_code==401
    assert c.post('/api/auth/logout',headers={'X-CSRF-Token':csrf}).status_code==200
    assert c.get('/api/auth/me').status_code==401
    assert c.post('/api/auth/login',json={'email':'person@example.com','password':'SafePassword123!'}).status_code==200
    assert c.get('/api/auth/me').status_code==200


def test_auth_and_csrf_enforced(client,signed_in):
    c,csrf=signed_in
    assert c.post('/api/links',json={'target_url':'https://example.com','title':'Bad CSRF'}).status_code==403
    c.cookies.clear()
    assert c.get('/api/links').status_code==401


def test_origin_validation(client):
    data={'name':'Alex','email':'alex@example.com','password':'SecurePassword123!'}
    assert client.post('/api/auth/register',json=data,headers={'origin':'https://attacker.example'}).status_code==403
