from datetime import datetime, timedelta, timezone
from tests.conftest import add_link


def test_create_list_get_and_update(signed_in):
    c,csrf=signed_in
    r=add_link(c,csrf,slug='my-landing',tags='Marketing')
    assert r.status_code==201,r.text
    link=r.json();assert link['slug']=='my-landing'
    assert '/r/my-landing' in link['short_url']
    assert c.get('/api/links').json()['total']==1
    assert c.get('/api/links/'+str(link['id'])).json()['title']=='My campaign'
    r=c.patch(f"/api/links/{link['id']}",json={'title':'Retitled','description':'A note'},headers={'X-CSRF-Token':csrf})
    assert r.status_code==200 and r.json()['title']=='Retitled'


def test_duplicate_slug_conflict(signed_in):
    c,csrf=signed_in
    assert add_link(c,csrf,slug='shared-slug').status_code==201
    assert add_link(c,csrf,slug='shared-slug').status_code==409


def test_random_slug(signed_in):
    c,csrf=signed_in
    r=add_link(c,csrf)
    assert r.status_code==201 and len(r.json()['slug'])==7


def test_validate_urls(signed_in):
    c,csrf=signed_in
    bad=['javascript:alert(1)','file:///etc/passwd','http://localhost:8000/private','http://127.0.0.1','http://192.168.1.1','https://user:pass@example.com','https://bad url.com','ftp://example.com','https://test.local','http://[::1]']
    for url in bad:
        r=add_link(c,csrf,target_url=url)
        assert r.status_code==422,(url,r.text)


def test_slug_validation_and_expiry(signed_in):
    c,csrf=signed_in
    for slug in ['api','!', 'x'*33, 'ab']:
        assert add_link(c,csrf,slug=slug).status_code==422
    past=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    assert add_link(c,csrf,expires_at=past).status_code==422


def test_redirect_click_count_and_uniques(signed_in):
    c,csrf=signed_in
    link=add_link(c,csrf,slug='clicked-once').json()
    for i in range(3):
        r=c.get('/r/clicked-once',follow_redirects=False,headers={'User-Agent':'Mozilla/5.0 Chrome/121.0.0.0','Referer':'https://news.example.com/article'})
        assert r.status_code==302 and r.headers['location']=='https://example.com/abc'
    stats=c.get(f"/api/analytics/links/{link['id']}").json()
    assert stats['total_clicks']==3 and stats['unique_visitors']==1
    assert stats['referrers'][0]['name']=='news.example.com'
    assert c.get('/api/links/'+str(link['id'])).json()['click_count']==3


def test_bot_excluded(signed_in):
    c,csrf=signed_in
    l=add_link(c,csrf,slug='notabot').json()
    r=c.get('/r/notabot',follow_redirects=False,headers={'User-Agent':'Googlebot'})
    assert r.status_code==302
    assert c.get('/api/links/'+str(l['id'])).json()['click_count']==0
    assert c.get(f"/api/analytics/links/{l['id']}").json()['total_clicks']==0


def test_pause_resume_and_expiration(signed_in):
    c,csrf=signed_in
    l=add_link(c,csrf).json();id=l['id']
    assert c.patch(f'/api/links/{id}',json={'is_active':False},headers={'X-CSRF-Token':csrf}).status_code==200
    assert c.get('/r/'+l['slug'],follow_redirects=False).status_code==410
    assert c.patch(f'/api/links/{id}',json={'is_active':True},headers={'X-CSRF-Token':csrf}).json()['status']=='active'
    assert c.get('/r/'+l['slug'],follow_redirects=False).status_code==302


def test_delete_removes_redirect(signed_in):
    c,csrf=signed_in
    l=add_link(c,csrf).json()
    assert c.delete(f"/api/links/{l['id']}",headers={'X-CSRF-Token':csrf}).status_code==204
    assert c.get('/r/'+l['slug'],follow_redirects=False).status_code==404
    assert c.get('/api/links/'+str(l['id'])).status_code==404


def test_filter_search_sort_pagination(signed_in):
    c,csrf=signed_in
    for i in range(5):add_link(c,csrf,title='Alpha' if i%2 else 'Beta',slug=f'alias-{i}')
    assert c.get('/api/links?q=Alpha').json()['total']==2
    assert c.get('/api/links?limit=2&offset=2').json()['total']==5
    assert len(c.get('/api/links?limit=2&offset=2').json()['items'])==2
    assert c.get('/api/links?sort=title').json()['items'][0]['title']=='Alpha'
    assert c.get('/api/links?status=expired').json()['total']==0
    assert c.get('/api/links?limit=10000').status_code==422


def test_qr_png(signed_in):
    c,csrf=signed_in
    id=add_link(c,csrf).json()['id']
    r=c.get(f'/api/links/{id}/qr')
    assert r.status_code==200 and r.headers['content-type']=='image/png' and r.content[:8]==b'\x89PNG\r\n\x1a\n'


def test_data_isolation(client):
    r=client.post('/api/auth/register',json={'name':'First','email':'first@example.com','password':'Password1234!'})
    csrf1=r.json()['csrf_token']
    one=add_link(client,csrf1).json()
    client.post('/api/auth/logout',headers={'X-CSRF-Token':csrf1})
    r=client.post('/api/auth/register',json={'name':'Second','email':'second@example.com','password':'Password1234!'})
    csrf2=r.json()['csrf_token']
    assert client.get('/api/links').json()['total']==0
    assert client.get('/api/links/'+str(one['id'])).status_code==404
    assert client.get('/api/analytics/links/'+str(one['id'])).status_code==404
    assert client.get('/api/links/'+str(one['id'])+'/qr').status_code==404
    assert client.patch('/api/links/'+str(one['id']),json={'title':'Mine'},headers={'X-CSRF-Token':csrf2}).status_code==404
    assert client.delete('/api/links/'+str(one['id']),headers={'X-CSRF-Token':csrf2}).status_code==404


def test_null_target_rejected(signed_in):
    c,csrf=signed_in
    id=add_link(c,csrf).json()['id']
    assert c.patch(f'/api/links/{id}',json={'target_url':None},headers={'X-CSRF-Token':csrf}).status_code==422


def test_missing_link(signed_in):
    c,csrf=signed_in
    assert c.get('/api/links/998800').status_code==404
    assert c.get('/r/unknown-alias',follow_redirects=False).status_code==404
