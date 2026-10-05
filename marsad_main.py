"""
marsad_main.py — نقطة الدخول الرئيسية لنظام مرصد
الهيكل: المستخدم → eleven_layers → security_pipeline → output_guard → المستخدم
مرصد هو الكابل فقط — لا يدمج مع النموذج
"""

import asyncio
import sys
import os
from pathlib import Path

# إضافة المسارات
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE / "core"))
sys.path.insert(0, str(BASE / "agents"))
sys.path.insert(0, str(BASE / "rag"))

# تحميل .env
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass


# ─── استيراد الوحدات ──────────────────────────────────────────────────────────

def _import_safe(name, path):
    """استيراد آمن مع رسالة واضحة عند الفشل"""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, path)
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"[تحذير] لم يتم تحميل {name}: {e}")
        return None

# تحميل الوحدات
_eleven    = _import_safe("eleven_layers",   BASE / "core/eleven_layers.py")
_guard     = _import_safe("output_guard",    BASE / "core/output_guard.py")
_pipeline  = _import_safe("security_pipeline", BASE / "agents/security_pipeline.py")
_owner     = _import_safe("owner_auth",      BASE / "core/owner_auth.py")
_pipeline_out = _import_safe("agent_output_pipeline", BASE / "core/agent_output_pipeline.py")
_dar_pipe  = _import_safe("dar_data_pipeline", BASE / "core/dar_data_pipeline.py")


# ─── النظام الرئيسي ───────────────────────────────────────────────────────────

class MarsadSystem:
    """
    مرصد — الكابل بين المستخدم والنموذج
    يطبق:
    - 11 طبقة حماية للمدخلات
    - خط أنابيب الوكلاء الأمنيين
    - حماية المخرجات حسب مستوى المستخدم
    """

    def __init__(self):
        self._init_components()

    def _init_components(self):
        # 11 طبقة حماية
        if _eleven and hasattr(_eleven, "ElevenLayerShield"):
            self.shield = _eleven.ElevenLayerShield()
        else:
            self.shield = None

        # حماية المخرجات
        if _guard and hasattr(_guard, "OutputGuard"):
            self.guard = _guard.OutputGuard()
        else:
            self.guard = None

        # خط أنابيب الوكلاء
        if _pipeline and hasattr(_pipeline, "SecurityPipeline"):
            self.sec_pipeline = _pipeline.SecurityPipeline()
        else:
            self.sec_pipeline = None

        # خط أنابيب بيانات التدريب
        if _dar_pipe and hasattr(_dar_pipe, "DarDataPipeline"):
            self.dar_pipeline = _dar_pipe.DarDataPipeline()
        else:
            self.dar_pipeline = None

        # خط أنابيب مخرجات الوكلاء
        if _pipeline_out and hasattr(_pipeline_out, "AgentOutputSink"):
            self.output_sink = _pipeline_out.AgentOutputSink()
        else:
            self.output_sink = None

    async def analyze(self, code: str, user_token: str = "", language: str = "auto") -> dict:
        """
        التحليل الأمني الكامل
        يعيد: {"report": str, "patches": list, "tier": str}
        """

        # ── تحديد مستوى المستخدم ──
        user_tier = self._get_tier(user_token)

        # ── الطبقة 1: فحص المدخلات (eleven_layers) ──
        if self.shield:
            try:
                shield_result = self.shield.process(code)
                if not shield_result.get("allowed", True):
                    return {
                        "report": "⛔ المدخل رُفض بواسطة نظام الحماية.",
                        "patches": [],
                        "tier": user_tier,
                        "blocked": True,
                    }
            except Exception as e:
                pass  # eleven_layers اختياري

        # ── الطبقة 2: تحليل الوكلاء الأربعة ──
        result = None
        if self.sec_pipeline:
            try:
                result = await self.sec_pipeline.analyze(code, language)
            except Exception as e:
                return {
                    "report": f"⚠ خطأ في التحليل: {e}\nتحقق من مفاتيح API في .env",
                    "patches": [],
                    "tier": user_tier,
                }
        else:
            return {
                "report": "⚠ خط الأنابيب غير جاهز. شغّل: python setup.py",
                "patches": [],
                "tier": user_tier,
            }

        # ── الطبقة 3: فلتر المخرجات حسب المستوى ──
        if self.guard and result:
            try:
                guarded = self.guard.filter(result, user_tier)
                return guarded
            except Exception:
                pass

        # إذا لم يكن guard موجوداً — مخرج مباشر
        patches = []
        if user_tier in ("SUBSCRIBER", "OWNER") and result:
            patches = getattr(result, "patches", []) or []

        return {
            "report": result.report if result else "لا نتائج",
            "patches": patches,
            "tier": user_tier,
            "human_approval_required": True,
        }

    def _get_tier(self, token: str) -> str:
        """يحدد مستوى المستخدم من التوكن"""
        if not token:
            return "FREE"
        if token.startswith("dlf_") and _owner and hasattr(_owner, "verify_owner"):
            try:
                if _owner.verify_owner(token):
                    return "OWNER"
            except Exception:
                pass
        if len(token) > 20:
            return "SUBSCRIBER"
        return "FREE"

    def status(self) -> dict:
        """حالة النظام"""
        return {
            "eleven_layers":       self.shield is not None,
            "output_guard":        self.guard is not None,
            "security_pipeline":   self.sec_pipeline is not None,
            "dar_data_pipeline":   self.dar_pipeline is not None,
            "agent_output_sink":   self.output_sink is not None,
            "api_keys": {
                "groq":      bool(os.getenv("GROQ_API_KEY")),
                "together":  bool(os.getenv("TOGETHER_API_KEY")),
                "deepseek":  bool(os.getenv("DEEPSEEK_API_KEY")),
            }
        }


# ─── نقطة الدخول للاختبار ─────────────────────────────────────────────────────

async def demo():
    print("\n" + "═"*45)
    print("       مرصد — اختبار سريع")
    print("═"*45)

    sys = MarsadSystem()

    # عرض الحالة
    status = sys.status()
    print("\nحالة الوحدات:")
    for k, v in status.items():
        if isinstance(v, dict):
            print(f"  API keys:")
            for kk, vv in v.items():
                icon = "✓" if vv else "✗"
                print(f"    {icon} {kk}")
        else:
            icon = "✓" if v else "✗"
            print(f"  {icon} {k}")

    # اختبار تحليل
    if not status["api_keys"]["groq"] and not status["api_keys"]["together"]:
        print("\n⚠ لا توجد مفاتيح API — أضفها في .env ثم أعد التشغيل")
        return

    test_code = '''
import sqlite3
def login(username, password):
    db = sqlite3.connect("users.db")
    q = f"SELECT * FROM users WHERE user='{username}' AND pass='{password}'"
    return db.execute(q).fetchone()
'''

    print("\n🔍 تحليل كود اختباري...")
    result = await sys.analyze(test_code, language="python")
    print(f"\n{result['report']}")
    print(f"\nالمستوى: {result['tier']}")
    if result.get("patches"):
        print(f"تصحيحات متاحة: {len(result['patches'])}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="مرصد — النظام الرئيسي")
    parser.add_argument("--status", action="store_true", help="عرض حالة النظام")
    parser.add_argument("--demo",   action="store_true", help="تشغيل اختبار سريع")
    args = parser.parse_args()

    if args.status:
        m = MarsadSystem()
        import json
        print(json.dumps(m.status(), ensure_ascii=False, indent=2))
    else:
        asyncio.run(demo())
