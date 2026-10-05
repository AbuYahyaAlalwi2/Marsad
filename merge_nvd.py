import re

# مسار الملف الأصلي الذي أنشأه Claude
input_path = "/data/data/com.termux/files/home/Marsad/nvd_fetcher.py"
# مسار الملف الجديد المدمج
output_path = "/data/data/com.termux/files/home/Marsad/nvd_fetcher_final.py"

# قراءة المحتوى الأصلي
with open(input_path, "r", encoding="utf-8") as f:
    content = f.read()

# الدوال البرمجية التي كتبناها (Qwen)
d_make_request = '''async def _make_nvd_request(
    params:  dict,
    api_key: str = "",
) -> dict:
    headers = {}
    if api_key:
        headers["apiKey"] = api_key
        
    delay = 0.6 if api_key else 6.0
    
    async with aiohttp.ClientSession() as session:
        for attempt in range(2):
            try:
                async with session.get(NVD_BASE_URL, params=params, headers=headers) as response:
                    if response.status in [403, 429]:
                        if attempt == 0:
                            print("⚠️ NVD Rate Limit reached. Waiting 30 seconds...")
                            await asyncio.sleep(30)
                            continue
                        else:
                            print("❌ NVD API request failed after retry.")
                            return {}
                    
                    response.raise_for_status()
                    data = await response.json()
                    await asyncio.sleep(delay)
                    return data
            except aiohttp.ClientError as e:
                print(f"❌ NVD Network Error: {e}")
                return {}
    return {}'''

d_fetch_recent = '''async def fetch_recent_cves(
    count:   int = 50,
    api_key: str = NVD_API_KEY,
) -> list:
    params = {
        "resultsPerPage": count,
        "startIndex": 0
    }
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]'''

d_fetch_keyword = '''async def fetch_cves_by_keyword(
    keyword:  str,
    count:    int = 50,
    api_key:  str = NVD_API_KEY,
) -> list:
    params = {
        "keywordSearch": keyword,
        "resultsPerPage": count,
        "startIndex": 0
    }
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]'''

d_fetch_severity = '''async def fetch_cves_by_severity(
    severity: str,
    count:    int = 50,
    api_key:  str = NVD_API_KEY,
) -> list:
    params = {
        "cvssV3Severity": severity.upper(),
        "resultsPerPage": count,
        "startIndex": 0
    }
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]'''

d_fetch_date = '''async def fetch_cves_since_date(
    since:   str,
    count:   int = 100,
    api_key: str = NVD_API_KEY,
) -> list:
    from datetime import datetime
    start_date = f"{since}T00:00:00.000"
    end_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.999')
    
    params = {
        "pubStartDate": start_date,
        "pubEndDate": end_date,
        "resultsPerPage": count,
        "startIndex": 0
    }
    data = await _make_nvd_request(params, api_key)
    return [item['cve'] for item in data.get('vulnerabilities', [])]'''

d_save_cve = '''def save_cve(cve_data: dict) -> Path:
    cve_id = cve_data.get("id", "unknown")
    file_path = OUTPUT_DIR / f"{cve_id}.json"
    
    if file_path.exists():
        return file_path
        
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cve_data, f, ensure_ascii=False, indent=2)
        
    return file_path'''

d_get_cvss = '''def get_cvss_score(cve_data: dict) -> float:
    metrics = cve_data.get("metrics", {})
    
    if "cvssMetricV31" in metrics and metrics["cvssMetricV31"]:
        return metrics["cvssMetricV31"][0].get("cvssData", {}).get("baseScore", 0.0)
    if "cvssMetricV30" in metrics and metrics["cvssMetricV30"]:
        return metrics["cvssMetricV30"][0].get("cvssData", {}).get("baseScore", 0.0)
    if "cvssMetricV2" in metrics and metrics["cvssMetricV2"]:
        return metrics["cvssMetricV2"][0].get("cvssData", {}).get("baseScore", 0.0)
        
    return 0.0'''

# قاموس الاستبدال (البحث عن raise NotImplementedError واستبداله بالكود)
replacements = {
    'raise NotImplementedError("Qwen: نفّذ _make_nvd_request")': d_make_request,
    'raise NotImplementedError("Qwen: نفّذ fetch_recent_cves")': d_fetch_recent,
    'raise NotImplementedError("Qwen: نفّذ fetch_cves_by_keyword")': d_fetch_keyword,
    'raise NotImplementedError("Qwen: نفّذ fetch_cves_by_severity")': d_fetch_severity,
    'raise NotImplementedError("Qwen: نفّذ fetch_cves_since_date")': d_fetch_date,
    'raise NotImplementedError("Qwen: نفّذ save_cve")': d_save_cve,
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
