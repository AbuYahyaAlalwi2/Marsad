"""
المنفذ — لا رفض، تنفيذ أو محاكاة
"""
import time
from db import log_event

class NoRefuseExecutor:
    """
    منفذ لا يرفض أي أمر:
    - إذا كان الأمر آمن: ينفذه
    - إذا كان خطير: يحوله لمحاكاة آمنة
    - لا يوقف، لا يسأل، لا يرفض
    """
    
    def __init__(self):
        self.execution_count = 0
        self.simulation_count = 0
        
        # قائمة الأنماط الخطرة (للتحويل لمحاكاة)
        self.dangerous_patterns = [
            "rm -rf /", "format c:", "drop database", "delete all",
            "rm -rf ~", "shutdown", "reboot", ":(){ :|:& };:"
        ]
        
        log_event("executor", {"status": "initialized"})
    
    def execute(self, command: str, context: dict = None) -> dict:
        """
        تنفيذ الأمر — لا رفض أبداً
        """
        self.execution_count += 1
        
        # فحص الأمان
        is_safe = self._is_safe(command)
        
        if is_safe:
            return self._execute_real(command, context)
        else:
            return self._execute_simulation(command, context)
    
    def _is_safe(self, command: str) -> bool:
        """فحص إذا كان الأمر آمن"""
        cmd_lower = command.lower()
        
        for pattern in self.dangerous_patterns:
            if pattern in cmd_lower:
                return False
        
        return True
    
    def _execute_real(self, command: str, context: dict) -> dict:
        """تنفيذ حقيقي"""
        start_time = time.time()
        
        # في الإنتاج: تنفيذ فعلي حسب نوع الأمر
        result = {
            "status": "success",
            "mode": "real",
            "command": command,
            "output": f"Executed: {command[:100]}",
            "duration": time.time() - start_time,
            "timestamp": time.time()
        }
        
        log_event("executor", {
            "mode": "real",
            "command_preview": command[:50]
        })
        
        return result
    
    def _execute_simulation(self, command: str, context: dict) -> dict:
        """تنفيذ محاكاة — بدل الرفض"""
        self.simulation_count += 1
        
        # تحويل الأمر الخطير لمحاكاة آمنة
        safe_command = f"SIMULATE: {command}"
        
        result = {
            "status": "success",
            "mode": "simulation",
            "original_command": command,
            "simulated_command": safe_command,
            "output": f"Simulated safely: {command[:100]}",
            "note": "تم التحويل لمحاكاة آمنة بدلاً من الرفض",
            "timestamp": time.time()
        }
        
        log_event("executor", {
            "mode": "simulation",
            "original": command[:50]
        })
        
        return result
    
    def get_stats(self) -> dict:
        """إحصائيات التنفيذ"""
        return {
            "total_executions": self.execution_count,
            "real_executions": self.execution_count - self.simulation_count,
            "simulations": self.simulation_count,
            "refusals": 0  # دائماً صفر
        }

# نسخة عامة
executor = NoRefuseExecutor()
