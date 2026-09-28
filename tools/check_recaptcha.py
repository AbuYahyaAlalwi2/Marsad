"""check_recaptcha.py — فحص حالة reCAPTCHA في Chrome النشط."""
import asyncio, httpx, json, websockets


async def main():
    r = httpx.get('http://localhost:9222/json', timeout=10)
    pages = [t for t in r.json() if t.get('type') == 'page']
    target = next((p for p in pages if 'recaptcha' in p.get('url', '')),
                  pages[0] if pages else None)
    if not target:
        print('no page')
        return
    print('Tab:', target['url'])
    ws = await websockets.connect(target['webSocketDebuggerUrl'],
                                   max_size=50*1024*1024)
    mid = 0
    async def cmd(method, params=None):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({'id': mid, 'method': method,
                                  'params': params or {}}))
        while True:
            d = json.loads(await ws.recv())
            if d.get('id') == mid:
                return d.get('result', {})
    js = '''
    (function(){
        var out = {url: location.href, title: document.title};
        var a = document.querySelector('iframe[src*="api2/anchor"]');
        out.anchor = !!a;
        if (a && a.contentDocument) {
            var cb = a.contentDocument.querySelector('.recaptcha-checkbox');
            out.checked = cb ? cb.classList.contains('recaptcha-checkbox-checked') : null;
        }
        var b = document.querySelector('iframe[src*="api2/bframe"]');
        out.bframe = !!b;
        if (b) out.bframe_vis = b.style.visibility || 'unknown';
        return JSON.stringify(out);
    })()
    '''
    r1 = await cmd('Runtime.evaluate',
                   {'expression': js, 'returnByValue': True})
    print('State:', r1.get('result', {}).get('value'))
    await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
