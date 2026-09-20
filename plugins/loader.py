"""
محمل الإضافات — تحميل ديناميكي
"""
import os
import importlib.util
from config import BASE_DIR
from db import log_event

class PluginLoader:
    """تحميل إضافات من مجلد plugins/"""

    def __init__(self):
        self.plugins_dir = os.path.join(BASE_DIR, "plugins")
        self.loaded = {}

        os.makedirs(self.plugins_dir, exist_ok=True)

        log_event("plugin_loader", {"status": "initialized"})

    def load_all(self) -> dict:
        """تحميل كل الإضافات"""
        loaded = {}

        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                name = filename[:-3]
                result = self.load(name)
                loaded[name] = result

        return loaded

    def load(self, name: str) -> dict:
        """تحميل إضافة محددة"""
        try:
            path = os.path.join(self.plugins_dir, f"{name}.py")

            if not os.path.exists(path):
                return {"status": "error", "reason": "file_not_found"}

            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            self.loaded[name] = module

            log_event("plugin_loader", {"loaded": name})

            return {"status": "success", "module": module}

        except Exception as e:
            log_event("plugin_loader_errors", {"name": name, "error": str(e)})
            return {"status": "error", "error": str(e)}

    def get(self, name: str):
        """الحصول على إضافة محملة"""
        return self.loaded.get(name)

    def call(self, name: str, function: str, *args, **kwargs):
        """استدعاء دالة في إضافة"""
        module = self.get(name)

        if module and hasattr(module, function):
            return getattr(module, function)(*args, **kwargs)

        return None

plugin_loader = PluginLoader()
