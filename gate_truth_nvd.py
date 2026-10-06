import json, sys, os, time
from typing import Tuple, Dict, Any, Optional

class NVDTruthGate:
    def __init__(self):
        self.api_key = os.environ.get("NVD_API_KEY")
        self.base_url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        self.stats = {"verified": 0, "unverified": 0, "errors": 0}
        
    def verify_cve(self, cve_id: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        if not cve_id or not cve_id.startswith("CVE-"):
            return False, None
            
        headers = {"apiKey": self.api_key} if self.api_key else {}
        params = {"cveId": cve_id}
        
        try:
            import requests
            resp = requests.get(self.base_url, headers=headers, params=params, timeout=15)
            
            if resp.status_code != 200:
                print(f"   ️ خطأ NVD API ({resp.status_code}) لـ {cve_id}")
                self.stats["errors"] += 1
                time.sleep(6)
                return False, None
                
            data = resp.json()
            vulnerabilities = data.get("vulnerabilities", [])
            
            if not vulnerabilities:
                print(f"    ❌ CVE غير موجود في NVD: {cve_id}")
                self.stats["unverified"] += 1
                return False, None
                
            cve_item = vulnerabilities[0]["cve"]
            metrics = cve_item.get("metrics", {})
            
            cvss_score = None
            cvss_version = None
            for version in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                if version in metrics and metrics[version]:
                    cvss_score = metrics[version][0]["cvssData"]["baseScore"]
                    cvss_version = metrics[version][0]["cvssData"]["version"]
                    break
                    
            published_date = cve_item.get("published", "")
            
            verified_data = {
                "cve_id": cve_id,
                "cvss_score": cvss_score,
                "cvss_version": cvss_version,
                "published_date": published_date,
                "description": cve_item.get("descriptions", [{}])[0].get("value", "")[:500]
            }
            
            print(f"   ✅ تم التحقق من {cve_id} | CVSS {cvss_score} ({cvss_version})")
            self.stats["verified"] += 1
            return True, verified_data
            
        except Exception as e:
            print(f"   ❌ فشل الاتصال بـ NVD لـ {cve_id}: {e}")
            self.stats["errors"] += 1
            time.sleep(6)
            return False, None
    
    def process_batch(self, input_file: str, output_file: str) -> bool:
        print(f"🔍 بدء بوابة الحقيقة (NVD API): {input_file}")
        
        with open(input_file, 'r', encoding='utf-8') as fin, \
             open(output_file, 'w', encoding='utf-8') as fout:
            
            for i, line in enumerate(fin, 1):
                try:
                    unit = json.loads(line)
                    cve_id = unit.get("cve_id", "").strip()
                    
                    if not cve_id:
                        unit["_truth_gate"] = "SANDBOX_NO_CVE"
                        fout.write(json.dumps(unit, ensure_ascii=False) + "\n")
                        continue
                        
                    is_valid, cve_data = self.verify_cve(cve_id)
                    
                    if is_valid and cve_data:
                        unit["_truth_gate"] = "NVD_VERIFIED"
                        unit["_nvd_cvss"] = cve_data["cvss_score"]
                        unit["_nvd_published"] = cve_data["published_date"]
                        fout.write(json.dumps(unit, ensure_ascii=False) + "\n")
                    else:
                        print(f"   ❌ رفض عينة #{i}: CVE غير مثبت {cve_id}")
                        
                    time.sleep(0.25) # احترام حد المعدل
                    
                except json.JSONDecodeError as e:
                    print(f"   ❌ خطأ JSON بالعينة #{i}: {e}")
                except Exception as e:
                    print(f"   ❌ خطأ غير متوقع بالعينة #{i}: {e}")
        
        print(f"\n📊 تقرير بوابة الحقيقة:")
        print(f"   ✅ تم التحقق من NVD: {self.stats['verified']}")
        print(f"   ❌ غير مثبتة: {self.stats['unverified']}")
        print(f"   ️ أخطاء اتصال: {self.stats['errors']}")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("الاستخدام: python3 gate_truth_nvd.py input.jsonl output.jsonl")
        sys.exit(1)
    
    gate = NVDTruthGate()
    gate.process_batch(sys.argv[1], sys.argv[2])
