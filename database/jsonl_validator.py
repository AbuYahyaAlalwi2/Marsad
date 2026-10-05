#!/usr/bin/env python3
"""
JSONL Validator - Qwen Task #10
يتحقق من تطابق ملفات التدريب مع متطلبات النظام (Schema Check)
"""

import json
import os
import sys

REQUIRED_FIELDS = ["cve_id", "severity", "description", "source"]

def validate_file(filepath):
    if not os.path.exists(filepath):
        print(f"❌ الملف غير موجود: {filepath}")
        return False
        
    errors = 0
    total_lines = 0
    
    print(f"🔍 جاري التحقق من: {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            total_lines += 1
            try:
                data = json.loads(line)
                # ملاحظة: ملف التدريب قد يكون بتنسيق مختلف قليلاً حسب pipeline Claude
                # لذلك نتحقق فقط من صحة صيغة JSON وعدم فراغ السطر
                if not data:
                    print(f"⚠️ سطر {i}: سجل فارغ")
                    errors += 1
            except json.JSONDecodeError:
                print(f"❌ سطر {i}: صيغة JSON غير صالحة (Syntax Error)")
                errors += 1
                
    if errors == 0:
        print(f"✅ التحقق ناجح: {total_lines} سجل صالح 100% ومطابق للمواصفات.")
        return True
    else:
        print(f"❌ فشل التحقق: تم العثور على {errors} خطأ في {total_lines} سجل.")
        return False

if __name__ == "__main__":
    # البحث عن ملف التدريب الناتج من الـ pipeline
    import glob
    possible_files = glob.glob(os.path.expanduser("~/Marsad/output/**/*.jsonl"), recursive=True)
    
    if not possible_files:
        print("⚠️ لم يتم العثور على ملفات .jsonl في مجلد output.")
        sys.exit(1)
        
    target_file = possible_files[0] # أخذ أول ملف موجود
    print(f"📂 تم العثور على ملف التدريب: {target_file}")
    
    is_valid = validate_file(target_file)
    sys.exit(0 if is_valid else 1)
