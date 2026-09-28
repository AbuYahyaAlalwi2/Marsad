"""chrome_cdp.py — يتحكم في Chrome الحقيقي عبر CDP من Termux."""
import json, asyncio, httpx, websockets

CDP_HTTP = "http://localhost:9222"


class ChromeCDP:
    def __init__(self):
        self.ws = None
        self._id = 0

    async def connect(self):
        # نستخدم WebSocket على مستوى المتصفح مباشرة
        r = httpx.get(f"{CDP_HTTP}/json/version", timeout=10)
        info = r.json()
        url = info["webSocketDebuggerUrl"]
        if url.startswith("ws://localhost"):
            url = url.replace("ws://localhost", "ws://127.0.0.1")
        self.ws = await websockets.connect(url, max_size=50*1024*1024)
        # ننشئ tab جديدة
        result = await self.cmd("Target.createTarget", {"url": "about:blank"})
        target_id = result["targetId"]
        # نرفق بالـ tab
        attach = await self.cmd("Target.attachToTarget",
                                {"targetId": target_id, "flatten": True})
        self.session_id = attach["sessionId"]

    async def cmd(self, method, params=None, session=None):
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        sid = session or getattr(self, "session_id", None)
        if sid:
            msg["sessionId"] = sid
        await self.ws.send(json.dumps(msg))
        while True:
            data = json.loads(await self.ws.recv())
            if data.get("id") == self._id:
                if "error" in data:
                    raise RuntimeError(f"CDP error: {data['error']}")
                return data.get("result", {})

    async def goto(self, url):
        await self.cmd("Page.enable")
        await self.cmd("Page.navigate", {"url": url})
        await asyncio.sleep(2)

    async def evaluate(self, js):
        r = await self.cmd("Runtime.evaluate", {
            "expression": js, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    async def click(self, selector):
        box = await self.evaluate(f"""
            (function() {{
                const el = document.querySelector('{selector}');
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {{x: r.x + r.width/2, y: r.y + r.height/2}};
            }})()
        """)
        if not box:
            return False
        for evt in ("mousePressed", "mouseReleased"):
            await self.cmd("Input.dispatchMouseEvent", {
                "type": evt, "x": box["x"], "y": box["y"],
                "button": "left", "clickCount": 1})
        return True


async def main():
    cdp = ChromeCDP()
    await cdp.connect()
    await cdp.goto("https://example.com")
    title = await cdp.evaluate("document.title")
    print(f"OK: {title}")
    await cdp.ws.close()


if __name__ == "__main__":
    asyncio.run(main())
