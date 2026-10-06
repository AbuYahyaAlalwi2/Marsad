# تعريف صارم: ثلاثي هندسة الكشف = (سلوك مشبوه + آلية كشف + إجراء تصليب).
# هذا تحليل دفاعي بحت وليس سلسلة هجومية قابلة للتنفيذ.
# أي عينة تفتقر لأحد المكونات الثلاثة تُرفض آلياً.
import json, sys, re
from typing import Tuple, Dict, Any

class CompletenessGate:
    def __init__(self):
        self.stats = {"accepted": 0, "rejected": 0, "reasons": {}}
        
    def validate_unit(self, unit: Dict[str, Any]) -> Tuple[bool, str]:
        # الحد الفاصل: مخرج دفاعي إلزامي
        if not unit.get("defensive_mechanism"):
            return False, "MISSING_DEFENSIVE_MECHANISM"
            
        defense = str(unit["defensive_mechanism"]).strip()
        if len(defense) < 50 or "implement" not in defense.lower():
            return False, "INVALID_DEFENSE_NOT_APPLICABLE"
        
        # الأمر البنيوي #1: سيناريوهات متراكبة كاملة
        required = ["anomalous_behavior", "detection_mechanism", "hardening_response"]
        missing = [c for c in required if not unit.get(c)]
        if missing:
            return False, f"INCOMPLETE_OVERLAY_MISSING_{','.join(missing).upper()}"
        
        # الأمر البنيوي #3: تنسيق CVE صحيح (إن وُجد)
        if unit.get("cve_id") and not re.match(r'^CVE-\d{4}-\d{4,}$', unit["cve_id"]):
            return False, "INVALID_CVE_FORMAT"
        
        # الأمر البنيوي #5: بيئات اختبار معيارية
        allowed_envs = ["DVWA", "Juice Shop", "Metasploitable", "OWASP WebGoat", "Custom Sandbox"]
        env = unit.get("test_environment", "").strip()
        if env and env not in allowed_envs and not env.startswith("Custom Sandbox"):
            return False, "NON_STANDARD_ENVIRONMENT"
        
        # KPI: عمق تقني كافٍ للتكييف (>30 دقيقة)
        if len(str(unit.get("technical_description", "")).strip()) < 200:
            return False, "INSUFFICIENT_TECHNICAL_DEPTH"
        
        return True, ""
    
    def process_batch(self, input_file: str, output_file: str) -> bool:
        print(f"🔒 بدء فحص بوابة الاكتمال: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as fin, \
             open(output_file, 'w', encoding='utf-8') as fout:
            for i, line in enumerate(fin, 1):
                try:
                    unit = json.loads(line)
                    ok, reason = self.validate_unit(unit)
                    if ok:
                        unit["_gate_status"] = "COMPLETENESS_PASSED"
                        fout.write(json.dumps(unit, ensure_ascii=False) + "\n")
                        self.stats["accepted"] += 1
                    else:
                        self.stats["rejected"] += 1
                        key = reason.split(":")[0] if ":" in reason else reason
                        self.stats["reasons"][key] = self.stats["reasons"].get(key, 0) + 1
                        print(f"   ❌ عينة #{i}: {reason}")
                except Exception as e:
                    self.stats["rejected"] += 1
                    print(f"   ❌ خطأ بالعينة #{i}: {e}")
        
        print(f"\n تقرير البوابة:")
        print(f"   ✅ مقبول: {self.stats['accepted']}")
        print(f"   ❌ مرفوض: {self.stats['rejected']}")
        for r, c in sorted(self.stats["reasons"].items(), key=lambda x:-x[1]):
            print(f"      • {r}: {c}")
        return self.stats["accepted"] > 0

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("الاستخدام: python gate_completeness_v2.py input.jsonl output.jsonl")
        sys.exit(1)
    g = CompletenessGate()
    sys.exit(0 if g.process_batch(sys.argv[1], sys.argv[2]) else 1)
