"""محمّل الوكلاء: تحميل/إزالة/إعادة تحميل/تراجع، من مسار مسموح فقط."""
import importlib
import sys
from collections import defaultdict

from .errors import SecurityError


class PluginLoader:
    ALLOWED_PREFIX = "delfin.agents."

    def __init__(self):
        self._agents = {}
        self._history = defaultdict(list)
        self._spec = {}

    def register(self, agent):
        if agent.name in self._agents:
            self._history[agent.name].append(self._agents[agent.name])
        self._agents[agent.name] = agent

    def get(self, name):
        return self._agents[name]

    def unload(self, name):
        self._agents.pop(name, None)

    def rollback(self, name):
        if not self._history[name]:
            raise KeyError("لا توجد نسخة سابقة")
        self._agents[name] = self._history[name].pop()

    def load_module(self, dotted, cls, **kwargs):
        if not dotted.startswith(self.ALLOWED_PREFIX):
            raise SecurityError("التحميل مسموح فقط من delfin.agents")
        mod = importlib.import_module(dotted)
        inst = getattr(mod, cls)(**kwargs)
        self.register(inst)
        self._spec[inst.name] = (dotted, cls, kwargs)
        return inst

    def reload(self, name):
        dotted, cls, kwargs = self._spec[name]
        importlib.reload(sys.modules[dotted])
        return self.load_module(dotted, cls, **kwargs)

    def list(self):
        return [{"name": n, "version": getattr(a, "version", "?")} for n, a in sorted(self._agents.items())]
