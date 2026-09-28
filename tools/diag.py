import asyncio, httpx, json, websockets


async def main():
    r = httpx.get('http://localhost:9222/json', timeout=10)
    print('=== TABS ===')
    for t in r.json():
        if t.get('type') == 'page':
            print(t.get('url'), '|', t.get('title'))

    pages = [t for t in r.json() if t.get('type')=='page']
    if not pages:
        print('no page'); return

    # اختر tab فيها recaptcha
    target = next((p for p in pages if 'recaptcha' in p.get('url','')), pages[0])
    print('\nUsing tab:', target['url'])

    ws = await websockets.connect(target['webSocketDebuggerUrl'], max_size=50*1024*1024)
    mid = 0
    async def cmd(method, params=None):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
        while True:
            d = json.loads(await ws.recv())
            if d.get('id') == mid:
                return d.get('result', {})

    await cmd('Page.enable')
    # افحص الـ iframes من طبقة الـ JS
    r = await cmd('Runtime.evaluate', {
        'expression': "JSON.stringify({url:location.href, iframes:Array.from(document.querySelectorAll('iframe')).map(f=>({src:f.src.slice(0,120),id:f.id}))})",
        'returnByValue': True})
    print('\nIframes:', r.get('result', {}).get('value'))

    # افحص نوع الصفحة
    r2 = await cmd('Runtime.evaluate', {
        'expression': "document.body ? document.body.innerHTML.slice(0,300) : 'no body'",
        'returnByValue': True})
    print('\nBody preview:', r2.get('result', {}).get('value')[:300])

    await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
