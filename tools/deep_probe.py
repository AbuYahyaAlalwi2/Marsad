"""deep_probe.py — يستكشف bframe بعمق بعد انتظار طويل."""
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

    # افحص iframe الـ bframe من الخارج أولاً
    print('[1] Checking parent page...')
    r1 = await cmd('Runtime.evaluate', {
        'expression': '''JSON.stringify(
            Array.from(document.querySelectorAll('iframe')).map(function(f){
                return {
                    id: f.id,
                    src: (f.src||'').slice(0,100),
                    w: f.getBoundingClientRect().width,
                    h: f.getBoundingClientRect().height,
                    vis: f.style.visibility || 'default',
                    display: f.style.display || 'default',
                };
            })
        )''',
        'returnByValue': True})
    print(r1['result']['value'])

    # احصل على frameId للـ bframe
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
    print(f'[2] bframe frameId: {bframe_id}')
    if not bframe_id:
        await ws.close(); return

    # افحص محتوى bframe بعمق
    world = await cmd('Page.createIsolatedWorld',
                      {'frameId': bframe_id, 'worldName': 'deep'})
    ctx = world['executionContextId']
    await asyncio.sleep(2)
    r2 = await cmd('Runtime.evaluate', {
        'expression': '''JSON.stringify({
            bodyLen: document.body ? document.body.innerHTML.length : 0,
            html: document.body ? document.body.innerHTML.slice(0,500) : 'no body',
            buttons: document.querySelectorAll('button').length,
            all: document.querySelectorAll('*').length,
            readyState: document.readyState,
        })''',
        'returnByValue': True, 'contextId': ctx})
    print(f'[3] bframe content: {r2["result"]["value"]}')

    # حاول الضغط على زر الصوت
    r3 = await cmd('Runtime.evaluate', {
        'expression': '''(function(){
            var b = document.getElementById('recaptcha-audio-button');
            if (!b) {
                var bs = document.querySelectorAll('button');
                return 'no-audio|btns=' + bs.length;
            }
            b.click();
            return 'clicked';
        })()''',
        'returnByValue': True, 'contextId': ctx})
    print(f'[4] audio click: {r3["result"]["value"]}')

    await asyncio.sleep(4)
    r4 = await cmd('Runtime.evaluate', {
        'expression': '''JSON.stringify({
            audio: (document.getElementById('audio-source')||{}).src || null,
            has_audio_tag: !!document.querySelector('audio'),
            buttons: document.querySelectorAll('button').length,
        })''',
        'returnByValue': True, 'contextId': ctx})
    print(f'[5] after click: {r4["result"]["value"]}')

    await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
