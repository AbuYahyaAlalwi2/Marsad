"""recaptcha_solve_v2.py — ينشئ تاب جديدة ويحل reCAPTCHA."""
import asyncio, httpx, json, websockets


async def main():
    # 1. اتصل بـ browser-level WS
    v = httpx.get('http://localhost:9222/json/version', timeout=10).json()
    browser_ws = v['webSocketDebuggerUrl']
    ws = await websockets.connect(browser_ws, max_size=50*1024*1024)
    mid = 0
    async def cmd(method, params=None, session=None):
        nonlocal mid
        mid += 1
        m = {'id': mid, 'method': method, 'params': params or {}}
        if session: m['sessionId'] = session
        await ws.send(json.dumps(m))
        while True:
            d = json.loads(await ws.recv())
            if d.get('id') == mid:
                if 'error' in d: raise RuntimeError(d['error'])
                return d.get('result', {})

    # 2. أنشئ تاب جديدة
    t = await cmd('Target.createTarget', {'url': 'about:blank'})
    tid = t['targetId']
    a = await cmd('Target.attachToTarget', {'targetId': tid, 'flatten': True})
    sid = a['sessionId']
    print('[+] new tab created:', tid[:12])

    # 3. اذهب لصفحة reCAPTCHA demo
    await cmd('Page.enable', session=sid)
    await cmd('Runtime.enable', session=sid)
    await cmd('Page.navigate',
              {'url': 'https://www.google.com/recaptcha/api2/demo'},
              session=sid)
    print('[+] navigating...')
    await asyncio.sleep(8)

    # 4. ابحث عن anchor iframe
    async def get_frame_ctx(pattern):
        doc = await cmd('DOM.getDocument', {'depth': -1, 'pierce': True}, session=sid)
        found = {'fid': None}
        async def walk(n):
            if found['fid']: return
            if n.get('nodeName') == 'IFRAME':
                al = n.get('attributes', [])
                attrs = {al[i]: al[i+1] for i in range(0, len(al), 2)}
                if pattern in attrs.get('src', ''):
                    found['fid'] = n['frameId']; return
            for c in n.get('children', []):
                await walk(c)
        await walk(doc['root'])
        if not found['fid']: return None
        w = await cmd('Page.createIsolatedWorld',
                      {'frameId': found['fid'], 'worldName': 'ghost'},
                      session=sid)
        return w['executionContextId']

    anchor_ctx = await get_frame_ctx('api2/anchor')
    if not anchor_ctx:
        print('[-] no anchor frame'); await ws.close(); return
    print('[+] anchor ctx:', anchor_ctx)

    # 5. اضغط checkbox
    r = await cmd('Runtime.evaluate', {
        'expression': "document.querySelector('.recaptcha-checkbox').click(); 'clicked'",
        'returnByValue': True, 'contextId': anchor_ctx}, session=sid)
    print('[+] anchor click:', r.get('result', {}).get('value'))
    await asyncio.sleep(5)

    # 6. ابحث عن bframe
    bframe_ctx = None
    for i in range(10):
        bframe_ctx = await get_frame_ctx('api2/bframe')
        if bframe_ctx:
            r = await cmd('Runtime.evaluate', {
                'expression': "document.querySelectorAll('button').length",
                'returnByValue': True, 'contextId': bframe_ctx}, session=sid)
            n = r.get('result', {}).get('value', 0)
            print(f'[+] bframe buttons: {n}')
            if n > 0: break
        await asyncio.sleep(1)
    if not bframe_ctx:
        print('[✓] no challenge — may have auto-passed'); await ws.close(); return

    # 7. اضغط زر الصوت
    r = await cmd('Runtime.evaluate', {
        'expression': "document.querySelector('#recaptcha-audio-button').click(); 'ok'",
        'returnByValue': True, 'contextId': bframe_ctx}, session=sid)
    print('[+] audio click:', r.get('result', {}).get('value'))
    await asyncio.sleep(5)

    # 8. استخرج رابط الصوت
    r = await cmd('Runtime.evaluate', {
        'expression': "(document.querySelector('#audio-source')||{}).src || 'none'",
        'returnByValue': True, 'contextId': bframe_ctx}, session=sid)
    url = r.get('result', {}).get('value')
    print('[+] audio url:', url)
    if url and url.startswith('http'):
        with open('/tmp/recaptcha_url.txt', 'w') as f:
            f.write(url)
        print('[✓] saved')

    await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
