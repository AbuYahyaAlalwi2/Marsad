"""probe_bframe.py — يستكشف DOM داخل bframe."""
import asyncio, httpx, json, websockets


async def main():
    r = httpx.get('http://localhost:9222/json', timeout=10)
    pages = [t for t in r.json() if t.get('type')=='page' and 'recaptcha' in t.get('url','')]
    if not pages:
        print('no tab'); return
    ws = await websockets.connect(pages[0]['webSocketDebuggerUrl'], max_size=50*1024*1024)
    mid = 0
    async def cmd(method, params=None):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        while True:
            d = json.loads(await ws.recv())
            if d.get('id') == mid:
                return d.get('result', {})

    doc = await cmd('DOM.getDocument', {'depth': -1, 'pierce': True})
    frame_id = None
    async def walk(n):
        nonlocal frame_id
        if frame_id: return
        if n.get('nodeName') == 'IFRAME':
            al = n.get('attributes', [])
            attrs = {al[i]: al[i+1] for i in range(0, len(al), 2)}
            if 'api2/bframe' in attrs.get('src', ''):
                frame_id = n['frameId']; return
        for c in n.get('children', []):
            await walk(c)
    await walk(doc['root'])
    print('frameId:', frame_id)
    if not frame_id: await ws.close(); return

    world = await cmd('Page.createIsolatedWorld', {'frameId': frame_id, 'worldName': 'probe'})
    ctx = world['executionContextId']
    print('ctx:', ctx)
    await asyncio.sleep(1)

    js = '''
    (function(){
        var btns = Array.from(document.querySelectorAll('button')).map(function(b){
            return {id: b.id, cls: b.className, txt: (b.textContent||'').slice(0,30)};
        });
        var inputs = Array.from(document.querySelectorAll('input')).map(function(i){
            return {id: i.id, type: i.type};
        });
        return JSON.stringify({buttons: btns, inputs: inputs, title: document.title});
    })()
    '''
    r1 = await cmd('Runtime.evaluate', {'expression': js, 'returnByValue': True, 'contextId': ctx})
    print('DOM:', r1.get('result', {}).get('value'))
    await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
