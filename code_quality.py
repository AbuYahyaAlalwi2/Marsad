"""
نظام فحص جودة الكود — فحص الكود قبل الرفع
"""
import subprocess
import os
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from db import log_event


class CodeQualityChecker:
    """
    فحص جودة الكود قبل الرفع:
    - Linting (pylint)
    - Type Checking (mypy)
    - Formatting (black)
    - Import Sorting (isort)
    - Syntax Checking
    """

    def __init__(self, project_root: str = None):
        self.project_root = project_root or os.path.dirname(os.path.abspath(__file__))
        self.errors = []
        self.warnings = []
        self.info = []

    def check_all(self, paths: List[str] = None, strict: bool = False) -> Dict:
        """فحص جميع أنواع جودة الكود"""
        results = {
            "syntax": self.check_syntax(paths),
            "linting": self.check_linting(paths),
            "type_checking": self.check_type_checking(paths),
            "formatting": self.check_formatting(paths),
            "import_sorting": self.check_import_sorting(paths),
            "security": self.check_security(paths)
        }
        
        # جمع النتائج
        all_passed = all(r.get("passed", False) for r in results.values())
        
        return {
            "all_passed": all_passed,
            "results": results,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info
        }

    def check_syntax(self, paths: List[str] = None) -> Dict:
        """فحص Syntax باستخدام Python compiler"""
        result = {"passed": True, "errors": []}
        files = self._get_python_files(paths)
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    compile(f.read(), file_path, 'exec')
            except SyntaxError as e:
                result["passed"] = False
                error_msg = f"{file_path}:{e.lineno}: {e.msg}"
                result["errors"].append(error_msg)
                self.errors.append(error_msg)
                log_event("code_quality", {"type": "syntax_error", "file": file_path, "error": str(e)})
        
        return result

    def check_linting(self, paths: List[str] = None) -> Dict:
        """فحص Linting باستخدام pylint"""
        result = {"passed": True, "errors": [], "warnings": []}
        files = self._get_python_files(paths)
        
        if not self._is_tool_available("pylint"):
            self.info.append("pylint not installed, skipping linting")
            return {"passed": True, "skipped": True}
        
        for file_path in files:
            try:
                cmd = ["pylint", "--disable=all", "--enable=E,F", file_path]
                output = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
                
                if output.returncode != 0:
                    result["passed"] = False
                    for line in output.stdout.split('\n'):
                        if line.strip():
                            if "error" in line.lower() or line.startswith('E'):
                                result["errors"].append(line)
                                self.errors.append(f"Lint Error: {line}")
                            elif "warning" in line.lower() or line.startswith('W'):
                                result["warnings"].append(line)
                                self.warnings.append(f"Lint Warning: {line}")
            except Exception as e:
                result["passed"] = False
                result["errors"].append(f"{file_path}: {str(e)}")
                self.errors.append(f"Lint Error: {file_path}: {str(e)}")
        
        return result

    def check_type_checking(self, paths: List[str] = None) -> Dict:
        """فحص Type Checking باستخدام mypy"""
        result = {"passed": True, "errors": []}
        
        if not self._is_tool_available("mypy"):
            self.info.append("mypy not installed, skipping type checking")
            return {"passed": True, "skipped": True}
        
        files = self._get_python_files(paths)
        if not files:
            return result
        
        try:
            cmd = ["mypy", "--ignore-missing-imports"] + files
            output = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
            
            if output.returncode != 0:
                result["passed"] = False
                for line in output.stdout.split('\n'):
                    if line.strip() and "error" in line.lower():
                        result["errors"].append(line)
                        self.errors.append(f"Type Error: {line}")
                        log_event("code_quality", {"type": "type_error", "error": line})
        except Exception as e:
            result["passed"] = False
            result["errors"].append(str(e))
            self.errors.append(f"Type Check Error: {str(e)}")
        
        return result

    def check_formatting(self, paths: List[str] = None, check_only: bool = True) -> Dict:
        """فحص Formatting باستخدام black"""
        result = {"passed": True, "errors": [], "files_needing_format": []}
        
        if not self._is_tool_available("black"):
            self.info.append("black not installed, skipping formatting check")
            return {"passed": True, "skipped": True}
        
        files = self._get_python_files(paths)
        
        for file_path in files:
            try:
                cmd = ["black", "--check", file_path]
                output = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
                
                if output.returncode != 0:
                    result["passed"] = False
                    result["files_needing_format"].append(file_path)
                    self.warnings.append(f"Formatting needed: {file_path}")
            except Exception as e:
                result["passed"] = False
                result["errors"].append(f"{file_path}: {str(e)}")
                self.errors.append(f"Format Check Error: {file_path}: {str(e)}")
        
        return result

    def check_import_sorting(self, paths: List[str] = None) -> Dict:
        """فحص ترتيب الاستيرادات باستخدام isort"""
        result = {"passed": True, "errors": [], "files_needing_sort": []}
        
        if not self._is_tool_available("isort"):
            self.info.append("isort not installed, skipping import sorting check")
            return {"passed": True, "skipped": True}
        
        files = self._get_python_files(paths)
        
        for file_path in files:
            try:
                cmd = ["isort", "--check-only", file_path]
                output = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
                
                if output.returncode != 0:
                    result["passed"] = False
                    result["files_needing_sort"].append(file_path)
                    self.warnings.append(f"Import sorting needed: {file_path}")
            except Exception as e:
                result["passed"] = False
                result["errors"].append(f"{file_path}: {str(e)}")
                self.errors.append(f"Import Sort Error: {file_path}: {str(e)}")
        
        return result

    def check_security(self, paths: List[str] = None) -> Dict:
        """فحص أمني أساسي"""
        result = {"passed": True, "errors": [], "warnings": []}
        files = self._get_python_files(paths)
        
        # التحقق من كلمات سر في الكود
        security_patterns = [
            ("API Key", ["api_key", "API_KEY", "apikey"]),
            ("Password", ["password", "PASSWORD", "passwd"]),
            ("Secret", ["secret", "SECRET", "token"]),
            ("Private Key", ["private_key", "PRIVATE_KEY"]),
        ]
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for pattern_name, patterns in security_patterns:
                        for pattern in patterns:
                            if pattern in content.lower():
                                result["warnings"].append(f"{file_path}: Potential {pattern_name} found")
                                self.warnings.append(f"Security Warning: {file_path} may contain {pattern_name}")
            except Exception as e:
                result["errors"].append(f"{file_path}: {str(e)}")
                self.errors.append(f"Security Check Error: {file_path}: {str(e)}")
        
        if result["errors"]:
            result["passed"] = False
        
        return result

    def format_code(self, paths: List[str] = None) -> Dict:
        """تنسيق الكود تلقائيًا"""
        result = {"formatted": [], "errors": []}
        files = self._get_python_files(paths)
        
        # استخدام black
        if self._is_tool_available("black"):
            try:
                cmd = ["black"] + files
                output = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
                if output.returncode == 0:
                    result["formatted"].extend(files)
                else:
                    result["errors"].append(f"Black formatting failed: {output.stderr}")
            except Exception as e:
                result["errors"].append(f"Black error: {str(e)}")
        
        # استخدام isort
        if self._is_tool_available("isort"):
            try:
                cmd = ["isort"] + files
                output = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
                if output.returncode == 0:
                    result["formatted"].extend(files)
                else:
                    result["errors"].append(f"isort formatting failed: {output.stderr}")
            except Exception as e:
                result["errors"].append(f"isort error: {str(e)}")
        
        return result

    def _get_python_files(self, paths: List[str] = None) -> List[str]:
        """حصول على قائمة ملفات Python"""
        if paths:
            files = []
            for path in paths:
                if os.path.isfile(path) and path.endswith('.py'):
                    files.append(path)
                elif os.path.isdir(path):
                    for root, _, filenames in os.walk(path):
                        for filename in filenames:
                            if filename.endswith('.py'):
                                files.append(os.path.join(root, filename))
            return files
        else:
            # الحصول على جميع ملفات Python في المشروع
            python_files = []
            for root, _, filenames in os.walk(self.project_root):
                # تجاهل المجلدات المخفية و __pycache__
                if '__pycache__' in root or '/.git/' in root or '/.venv/' in root:
                    continue
                for filename in filenames:
                    if filename.endswith('.py'):
                        python_files.append(os.path.join(root, filename))
            return python_files

    def _is_tool_available(self, tool_name: str) -> bool:
        """التحقق من توافر أداة معينة"""
        try:
            result = subprocess.run(
                ["which", tool_name] if os.name != 'nt' else ["where", tool_name],
                capture_output=True
            )
            return result.returncode == 0
        except:
            return False

    def generate_report(self, results: Dict) -> str:
        """توليد تقرير عن جودة الكود"""
        report = ["=" * 50]
        report.append("Code Quality Report")
        report.append("=" * 50)
        
        for check_name, check_result in results.get("results", {}).items():
            status = "✓ PASS" if check_result.get("passed", False) else "✗ FAIL"
            if check_result.get("skipped"):
                status = "⊘ SKIP"
            report.append(f"\n{check_name.upper()}: {status}")
            
            if "errors" in check_result and check_result["errors"]:
                report.append("  Errors:")
                for error in check_result["errors"]:
                    report.append(f"    - {error}")
            
            if "warnings" in check_result and check_result["warnings"]:
                report.append("  Warnings:")
                for warning in check_result["warnings"]:
                    report.append(f"    - {warning}")
            
            if "files_needing_format" in check_result and check_result["files_needing_format"]:
                report.append("  Files needing format:")
                for file_path in check_result["files_needing_format"]:
                    report.append(f"    - {file_path}")
        
        report.append("\n" + "=" * 50)
        overall = "✓ ALL CHECKS PASSED" if results.get("all_passed", False) else "✗ SOME CHECKS FAILED"
        report.append(overall)
        report.append("=" * 50)
        
        return "\n".join(report)


def check_code_quality(project_root: str = None, paths: List[str] = None, strict: bool = False) -> Dict:
    """دالة عالمية لفحص جودة الكود"""
    checker = CodeQualityChecker(project_root)
    results = checker.check_all(paths, strict)
    report = checker.generate_report(results)
    
    log_event("code_quality", {
        "all_passed": results["all_passed"],
        "errors_count": len(results.get("errors", [])),
        "warnings_count": len(results.get("warnings", [])),
        "report": report
    })
    
    return results


if __name__ == "__main__":
    # تشغيل فحص جودة الكود عند تنفيذ الملف
    results = check_code_quality()
    report = CodeQualityChecker().generate_report(results)
    print(report)
    
    if not results["all_passed"]:
        sys.exit(1)
