"""
manual_captcha.py — أنت تنقر، النظام يكمل.
1. يفتح صفحة reCAPTCHA في Chrome
2. ينتظر نقرة إصبعك (60 ثانية)
3. يكتشف ظهور التحدي
4. يستخرج الصوت + Whisper + يرسل الإجابة
"""
import asyncio, httpx, json, websockets, time
from pathlib import Path


SITE_URL = "https://www.google.com/recaptcha/api2/demo"


async def cdp():
    v = httpx.get('http://localhost:9222/json/version', timeout=10).json()
    ws = await websockets.connect(v['webSocketDebuggerUrl'], max_size=50*1024*1024)
    state = {'mid': 0}
    async def cmd(m, p=None, s=None):
        state['mid'] += 1
        msg = {'id': state['mid'], 'method': m, 'params': p or {}}
        if s: msg['sessionId'] = s
        await ws.send(json.dumps(msg))
        while True:
            d = json.loads(await ws.recv())
            if d.get('id') == state['mid']:
                if 'error' in d: raise RuntimeError(d['error'])
                return d.get('result', {})
    return ws, cmd


async def get_bframe_state(cmd, s):
    """يفحص حالة bframe: كم زر؟ هل عنده body؟"""
    doc = await cmd('DOM.getDocument', {'depth': -1, 'pierce': True}, s)
    bfid = {'id': None}
    async def walk(n):
        if bfid['id']: return
        if n.get('nodeName') == 'IFRAME':
            al = n.get('attributes', [])
            attrs = {al[i]: al[i+1] for i in range(0, len(al), 2)}
            if 'api2/bframe' in attrs.get('src', ''):
                bfid['id'] = n['frameId']; return
        for c in n.get('children', []):
            await walk(c)
    await walk(doc['root'])
    if not bfid['id']:
        return None, None
    w = await cmd('Page.createIsolatedWorld',
                  {'frameId': bfid['id'], 'worldName': f'w{time.time()}'},
                  session)
    ctx = w['executionContextId']
    r = await cmd('Runtime.evaluate', {
        'expression': "JSON.stringify({b:document.querySelectorAll('button').length,l:document.body?document.body.innerHTML.length:0})",
        'returnByValue': True, 'contextId': ctx}, s)
    return bfid['id'], json.loads(r['result']['value'])


async def main():
    ws, cmd = await cdp()
    try:
        # 1. افتح tab جديدة
        t = await cmd('Target.createTarget', {'url': SITE_URL})
        tid = t['targetId']
        a = await cmd('Target.attachToTarget', {'targetId': tid, 'flatten': True})
        sid = a['sessionId']
        await cmd('Page.enable', s=sid)
        await cmd('Runtime.enable', s=sid)

        print('=' * 55)
        print('⚠️  انتقل الآن إلى Chrome على هاتفك')
        print('⚠️  انقر على مربع reCAPTCHA بإصبعك')
        print('⚠️  بعد ظهور التحدي، ارجع إلى Termux')
        print('=' * 55)
        print()

        # 2. انتظر ظهور التحدي (120 ثانية)
        for i in range(40):
            await asyncio.sleep(3)
            bfid, state = await get_bframe_state(cmd, sid)
            if state:
                print(f'  [{(i+1)*3}s] buttons={state["b"]} bodyLen={state["l"]}')
                if state['b'] > 0 and state['l'] > 200:
                    print()
                    print('[✓] التحدي ظهر! نكمل تلقائياً...')
                    break
        else:
            print('[✗] لم يظهر التحدي. أعد المحاولة.')
            return

        # 3. اضغط زر الصوت
        print('[+] الضغط على زر الصوت...')
        w = await cmd('Page.createIsolatedWorld',
                      {'frameId': bfid, 'worldName': 'audio'}, sid)
        ctx = w['executionContextId']
        r = await cmd('Runtime.evaluate', {
            'expression': "var b=document.getElementById('recaptcha-audio-button'); if(b){b.click(); 'clicked';} else 'no-btn';",
            'returnByValue': True, 'contextId': ctx}, sid)
        print(f'    → {r["result"]["value"]}')
        await asyncio.sleep(4)

        # 4. استخرج رابط الصوت
        r = await cmd('Runtime.evaluate', {
            'expression': "(document.getElementById('audio-source')||{}).src || 'none'",
            'returnByValue': True, 'contextId': ctx}, sid)
        url = r['result']['value']
        print(f'[+] audio url: {url}')
        if not url or not url.startswith('http'):
            print('[✗] لم يُعثر على الصوت'); return

        # 5. احفظ الرابط
        Path('/tmp/recaptcha_url.txt').write_text(url)
        print('[✓] محفوظ في /tmp/recaptcha_url.txt')
        print()
        print('الخطوة التالية: التشغيل مع Whisper (لاحقاً)')

    finally:
        await ws.close()


if __name__ == '__main__':
    asyncio.run(main())
