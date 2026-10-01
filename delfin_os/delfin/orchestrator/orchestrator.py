"""المنسّق (الطبقة 6): طابور أولويات، عمّال محدودون، تنسيق خطة متعددة الوكلاء."""
import asyncio
import itertools


class Orchestrator:
    def __init__(self, engine, workers=2):
        self.engine, self.workers = engine, workers
        self._q, self._seq, self._tasks = asyncio.PriorityQueue(), itertools.count(), []

    async def start(self):
        self._tasks = [asyncio.create_task(self._worker()) for _ in range(self.workers)]

    async def stop(self):
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _worker(self):
        while True:
            _, _, kind, payload, owner, fut = await self._q.get()
            try:
                fut.set_result(await self.engine.execute(kind, payload, owner))
            except Exception as e:
                fut.set_result({"status": "failed", "error": f"{type(e).__name__}", "result": None})

    async def submit(self, kind, payload, owner, priority=None):
        fut = asyncio.get_running_loop().create_future()
        p = self.engine.rules.priority(kind) if priority is None else priority
        await self._q.put((p, next(self._seq), kind, payload, owner, fut))
        return await fut

    async def run_goal(self, goal, owner):
        plan = await self.submit("plan", {"goal": goal}, owner)
        if plan["status"] != "done" or not plan["result"]["steps"]:
            return {"plan": plan, "steps": []}
        return {"plan": plan, "steps": await self.engine.run_steps(plan["result"]["steps"], owner)}

    def history(self, owner, limit=50):
        return self.engine.state.list_tasks(limit, owner)
