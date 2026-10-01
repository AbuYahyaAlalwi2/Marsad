"""الصنف الأساس لكل وكيل."""


class Agent:
    name = "base"
    version = "0.1.0"

    async def handle(self, kind, payload, ctx):
        raise NotImplementedError
