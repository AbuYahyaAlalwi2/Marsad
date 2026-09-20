"""
إعادة الإنشاء — توليد أكواد ومشاريع جديدة
"""
import time
from db import log_event

class CodeRegenerator:
    """إعادة إنشاء أكواد من البيانات المجمعة"""

    def regenerate(self, seed_code: str, variations: int = 5) -> list:
        """توليد variations من الكود"""
        variations_list = []

        for i in range(variations):
            variation = self._generate_variation(seed_code, i)
            variations_list.append(variation)

        log_event("regenerator", {
            "seed_length": len(seed_code),
            "variations": len(variations_list)
        })

        return variations_list

    def _generate_variation(self, code: str, index: int) -> str:
        return f"# Variation {index}\n# Based on: {code[:50]}...\n{code}\n# End variation"

    def generate_project(self, description: str, files: int = 5) -> dict:
        """توليد مشروع كامل"""
        project = {
            "name": f"project_{int(time.time())}",
            "description": description,
            "files": {}
        }

        for i in range(files):
            filename = f"file_{i}.py"
            project["files"][filename] = f"# {filename}\n# Generated from: {description[:50]}"

        return project

regenerator = CodeRegenerator()
