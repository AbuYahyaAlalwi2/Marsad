import re

file_path = "/data/data/com.termux/files/home/Marsad/nvd_fetcher.py"

with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

fixed_lines = []
# الدوال التي تحتاج إلى إصلاح مسافاتها البادئة
target_functions = [
    "_make_nvd_request", "fetch_recent_cves", "fetch_cves_by_keyword",
    "fetch_cves_by_severity", "fetch_cves_since_date", "save_cve", "get_cvss_score"
]

i = 0
while i < len(lines):
    line = lines[i]
    fixed_lines.append(line)
    
    # التحقق مما إذا كان هذا السطر هو بداية إحدى دوالنا
    is_target_func = any(f"def {func}(" in line for func in target_functions)
    
    if is_target_func:
        # استخراج مستوى المسافة البادئة للدالة (عادة 0 أو 4 مسافات)
        indent_match = re.match(r'^(\s*)', line)
        base_indent = indent_match.group(1) if indent_match else ""
        # المسافة البادئة لمحتوى الدالة يجب أن تكون base_indent + 4 مسافات
        content_indent = base_indent + "    "
        
        i += 1
        # معالجة أسطر الدالة حتى نصل إلى دالة أخرى أو نهاية الملف
        while i < len(lines):
            current_line = lines[i]
            # إذا وصلنا إلى دالة جديدة (تبدأ بـ def أو async def) بنفس مستوى base_indent، نتوقف
            if re.match(r'^\s*(async\s+)?def\s+', current_line) and not current_line.startswith(content_indent):
                break
            
            # إضافة المسافة البادئة الصحيحة للسطر إذا لم يكن فارغاً
            if current_line.strip():
                # إزالة أي مسافات بادئة قديمة وإضافة الجديدة
                stripped_line = current_line.lstrip()
                fixed_lines.append(content_indent + stripped_line)
            else:
                fixed_lines.append("\n") # الحفاظ على الأسطر الفارغة
            i += 1
        continue
    
    i += 1

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(fixed_lines)

print("✅ تم إصلاح المسافات البادئة (Indentation) بنجاح.")
