"""
المحلل المتقدم — أوامر معقدة، معاملات مسماة، اختصارات
"""
import re
from db import log_event


class AdvancedCommandParser:
    """
    محلل أوامر متقدم يدعم:
    - أوامر معقدة متعددة
    - معاملات مسماة (key=value)
    - اختصارات customizable
    - سياق محادثة
    - أوامر مسجلة من plugins
    """

    def __init__(self):
        # الأوامر المسجلة (يمكن للـplugins إضافة المزيد)
        self.registered_commands = {}

        # الاختصارات الافتراضية
        self.aliases = {
            "جمع": "collect",
            "اجمع": "collect",
            "collect": "collect",
            "gather": "collect",

            "نظف": "clean",
            "نظفها": "clean",
            "clean": "clean",

            "ولد": "generate",
            "ولدد": "generate",
            "generate": "generate",
            "create": "generate",
            "أنشئ": "generate",

            "اصهر": "merge",
            "ادمج": "merge",
            "merge": "merge",
            "combine": "merge",

            "درّب": "train",
            "تدريب": "train",
            "train": "train",

            "انشر": "deploy",
            "deploy": "deploy",
            "publish": "deploy",

            "هاجم": "attack",
            "attack": "attack",
            "exploit": "attack",

            "دافع": "defend",
            "defend": "defend",
            "protect": "defend",

            "حلل": "analyze",
            "analyze": "analyze",
            "analysis": "analyze",

            "شغل": "execute",
            "نفذ": "execute",
            "execute": "execute",
            "run": "execute",
        }

        # أنماط المعاملات
        self.param_patterns = [
            r'(\w+)\s*=\s*"([^"]*)"',  # key="value"
            r'(\w+)\s*=\s*\'([^\']*)\'',  # key='value'
            r'(\w+)\s*=\s*(\S+)',  # key=value
        ]

        log_event("advanced_parser", {"status": "initialized"})

    def parse(self, command: str, context: list = None) -> dict:
        """
        تحليل أمر متقدم

        يدعم:
        - "اجمع من github limit=100"
        - "collect platform=github; clean; merge"
        - "جمع و نظف و اصهر"
        - "ولد كود python function=main"
        """
        # 1. تقسيم الأوامر المتعددة
        sub_commands = self._split_commands(command)

        # 2. تحليل كل أمر فرعي
        parsed_commands = []
        for sub_cmd in sub_commands:
            parsed = self._parse_single(sub_cmd, context)
            parsed_commands.append(parsed)

        # 3. تحديد إذا كان أمر واحد أو متعدد
        is_complex = len(parsed_commands) > 1

        return {
            "original": command,
            "is_complex": is_complex,
            "commands": parsed_commands,
            "command_count": len(parsed_commands),
            "context_used": len(context) if context else 0
        }

    def _split_commands(self, command: str) -> list:
        """تقسيم الأوامر المتعددة"""
        # الفواصل المدعومة
        separators = [';', '؛', ' ثم ', ' then ', ' و ', ' and ']

        parts = [command]

        for sep in separators:
            new_parts = []
            for part in parts:
                if sep in part:
                    new_parts.extend([p.strip() for p in part.split(sep) if p.strip()])
                else:
                    new_parts.append(part)
            parts = new_parts

        return [p for p in parts if p]

    def _parse_single(self, command: str, context: list = None) -> dict:
        """تحليل أمر واحد"""
        # 1. استخراج المعاملات المسماة
        params, clean_command = self._extract_params(command)

        # 2. تحديد نوع الأمر (مع الاختصارات)
        command_type, remaining = self._identify_command(clean_command)

        # 3. استخراج المعاملات الموضعية
        positional = self._extract_positional(remaining)

        # 4. تحديد اللغة
        language = self._detect_language(command)

        # 5. البحث في السياق إذا كان الأمر غامض
        if command_type == "unknown" and context:
            command_type = self._infer_from_context(command, context)

        return {
            "type": command_type,
            "params": params,
            "positional": positional,
            "language": language,
            "raw": command,
            "confidence": self._calculate_confidence(command_type, params, context)
        }

    def _extract_params(self, command: str) -> tuple:
        """استخراج المعاملات المسماة"""
        params = {}
        clean = command

        for pattern in self.param_patterns:
            matches = re.findall(pattern, command)
            for key, value in matches:
                params[key.lower()] = value
                # إزالة من النص النظيف
                clean = clean.replace(f"{key}={value}", "")
                clean = clean.replace(f'{key}="{value}"', "")
                clean = clean.replace(f"{key}='{value}'", "")

        return params, clean.strip()

    def _identify_command(self, command: str) -> tuple:
        """تحديد نوع الأمر مع الاختصارات"""
        command_lower = command.lower().strip()

        # البحث في الاختصارات
        for alias, cmd_type in self.aliases.items():
            if command_lower.startswith(alias.lower()):
                remaining = command_lower[len(alias):].strip()
                return cmd_type, remaining

        # البحث في الأوامر المسجلة من plugins
        for cmd_name, cmd_config in self.registered_commands.items():
            if command_lower.startswith(cmd_name.lower()):
                remaining = command_lower[len(cmd_name):].strip()
                return cmd_config["type"], remaining

        return "unknown", command_lower

    def _extract_positional(self, text: str) -> list:
        """استخراج المعاملات الموضعية"""
        # كلمات مفتاحية خاصة
        special_words = {"من", "from", "في", "in", "على", "on", "بـ", "with"}

        words = text.split()
        positional = []

        for i, word in enumerate(words):
            if word.lower() not in special_words:
                positional.append(word)

        return positional

    def _detect_language(self, text: str) -> str:
        """تحديد اللغة"""
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        return "arabic" if arabic_chars > len(text) * 0.3 else "english"

    def _infer_from_context(self, command: str, context: list) -> str:
        """استنتاج نوع الأمر من السياق"""
        if not context:
            return "unknown"

        # البحث في آخر 3 أوامر
        recent_types = [c.get("type") for c in context[-3:] if c.get("type")]

        if recent_types:
            # إذا تكرر نوع، استخدمه
            most_common = max(set(recent_types), key=recent_types.count)
            return most_common

        return "unknown"

    def _calculate_confidence(self, cmd_type: str, params: dict, context: list) -> float:
        """حساب الثقة في التحليل"""
        confidence = 0.5

        # ثقة أعلى إذا كان النوع معروف
        if cmd_type != "unknown":
            confidence += 0.3

        # ثقة أعلى إذا كان هناك معاملات
        if params:
            confidence += 0.1

        # ثقة أعلى إذا كان هناك سياق
        if context:
            confidence += 0.1

        return min(1.0, confidence)

    def register_command(self, name: str, command_type: str, handler=None):
        """تسجيل أمر جديد — من plugins أو المستخدم"""
        self.registered_commands[name] = {
            "type": command_type,
            "handler": handler
        }

        log_event("advanced_parser", {
            "registered": name,
            "type": command_type
        })

    def add_alias(self, alias: str, command_type: str):
        """إضافة اختصار جديد"""
        self.aliases[alias] = command_type

    def get_registered_commands(self) -> list:
        """قائمة الأوامر المسجلة"""
        return list(self.registered_commands.keys())

    def get_aliases(self) -> dict:
        """قائمة الاختصارات"""
        return self.aliases.copy()


# نسخة عامة
advanced_parser = AdvancedCommandParser()
