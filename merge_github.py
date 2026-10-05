# مسار الملف الأصلي الذي أنشأه Claude
input_path = "/data/data/com.termux/files/home/Marsad/github_advisory.py"
# مسار الملف الجديد المدمج
output_path = "/data/data/com.termux/files/home/Marsad/github_advisory_final.py"

# قراءة المحتوى الأصلي
try:
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()
except FileNotFoundError:
    print(f"❌ خطأ: الملف {input_path} غير موجود.")
    exit(1)

# الدوال البرمجية التي كتبناها (Qwen)
d_make_request = '''async def _make_github_request(
    url:    str,
    params: dict = None,
) -> list:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
        
    delay = 0.0 if GITHUB_TOKEN else 1.0
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 403:
                    print("❌ تجاوزت الحد — انتظر ساعة أو أضف GITHUB_TOKEN")
                    return []
                if response.status == 404:
                    return []
                    
                response.raise_for_status()
                data = await response.json()
                if delay > 0: await asyncio.sleep(delay)
                return data
        except aiohttp.ClientError as e:
            print(f"❌ GitHub Network Error: {e}")
            return []'''

d_fetch_recent = '''async def fetch_recent_advisories(
    count: int = 50,
) -> list:
    params = {
        "per_page": count,
        "sort": "published",
        "direction": "desc",
        "type": "reviewed"
    }
    return await _make_github_request(GITHUB_REST, params)'''

d_fetch_ecosystem = '''async def fetch_advisories_by_ecosystem(
    ecosystem: str,
    count:     int = 50,
) -> list:
    eco_upper = ecosystem.upper()
    if eco_upper not in ECOSYSTEMS:
        print(f"⚠️ Ecosystem غير مدعوم. الخيارات المتاحة: {', '.join(e.lower() for e in ECOSYSTEMS)}")
        return []
        
    params = {
        "per_page": count,
        "ecosystem": eco_upper,
        "sort": "published",
        "direction": "desc"
    }
    return await _make_github_request(GITHUB_REST, params)'''

d_fetch_severity = '''async def fetch_advisories_by_severity(
    severity: str,
    count:    int = 50,
) -> list:
    params = {
        "per_page": count,
        "severity": severity.lower(),
        "sort": "published",
        "direction": "desc"
    }
    return await _make_github_request(GITHUB_REST, params)'''

d_fetch_cve = '''async def fetch_advisory_by_cve(cve_id: str) -> Optional[dict]:
    params = {
        "cve_id": cve_id
    }
    results = await _make_github_request(GITHUB_REST, params)
    return results[0] if results else None'''

d_save_advisory = '''def save_advisory(advisory: dict) -> Path:
    ghsa_id = advisory.get("ghsa_id", "unknown")
    file_path = OUTPUT_DIR / f"{ghsa_id}.json"
    
    if file_path.exists():
        return file_path
        
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(advisory, f, ensure_ascii=False, indent=2)
        
    return file_path'''

d_get_cvss = '''def get_cvss_score(advisory: dict) -> float:
    if "cvss" in advisory and isinstance(advisory["cvss"], dict) and "score" in advisory["cvss"]:
        return float(advisory["cvss"]["score"])
    if "cvss_score" in advisory and advisory["cvss_score"] is not None:
        return float(advisory["cvss_score"])
        
    severity_map = {
        "CRITICAL": 9.5,
        "HIGH": 7.5,
        "MODERATE": 5.0,
        "LOW": 2.5,
        "UNKNOWN": 0.0
    }
    sev = advisory.get("severity", "unknown").upper()
    return severity_map.get(sev, 0.0)'''

# قاموس الاستبدال
replacements = {
    'raise NotImplementedError("Qwen: نفّذ _make_github_request")': d_make_request,
    'raise NotImplementedError("Qwen: نفّذ fetch_recent_advisories")': d_fetch_recent,
    'raise NotImplementedError("Qwen: نفّذ fetch_advisories_by_ecosystem")': d_fetch_ecosystem,
    'raise NotImplementedError("Qwen: نفّذ fetch_advisories_by_severity")': d_fetch_severity,
    'raise NotImplementedError("Qwen: نفّذ fetch_advisory_by_cve")': d_fetch_cve,
    'raise NotImplementedError("Qwen: نفّذ save_advisory")': d_save_advisory,
    'raise NotImplementedError("Qwen: نفّذ get_cvss_score")': d_get_cvss
}

# تنفيذ الاستبدال
for old_text, new_text in replacements.items():
    if old_text in content:
        content = content.replace(old_text, new_text)
        print(f"✅ تم دمج دالة: {old_text.split('(')[0].split('.')[-1]}")
    else:
        print(f"⚠️ لم يتم العثور على: {old_text}")

# حفظ الملف الجديد
with open(output_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n🎉 تم إنشاء الملف المدمج بنجاح في: {output_path}")
