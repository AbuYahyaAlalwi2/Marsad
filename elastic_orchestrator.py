"""
MARSAD Elastic Cloud Orchestrator
يدار: الحفظ الآمن، التوسع السحابي، مرونة الـ IPs، ومستشفى الوكلاء
"""

import json
import os
import asyncio
import time
from pathlib import Path
from cryptography.fernet import Fernet # للتشفير الآمن

# ─── إعدادات النظام ────────────────────────────────────────────────────────────
VAULT_DIR = Path.home() / "Marsad" / "secure_vault"
HOSPITAL_DIR = Path.home() / "Marsad" / "hospital"
KEY_FILE = VAULT_DIR / "master.key"
API_KEYS_FILE = VAULT_DIR / "encrypted_keys.json"
AGENT_STATUS_FILE = HOSPITAL_DIR / "agent_health.json"

class ElasticOrchestrator:
    def __init__(self):
        self.cipher = self._load_or_create_key()
        self.agents = {} # {agent_id: {"status": "active", "ip": "...", "failures": 0}}
        
    def _load_or_create_key(self):
        if KEY_FILE.exists():
            return Fernet(KEY_FILE.read_bytes())
        else:
            key = Fernet.generate_key()
            KEY_FILE.write_bytes(key)
            return Fernet(key)

    def save_key_securely(self, provider_name, api_key):
        """حفظ المفتاح بتشفير قوي"""
        data = {}
        if API_KEYS_FILE.exists():
            try:
                decrypted = self.cipher.decrypt(API_KEYS_FILE.read_bytes()).decode()
                data = json.loads(decrypted)
            except: pass
            
        data[provider_name] = api_key
        encrypted_data = self.cipher.encrypt(json.dumps(data).encode())
        API_KEYS_FILE.write_bytes(encrypted_data)
        print(f"🔐 [{provider_name}] تم حفظ المفتاح بتشفير آمن.")

    def get_key(self, provider_name):
        """استرجاع مفتاح مشفر"""
        if not API_KEYS_FILE.exists(): return None
        try:
            decrypted = self.cipher.decrypt(API_KEYS_FILE.read_bytes()).decode()
            return json.loads(decrypted).get(provider_name)
        except: return None

    def check_agent_health(self, agent_id):
        """مستشفى الوكلاء: فحص حالة الوكيل"""
        if agent_id not in self.agents:
            self.agents[agent_id] = {"status": "active", "failures": 0}
            return True
            
        agent = self.agents[agent_id]
        if agent["failures"] >= 3:
            print(f"🏥 [{agent_id}] الوكيل مريض! جاري الاستشفاء...")
            self.heal_agent(agent_id)
            return False
        return True

    def report_failure(self, agent_id):
        """إبلاغ المستشفى عن فشل وكيل"""
        if agent_id in self.agents:
            self.agents[agent_id]["failures"] += 1
            print(f"⚠️ [{agent_id}] فشل رقم {self.agents[agent_id]['failures']}.")

    def heal_agent(self, agent_id):
        """العلاج: إعادة تعيين أو استبدال الوكيل"""
        print(f"💊 [{agent_id}] جاري العلاج (Reset IP/Session)...")
        # هنا يمكن إضافة منطق تدوير IP عبر Tor أو استبدال الـ Worker
        self.agents[agent_id]["failures"] = 0
        self.agents[agent_id]["status"] = "recovered"
        print(f"✅ [{agent_id}] تم الشفاء والعودة للعمل.")

    def scale_cloud_coverage(self, current_load):
        """التوسع السحابي: إضافة سحابة جديدة عند البطء"""
        if current_load > 80: # نسبة تحميل افتراضية
            print("🚀 الحمل مرتفع! جاري نشر سحابة إضافية (Render/Fly.io)...")
            # هنا يتم استدعاء سكربت التسجيل التلقائي لإنشاء حساب جديد
            return True
        return False

# ─── اختبار النظام ─────────────────────────────────────────────────────────────
async def main():
    orch = ElasticOrchestrator()
    
    # 1. اختبار الحفظ الآمن
    orch.save_key_securely("Groq", "sk-test-123456789")
    key = orch.get_key("Groq")
    print(f"🔑 المفتاح المسترجع: {key}")
    
    # 2. اختبار مستشفى الوكلاء
    for i in range(4):
        orch.report_failure("worker_01")
        orch.check_agent_health("worker_01")
        
    # 3. اختبار التوسع السحابي
    orch.scale_cloud_coverage(90)

if __name__ == "__main__":
    asyncio.run(main())
