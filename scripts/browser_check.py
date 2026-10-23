"""Browser smoke test against real FastAPI endpoints through an ASGI bridge.

Requires `pip install playwright` and a Chromium installation. No external network.
"""
import os
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from app.main import create_app

SHOTS = Path(__file__).parent.parent / 'docs' / 'screenshots'
SHOTS.mkdir(exist_ok=True,parents=True)

def _run_browser(db_url):
    errors=[]
    with TestClient(create_app(db_url)) as test_client, sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.getenv('CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome') or None, args=['--no-sandbox'])
        context=browser.new_context(viewport={'width':1440,'height':900},device_scale_factor=1)
        # Some sandboxed browsers block navigation to all HTTP endpoints.
        # Render the real HTML/CSS/JS in Chromium and forward fetch calls to
        # FastAPI's actual TestClient. No endpoint or response is mocked.
        from app.main import STATIC
        import json
        def bridge(_, url, options):
            u=urlsplit(url)
            path=(u.path or '/')+('?' + u.query if u.query else '')
            headers={k:v for k,v in (options.get('headers') or {}).items()}
            if options.get('body') is not None:
                response=test_client.request(options.get('method','GET'),path,content=options['body'].encode(),headers=headers,follow_redirects=False)
            else:
                response=test_client.request(options.get('method','GET'),path,headers=headers,follow_redirects=False)
            return {'status':response.status_code,'body':response.text,'contentType':response.headers.get('content-type','application/json')}
        page=context.new_page()
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_default_timeout(6500)
        page.expose_binding('__bridgeApi',bridge)
        html=(STATIC/'index.html').read_text()
        css=(STATIC/'styles.css').read_text()
        css=css[css.index(':root'):]  # avoid remote font import in offline sandbox
        js=(STATIC/'app.js').read_text()
        page.goto('about:blank')
        page.set_content(html.replace('<link rel="stylesheet" href="/static/styles.css" />','').replace('<script src="/static/app.js" defer></script>',''))
        page.add_style_tag(content=css)
        page.evaluate('''window.fetch=async function(path, options={}) {const r=await window.__bridgeApi(String(path),options);return new Response([204,205,304].includes(r.status)?null:r.body,{status:r.status,headers:{'content-type':r.contentType}})}''')
        page.add_script_tag(content=js)
        assert page.locator('#authView').is_visible(), 'Expected login screen'
        page.screenshot(path=str(SHOTS/'sign-in-desktop.png'),full_page=True)
        page.locator('#demoLogin').click()
        page.get_by_text('Good',exact=False).first.wait_for(timeout=20000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(SHOTS/'dashboard-desktop.png'),full_page=True)
        assert page.get_by_text('Summer campaign launch').first.is_visible()
        page.locator('[data-page="analytics"]').first.click()
        assert page.get_by_text('Your analytics').first.is_visible()
        page.screenshot(path=str(SHOTS/'analytics-desktop.png'),full_page=True)
        page.locator('[data-page="links"]').first.click()
        assert page.get_by_text('My links').first.is_visible()
        page.locator('[data-action="new-link"]').first.click()
        page.locator('#linkTarget').fill('https://example.com/new-feature')
        page.locator('#linkTitle').fill('Browser integration example')
        page.locator('#linkSlug').fill('browser-example')
        page.locator('#linkTags').fill('QA')
        page.screenshot(path=str(SHOTS/'create-link-modal.png'),full_page=True)
        page.locator('#linkForm button[type="submit"]').click()
        page.get_by_text('Browser integration example').first.wait_for(timeout=12000)
        assert page.locator('#drawerLayer').is_visible()
        assert page.locator('#drawerContent img').first.is_visible()
        page.locator('#drawerContent [data-action="close-drawer"]').click()
        page.locator('#linkSearch').fill('Browser integration example')
        page.wait_for_timeout(800)
        assert page.get_by_text('Browser integration example').first.is_visible()
        page.locator('tbody [data-action="edit"]').first.click()
        page.locator('#linkTitle').fill('Updated from Chromium')
        page.locator('#linkForm button[type="submit"]').click()
        page.get_by_text('Updated from Chromium').first.wait_for(timeout=12000)
        page.locator('#linkSearch').fill('Updated from Chromium')
        page.wait_for_timeout(700)
        assert page.get_by_text('Updated from Chromium').first.is_visible()
        page.locator('tbody [data-action="details"]').first.click()
        page.get_by_text('Updated from Chromium').first.wait_for(timeout=10000)
        page.on('dialog',lambda d:d.accept())
        page.locator('#drawerContent [data-action="delete"]').click()
        page.wait_for_timeout(900)
        page.locator('#pageContent tbody tr').filter(has_text='Updated from Chromium').wait_for(state='detached', timeout=10000)
        page.locator('[data-page="overview"]').first.click()
        page.wait_for_timeout(600)
        page.set_viewport_size({'width':390,'height':844})
        page.wait_for_timeout(350)
        page.wait_for_timeout(4800)  # let transient confirmation toasts clear before screenshot
        page.screenshot(path=str(SHOTS/'dashboard-mobile.png'),full_page=True)
        page.locator('#openNav').click()
        assert page.locator('#sidebar').evaluate('(el)=>el.classList.contains("open")')
        page.locator('[data-page="links"]').first.click()
        assert not page.locator('#sidebar').evaluate('(el)=>el.classList.contains("open")')
        page.screenshot(path=str(SHOTS/'links-mobile.png'),full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'), 'Horizontal mobile overflow'
        page.locator('#openNav').click()
        page.locator('#logoutBtn').click()
        page.locator('#authView').wait_for()
        assert not errors, errors
        browser.close()
    return 'Browser flows passed: login, overview, analytics, create, search, edit, QR, delete, mobile nav, responsive overflow, logout.'

def run():
    with tempfile.TemporaryDirectory(prefix='linkscope-browser-') as temp:
        db_url='sqlite:///'+str(Path(temp)/'browser.db')
        old=os.environ.get('DATABASE_URL')
        os.environ['DATABASE_URL']=db_url
        try:
            from scripts.seed_demo import run as seed_demo
            seed_demo()
            return _run_browser(db_url)
        finally:
            if old is None: os.environ.pop('DATABASE_URL',None)
            else: os.environ['DATABASE_URL']=old

if __name__=='__main__': print(run())
