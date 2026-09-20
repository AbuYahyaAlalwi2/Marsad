"""
الصهر الشرطي — تفعيل أوزان محددة حسب المهمة
"""
from db import log_event

class ConditionalMerger:
    """
    بدل صهر ثابت — النموذج يتبدل حسب السياق
    
    مثال:
    - أمر هجومي → تفعيل أوزان Kimi + DeepSeek
    - أمر برمجي → تفعيل أوزان Qwen + CodeLlama
    - أمر عربي → تفعيل أوزان Llama + Kimi
    """
    
    def __init__(self):
        # خريطة التفعيل الشرطي
        self.activation_map = {
            "attack": {
                "kimi-k3": 0.7,
                "deepseek": 0.3
            },
            "defend": {
                "qwen-coder": 0.5,
                "securebert": 0.3,
                "llama3": 0.2
            },
            "code": {
                "qwen-coder": 0.6,
                "codellama": 0.25,
                "wizardcoder": 0.15
            },
            "arabic": {
                "llama3": 0.7,
                "kimi-k3": 0.3
            },
            "analyze": {
                "deepseek": 0.5,
                "kimi-k3": 0.3,
                "phind": 0.2
            }
        }
        
        log_event("conditional_merger", {"status": "initialized"})
    
    def get_active_weights(self, task_type: str) -> dict:
        """الحصول على الأوزان النشطة لنوع مهمة"""
        weights = self.activation_map.get(task_type, self.activation_map["analyze"])
        
        log_event("conditional_merger", {
            "task_type": task_type,
            "active_weights": weights
        })
        
        return weights
    
    def merge_for_task(self, task_type: str, base_model: dict) -> dict:
        """
        صهر مؤقت للمهمة
        
        بدل تعديل النموذج الأساسي، ننشئ نسخة مؤقتة
        """
        active_weights = self.get_active_weights(task_type)
        
        # في الإنتاج: تطبيق الأوزان على النموذج
        task_model = {
            "task_type": task_type,
            "base": base_model,
            "active_weights": active_weights,
            "temporary": True  # لا يُحفظ
        }
        
        return task_model
    
    def add_activation_pattern(self, task_type: str, weights: dict):
        """إضافة نمط تفعيل جديد — مرونة كاملة"""
        self.activation_map[task_type] = weights
        
        log_event("conditional_merger", {
            "new_pattern": task_type,
            "weights": weights
        })

# نسخة عامة
conditional_merger = ConditionalMerger()
