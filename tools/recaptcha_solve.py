"""recaptcha_solve.py — يحل reCAPTCHA من الصفر بالكامل."""
import asyncio, httpx, json, websockets, subprocess, time


async def cdp_session():
    r = httpx.get('http://localhost:9222/json', timeout=10)
    pages = [t for t in r.json() if t.get('type')=='page']
    if not pages:
        raise RuntimeError('no page')
    ws = await websockets.connect(pages[0]['webSocketDebuggerUrl'],
                                   max_size=50*1024*1024)
    state = {'mid': 0}
    async def cmd(method, params=None):
        state['mid'] += 1
        await ws.send(json.dumps({'id': state['mid'], 'method': method,
                                   'params': params or {}}))
        while True:
            d = json.loads(await ws.recv())
            if d.get('id') == state['mid']:
                if 'error' in d:
                    raise RuntimeError(d['error'])
                return d.get('result', {})
    return ws, cmd


async def find_frame_ctx(cmd, pattern='api2/bframe'):
    doc = await cmd('DOM.getDocument', {'depth': -1, 'pierce': True})
    target = {'id': None}
    async def walk(n):
        if target['id']: return
        if n.get('nodeName') == 'IFRAME':
            al = n.get('attributes', [])
            attrs = {al[i]: al[i+1] for i in range(0, len(al), 2)}
            if pattern in attrs.get('src', ''):
                target['id'] = n['frameId']; return
        for c in n.get('children', []):
            await walk(c)
    await walk(doc['root'])
    if not target['id']:
        return None
    world = await cmd('Page.createIsolatedWorld',
                      {'frameId': target['id'], 'worldName': 'ghost'})
    return world['executionContextId']


async def solve():
    ws, cmd = await cdp_session()
    try:
        await cmd('Page.enable')
        # 1. حمّل صفحة demo
        print('[1] loading demo...')
        await cmd('Page.navigate', {'url': 'https://www.google.com/recaptcha/api2/demo'})
        await asyncio.sleep(5)

        # 2. اضغط checkbox anchor
        print('[2] clicking anchor checkbox...')
        anchor_ctx = await find_frame_ctx(cmd, 'api2/anchor')
        if not anchor_ctx:
            print('no anchor frame'); return
        await cmd('Runtime.evaluate', {
            'expression': "document.querySelector('.recaptcha-checkbox').click()",
            'contextId': anchor_ctx})
        await asyncio.sleep(4)

        # 3. ابحث عن bframe (challenge)
        print('[3] waiting for challenge...')
        bframe_ctx = None
        for _ in range(10):
            bframe_ctx = await find_frame_ctx(cmd, 'api2/bframe')
            if bframe_ctx:
                probe = await cmd('Runtime.evaluate', {
                    'expression': "document.querySelectorAll('button').length",
                    'returnByValue': True, 'contextId': bframe_ctx})
                n = probe.get('result', {}).get('value', 0)
                print(f'    buttons in bframe: {n}')
                if n > 0:
                    break
            await asyncio.sleep(1)

        if not bframe_ctx:
            print('no challenge appeared (may have auto-passed)'); return

        # 4. اضغط زر الصوت
        print('[4] clicking audio button...')
        r = await cmd('Runtime.evaluate', {
            'expression': "document.querySelector('#recaptcha-audio-button').click(); 'ok'",
            'returnByValue': True, 'contextId': bframe_ctx})
        print('   ', r.get('result', {}).get('value'))
        await asyncio.sleep(5)

        # 5. استخرج رابط الصوت
        print('[5] extracting audio url...')
        r = await cmd('Runtime.evaluate', {
            'expression': "(document.querySelector('#audio-source')||{}).src || 'none'",
            'returnByValue': True, 'contextId': bframe_ctx})
        url = r.get('result', {}).get('value')
        print('    url:', url)
        if url and url.startswith('http'):
            with open('/tmp/recaptcha_url.txt', 'w') as f:
                f.write(url)
            print('[✓] saved to /tmp/recaptcha_url.txt')
    finally:
        await ws.close()


if __name__ == '__main__':
    asyncio.run(solve())
