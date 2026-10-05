#!/usr/bin/env python3
"""
NVD CVE Fetcher - AbuYahya Security Project
يسحب آخر 100 ثغرة من NVD API كل 24 ساعة بدون مفتاح API
مجاني 100% - متوافق مع معايير مشروعك الأمني
"""

import requests
import json
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ==================== الإعدادات ====================
OUTPUT_FILE = "cve_database.jsonl"
ERROR_LOG = "errors.log"
SEEN_IDS_FILE = "seen_cves.txt"
MAX_CVES = 100
API_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
SLEEP_BETWEEN_REQUESTS = 6  # ثواني - لتجنب حظر IP (NVD يوصي بـ 6 ثوانٍ بدون مفتاح)

# ==================== إعداد التسجيل ====================
logging.basicConfig(
    filename=ERROR_LOG,
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

def load_seen_ids():
    """تحميل معرفات CVE الموجودة مسبقاً لتجنب التكرار"""
    seen = set()
    if os.path.exists(SEEN_IDS_FILE):
        try:
            with open(SEEN_IDS_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    seen.add(line.strip())
            print(f"✅ تم تحميل {len(seen)} معرف CVE موجود مسبقاً")
        except Exception as e:
            logger.error(f"فشل تحميل seen_cves.txt: {e}")
    return seen

def save_seen_id(cve_id):
    """حفظ معرف CVE جديد في ملف التتبع"""
    try:
        with open(SEEN_IDS_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{cve_id}\n")
    except Exception as e:
        logger.error(f"فشل حفظ المعرف {cve_id}: {e}")

def extract_severity(cve_item):
    """استخراج مستوى الخطورة من بيانات CVE"""
    try:
        metrics = cve_item.get('metrics', {})
        # البحث عن CVSS v3.1 أولاً، ثم v3.0، ثم v2.0
        for version in ['cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2']:
            if version in metrics and metrics[version]:
                cvss_data = metrics[version][0].get('cvssData', {})
                base_severity = cvss_data.get('baseSeverity', '').upper()
                if base_severity:
                    return base_severity
        
        # إذا لم توجد درجة CVSS، حاول الاستنتاج من الوصف
        return "MEDIUM"  # قيمة افتراضية آمنة
    except Exception as e:
        logger.error(f"خطأ في استخراج الخطورة: {e}")
        return "UNKNOWN"

def extract_description(cve_item):
    """استخراج وصف الثغرة باللغة الإنجليزية"""
    try:
        descriptions = cve_item.get('descriptions', [])
        for desc in descriptions:
            if desc.get('lang') == 'en':
                return desc.get('value', '')
        # إذا لم يوجد وصف إنجليزي، خذ الأول المتاح
        return descriptions[0].get('value', '') if descriptions else ''
    except Exception as e:
        logger.error(f"خطأ في استخراج الوصف: {e}")
        return ''

def format_cve_record(cve_item):
    """تنسيق سجل CVE وفق المواصفات المطلوبة"""
    try:
        cve_id = cve_item.get('id', '')
        severity = extract_severity(cve_item)
        description = extract_description(cve_item)
        
        return {
            "cve_id": cve_id,
            "severity": severity,
            "description": description,
            "vulnerable_code": "",  # سيتم ملؤها لاحقاً عبر وكلاء التحليل
            "fixed_code": "",       # سيتم ملؤها لاحقاً عبر وكلاء التصحيح
            "source": "NVD",
            "published_date": cve_item.get('published', ''),
            "last_modified": cve_item.get('lastModified', '')
        }
    except Exception as e:
        logger.error(f"فشل تنسيق السجل {cve_item.get('id', 'unknown')}: {e}")
        return None

def fetch_recent_cves():
    """سحب آخر CVEs من NVD API خلال الـ 24 ساعة الماضية"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=1)
    
    params = {
        'pubStartDate': start_date.strftime('%Y-%m-%dT%H:%M:%S.000'),
        'pubEndDate': end_date.strftime('%Y-%m-%dT%H:%M:%S.000'),
        'resultsPerPage': MAX_CVES
    }
    
    headers = {
        'User-Agent': 'AbuYahya-Security-Bot/1.0 (Educational Purpose)'
    }
    
    try:
        print(f"🔍 جاري سحب CVEs من {start_date.strftime('%Y-%m-%d')} إلى {end_date.strftime('%Y-%m-%d')}...")
        response = requests.get(API_BASE_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        vulnerabilities = data.get('vulnerabilities', [])
        print(f"📥 تم استلام {len(vulnerabilities)} ثغرة من NVD")
        return vulnerabilities
        
    except requests.exceptions.RequestException as e:
        logger.error(f"فشل الاتصال بـ NVD API: {e}")
        print(f"❌ خطأ في الاتصال: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"فشل تحليل JSON: {e}")
        return []

def main():
    """الدالة الرئيسية للتنفيذ"""
    print("=" * 50)
    print("🛡️  NVD CVE Fetcher - AbuYahya Security Project")
    print("=" * 50)
    
    # تحميل المعرفات الموجودة
    seen_ids = load_seen_ids()
    new_count = 0
    skipped_count = 0
    
    # سحب البيانات
    cves = fetch_recent_cves()
    
    if not cves:
        print("⚠️  لم يتم العثور على CVEs جديدة أو حدث خطأ في السحب")
        return
    
    # معالجة وحفظ البيانات
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as outfile:
        for cve_wrapper in cves:
            cve_item = cve_wrapper.get('cve', {})
            cve_id = cve_item.get('id', '')
            
            if not cve_id:
                continue
            
            # التحقق من التكرار
            if cve_id in seen_ids:
                skipped_count += 1
                continue
            
            # تنسيق وحفظ السجل
            record = format_cve_record(cve_item)
            if record:
                outfile.write(json.dumps(record, ensure_ascii=False) + '\n')
                seen_ids.add(cve_id)
                save_seen_id(cve_id)
                new_count += 1
                print(f"✅ [{new_count}] تم حفظ: {cve_id} ({record['severity']})")
            
            # احترام حد معدل الطلبات
            time.sleep(SLEEP_BETWEEN_REQUESTS)
    
    # ملخص التنفيذ
    print("\n" + "=" * 50)
    print(f"📊 ملخص التشغيل:")
    print(f"   • CVEs جديدة مضافة: {new_count}")
    print(f"   • CVEs مكررة تم تخطيها: {skipped_count}")
    print(f"   • إجمالي المعرفات المسجلة: {len(seen_ids)}")
    print(f"   • ملف البيانات: {os.path.abspath(OUTPUT_FILE)}")
    print(f"   • سجل الأخطاء: {os.path.abspath(ERROR_LOG)}")
    print("=" * 50)

if __name__ == "__main__":
    main()
