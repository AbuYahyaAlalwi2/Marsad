"""real_click.py — نقرة حقيقية على checkbox reCAPTCHA عبر Input.dispatchMouseEvent."""
import asyncio, httpx, json, websockets


async def main():
    r = httpx.get('http://localhost:9222/json', timeout=10)
    pages = [t for t in r.json() if t.get('type')=='page'
             and 'recaptcha' in t.get('url','')]
    if not pages:
        print('no tab'); return
    ws = await websockets.connect(pages[0]['webSocketDebuggerUrl'],
                                   max_size=50*1024*1024)
    mid = 0
    async def cmd(m, p=None):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({'id': mid, 'method': m, 'params': p or {}}))
        while True:
            d = json.loads(await ws.recv())
            if d.get('id') == mid:
                return d.get('result', {})

    # احصل على إحداثيات checkbox في الصفحة الأم (وليس iframe)
    r1 = await cmd('Runtime.evaluate', {
        'expression': '''JSON.stringify(
            (function(){
                var f = document.querySelector('iframe[src*="api2/anchor"]');
                if (!f) return null;
                var rect = f.getBoundingClientRect();
                return {
                    x: rect.x,
                    y: rect.y,
                    w: rect.width,
                    h: rect.height,
                    // checkbox في الـ iframe عند ~30px من اليسار، ~28px من الأعلى
                    cx: rect.x + 30,
                    cy: rect.y + rect.height / 2,
                };
            })()
        )''',
        'returnByValue': True})
    info = json.loads(r1['result']['value'])
    print(f'[+] anchor frame: {info}')
    if not info:
        await ws.close(); return

    # نقرة حقيقية عبر CDP
    print(f'[+] dispatching real click at ({info["cx"]:.0f}, {info["cy"]:.0f})')
    await cmd('Input.dispatchMouseEvent', {
        'type': 'mouseMoved',
        'x': info['cx'],
        'y': info['cy'],
        'button': 'none',
    })
    await asyncio.sleep(0.1)
    await cmd('Input.dispatchMouseEvent', {
        'type': 'mousePressed',
        'x': info['cx'],
        'y': info['cy'],
        'button': 'left',
        'clickCount': 1,
    })
    await asyncio.sleep(0.05)
    await cmd('Input.dispatchMouseEvent', {
        'type': 'mouseReleased',
        'x': info['cx'],
        'y': info['cy'],
        'button': 'left',
        'clickCount': 1,
    })

    # انتظر طويلاً — Google قد يستغرق 30 ثانية للقرار
    print('[+] waiting up to 60s for challenge...')
    for i in range(20):
        await asyncio.sleep(3)
        # افحص حجم bframe
        doc = await cmd('DOM.getDocument', {'depth': -1, 'pierce': True})
        bframe_id = None
        async def walk(n):
            nonlocal bframe_id
            if bframe_id: return
            if n.get('nodeName') == 'IFRAME':
                al = n.get('attributes', [])
                attrs = {al[i]: al[i+1] for i in range(0, len(al), 2)}
                if 'api2/bframe' in attrs.get('src', ''):
                    bframe_id = n['frameId']; return
            for c in n.get('children', []):
                await walk(c)
        await walk(doc['root'])
        if not bframe_id:
            continue
        world = await cmd('Page.createIsolatedWorld',
                          {'frameId': bframe_id, 'worldName': f'w{i}'})
        ctx = world['executionContextId']
        r2 = await cmd('Runtime.evaluate', {
            'expression': '''JSON.stringify({
                btns: document.querySelectorAll('button').length,
                bodyLen: document.body ? document.body.innerHTML.length : 0,
            })''',
            'returnByValue': True, 'contextId': ctx})
        state = json.loads(r2['result']['value'])
        print(f'  [{(i+1)*3}s] buttons={state["btns"]} bodyLen={state["bodyLen"]}')
        if state['btns'] > 0:
            print('[✓] challenge appeared!')
            break

    # استخرج رابط الصوت إن وُجد
    if bframe_id:
        world = await cmd('Page.createIsolatedWorld',
                          {'frameId': bframe_id, 'worldName': 'final'})
        ctx = world['executionContextId']
        r3 = await cmd('Runtime.evaluate', {
            'expression': '''(function(){
                var b = document.getElementById('recaptcha-audio-button');
                if (b) { b.click(); return 'audio-clicked'; }
                return 'no-audio-btn';
            })()''',
            'returnByValue': True, 'contextId': ctx})
        print(f'[+] audio button: {r3["result"]["value"]}')
        await asyncio.sleep(4)
        r4 = await cmd('Runtime.evaluate', {
            'expression': "(document.getElementById('audio-source')||{}).src || 'none'",
            'returnByValue': True, 'contextId': ctx})
        url = r4['result']['value']
        print(f'[+] audio url: {url}')
        if url and url.startswith('http'):
            with open('/tmp/recaptcha_url.txt', 'w') as f:
                f.write(url)
            print('[✓] saved')

    await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
