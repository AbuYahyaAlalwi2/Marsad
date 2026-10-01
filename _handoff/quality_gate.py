"""بوابة الجودة والأمان للكود. تعيد قائمة (نوع، رسالة) حيث النوع: security | syntax | quality."""
import ast

BANNED_IMPORTS = {"os", "subprocess", "socket", "ctypes", "shutil", "requests", "urllib", "http",
                  "ftplib", "pty", "signal", "multiprocessing", "importlib", "pickle", "marshal", "sys"}
BANNED_CALLS = {"eval", "exec", "compile", "__import__", "open", "input", "breakpoint"}
BANNED_ATTRS = {"__subclasses__", "__globals__", "__builtins__", "__bases__", "__mro__", "__code__", "__class__"}


class QualityGate:
    def __init__(self, scanner, max_chars=20000, max_func_lines=60):
        self.scanner, self.max_chars, self.max_func_lines = scanner, max_chars, max_func_lines

    def check_python(self, code):
        """للكود المولَّد الذي سيُنفَّذ: صارم (دفاع إضافي؛ العزل هو الحماية الحقيقية)."""
        issues = []
        if len(code) > self.max_chars:
            return [("security", "الكود أطول من الحد")]
        if self.scanner.find(code):
            issues.append(("security", "الكود يحتوي سراً"))
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return issues + [("syntax", f"خطأ صياغة في السطر {e.lineno}")]
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    if a.name.split(".")[0] in BANNED_IMPORTS:
                        issues.append(("security", f"استيراد ممنوع: {a.name}"))
            elif isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] in BANNED_IMPORTS:
                issues.append(("security", f"استيراد ممنوع: {n.module}"))
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in BANNED_CALLS:
                issues.append(("security", f"استدعاء ممنوع: {n.func.id}"))
            elif isinstance(n, ast.Attribute) and n.attr in BANNED_ATTRS:
                issues.append(("security", f"وصول ممنوع: {n.attr}"))
            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if (n.end_lineno - n.lineno) > self.max_func_lines:
                    issues.append(("quality", f"الدالة {n.name} أطول من {self.max_func_lines} سطراً"))
        return issues

    def check_repo_file(self, path, content):
        """لتغييرات المستودع: أسرار + صياغة + استدعاءات ديناميكية؛ لا نمنع الاستيراد العادي."""
        issues = []
        if self.scanner.find(content):
            issues.append(("security", "الملف يحتوي سراً"))
        if path.endswith(".py"):
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                return issues + [("syntax", f"خطأ صياغة في السطر {e.lineno}")]
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"eval", "exec"}:
                    issues.append(("security", f"{n.func.id} ممنوع في المستودع"))
        return issues

    @staticmethod
    def blocking(issues):
        return [i for i in issues if i[0] in ("security", "syntax")]
