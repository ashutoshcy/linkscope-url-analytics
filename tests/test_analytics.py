from tests.conftest import add_link


def test_analytics_empty(signed_in):
    c,csrf=signed_in
    stats=c.get('/api/analytics/overview').json()
    assert len(stats['series'])==14 and stats['total_links']==0
    assert stats['total_clicks']==0


def test_overview_utm_campaign_and_export(signed_in):
    c,csrf=signed_in
    l=add_link(c,csrf,slug='utm-test').json()
    c.get('/r/utm-test?utm_campaign=october&utm_source=email&utm_medium=newsletter',follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 Chrome/120 Safari/537.36'})
    stats=c.get('/api/analytics/overview?days=7').json()
    assert stats['total_links']==1 and stats['all_time_clicks']==1
    assert stats['campaigns'][0]['name']=='october'
    r=c.get('/api/analytics/export.csv?days=7')
    assert r.status_code==200 and 'october' in r.text and 'utm_source' in r.text
    assert r.headers['content-type'].startswith('text/csv')


def test_date_window_validation(signed_in):
    c,csrf=signed_in
    assert c.get('/api/analytics/overview?days=5').status_code==422
    assert c.get('/api/analytics/overview?days=100').status_code==422


def test_no_raw_ip_exposed(signed_in):
    c,csrf=signed_in
    add_link(c,csrf,slug='ip-test')
    c.get('/r/ip-test',follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 Chrome/121'})
    assert '127.0.0.1' not in c.get('/api/analytics/export.csv').text


def test_csv_only_own_clicks(client):
    one=client.post('/api/auth/register',json={'name':'One','email':'one@example.com','password':'Password1234!'}).json()
    add_link(client,one['csrf_token'],slug='one-csv')
    client.get('/r/one-csv',follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 Chrome/121'})
    client.post('/api/auth/logout',headers={'X-CSRF-Token':one['csrf_token']})
    client.post('/api/auth/register',json={'name':'Two','email':'two@example.com','password':'Password1234!'})
    assert 'one-csv' not in client.get('/api/analytics/export.csv').text


def test_csv_formula_injection_is_escaped(signed_in):
    c,csrf=signed_in
    add_link(c,csrf,slug='formula-test',title='=2+2')
    c.get('/r/formula-test?utm_campaign=%3DIMPORTXML%28%22attack%22%29',follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 Chrome/123'})
    exported=c.get('/api/analytics/export.csv').text
    assert "'=2+2" in exported
    assert "'=IMPORTXML" in exported


def test_expiry_can_be_cleared_by_update(signed_in):
    from datetime import datetime, timedelta, timezone
    c,csrf=signed_in
    expiry=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()
    l=add_link(c,csrf,expires_at=expiry).json()
    assert l['expires_at']
    r=c.patch(f"/api/links/{l['id']}",json={'expires_at':None},headers={'X-CSRF-Token':csrf})
    assert r.status_code==200 and r.json()['expires_at'] is None
