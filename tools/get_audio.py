"""get_audio.py — يطابق context بـ frameId مباشرة."""
import asyncio, httpx, json, websockets


async def main():
    r = httpx.get('http://localhost:9222/json', timeout=10)
    pages = [t for t in r.json() if t.get('type')=='page' and 'recaptcha' in t.get('url','')]
    if not pages:
        print('no tab'); return
    ws = await websockets.connect(pages[0]['webSocketDebuggerUrl'], max_size=50*1024*1024)
    mid = 0
    contexts = {}

    async def cmd(method, params=None):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        while True:
            d = json.loads(await ws.recv())
            if d.get('method') == 'Runtime.executionContextCreated':
                c = d['params']['context']
                fid = c.get('auxData', {}).get('frameId', '')
                contexts[c['id']] = {'frameId': fid, 'origin': c.get('origin',''), 'name': c.get('name','')}
            if d.get('id') == mid:
                return d.get('result', {})

    await cmd('Runtime.enable')
    await asyncio.sleep(1)

    # احصل على frameId من DOM
    doc = await cmd('DOM.getDocument', {'depth': -1, 'pierce': True})
    target_frame = None
    async def walk(n):
        nonlocal target_frame
        if target_frame: return
        if n.get('nodeName') == 'IFRAME':
            al = n.get('attributes', [])
            attrs = {al[i]: al[i+1] for i in range(0, len(al), 2)}
            if 'api2/bframe' in attrs.get('src', ''):
                target_frame = n['frameId']; return
        for c in n.get('children', []):
            await walk(c)
    await walk(doc['root'])
    print('target frame:', target_frame)
    if not target_frame:
        await ws.close(); return

    # اطبع كل contexts مع frameIds
    for cid, info in contexts.items():
        print(f"  ctx {cid}: frame={info['frameId'][:16]} origin={info['origin']}")

    # ابحث عن context مطابق
    bframe_ctx = None
    for cid, info in contexts.items():
        if info['frameId'] == target_frame:
            bframe_ctx = cid; break

    # fallback: استخدم createIsolatedWorld
    if not bframe_ctx:
        print('using createIsolatedWorld')
        world = await cmd('Page.createIsolatedWorld', {'frameId': target_frame, 'worldName': 'ghost2'})
        bframe_ctx = world['executionContextId']

    print('using ctx:', bframe_ctx)

    # فحص محتوى bframe
    r_probe = await cmd('Runtime.evaluate', {
        'expression': 'document.body ? document.body.innerHTML.slice(0,400) : "no body"',
        'returnByValue': True, 'contextId': bframe_ctx})
    print('body preview:', r_probe.get('result', {}).get('value'))

    # اضغط زر الصوت
    js_click = '''(function(){
        var b = document.querySelector('#recaptcha-audio-button');
        if(!b){var bs=document.querySelectorAll('button');return 'no-audio-btn|btns='+bs.length;}
        b.click(); return 'clicked';
    })()'''
    r1 = await cmd('Runtime.evaluate', {'expression': js_click, 'returnByValue': True, 'contextId': bframe_ctx})
    print('click:', r1.get('result', {}).get('value'))
    await asyncio.sleep(4)

    js_url = '''(function(){
        var s = document.querySelector('#audio-source');
        if(s && s.src) return s.src;
        var a = document.querySelector('audio');
        if(a && a.src) return a.src;
        return 'not-found';
    })()'''
    r2 = await cmd('Runtime.evaluate', {'expression': js_url, 'returnByValue': True, 'contextId': bframe_ctx})
    url = r2.get('result', {}).get('value')
    print('audio:', url)
    if url and url.startswith('http'):
        with open('/tmp/recaptcha_url.txt', 'w') as f:
            f.write(url)
    await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
