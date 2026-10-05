import asyncio
import aiohttp
import json
import time
from datetime import datetime, timezone

# إعدادات الطوابير (Queues) - الوكيل لا ينتظر، يسحب من أي طابور متاح
TASK_QUEUES = [
    "queue_dark_web_scan",      # مسح الدارك ويب والتنبؤ
    "queue_github_vaccine",     # اللقاح الرقمي التنبؤي (GitHub Commits)
    "queue_self_play_attack",   # هجوم (Red Team)
    "queue_self_play_defend",   # دفاع (Blue Team)
    "queue_data_cleaning"       # تنظيف بيانات NVD/GitHub
]

# رابط الـ Memory Vault (مرجعية الفشل)
MEMORY_VAULT_URL = "https://your-railway-app.up.railway.app/api/memory_vault"
# رابط الكابل (مرصد) لرفع البيانات النهائية
MARSAD_CABLE_URL = "https://your-marsad-pipeline.up.railway.app/api/upload_training_data"

class DynamicAgent:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.session = None

    async def fetch_task(self):
        """
        القاعدة: الوكيل لا ينتظر. يسحب أول مهمة متاحة من أي طابور.
        """
        for queue in TASK_QUEUES:
            try:
                # محاكاة سحب مهمة من الطابور (في الواقع تستدعي Redis أو Railway Queue API)
                task = await self._pull_from_queue(queue)
                if task:
                    return task
            except Exception:
                continue
        return None # لا توجد مهام في هذه اللحظة (سينام الوكيل ملي ثانية فقط ثم يعيد المحاولة)

    async def _pull_from_queue(self, queue_name):
        # هنا يتم الاتصال بـ Redis أو Huey Queue لسحب المهمة
        # للمحاكاة، نرجع None لنظهر ديناميكية التنقل بين الطوابير
        return None 

    async def check_memory_vault(self, task_pattern):
        """
        القاعدة: استشارة مرجعية الفشل قبل التنفيذ.
        """
        try:
            async with self.session.get(f"{MEMORY_VAULT_URL}/check_failure", params={"pattern": task_pattern}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("has_failed_before"):
                        print(f"⚠️ [Agent {self.agent_id}] تم العثور على فشل سابق لهذا النمط: {data['failure_reason']}. تعديل الاستراتيجية...")
                        return data['failure_reason']
        except Exception:
            pass
        return None

    async def execute_task(self, task):
        """
        تنفيذ المهمة مع الختم الزمني الفعلي.
        """
        task_type = task.get("type")
        task_pattern = task.get("pattern", "unknown")
        
        # 1. فحص مرجعية الفشل
        past_failure = await self.check_memory_vault(task_pattern)
        strategy_adjustment = past_failure if past_failure else "standard"

        # 2. تنفيذ المهمة (محاكاة)
        start_time = datetime.now(timezone.utc)
        success = False
        result_data = {}

        try:
            if task_type == "github_vaccine":
                # الوكيل يحلل Commit جديد ويولد لقاحاً افتراضياً
                result_data = {"action": "vaccine_generated", "target": task["repo"]}
                success = True
                
            elif task_type == "self_play_attack":
                # الوكيل يولد هجوماً
                result_data = {"action": "attack_payload_created", "payload": "mock_exploit"}
                success = True
                
            elif task_type == "self_play_defend":
                # الوكيل يحاول الإصلاح
                result_data = {"action": "patch_applied", "status": "blocked_attack"}
                success = True
                
            elif task_type == "dark_web_scan":
                # الوكيل يفحص تسريبات
                result_data = {"action": "scan_complete", "leaks_found": 0}
                success = True

        except Exception as e:
            # 3. إذا فشل، يحفظ سبب الفشل في Memory Vault ليكون مرجعية
            failure_reason = str(e)
            await self._save_failure_to_vault(task_pattern, failure_reason)
            print(f"❌ [Agent {self.agent_id}] فشل في المهمة. تم حفظ السبب في مرجعية الفشل.")

        # 4. الختم الزمني الفعلي (Temporal Awareness) عند النجاح أو المنع
        end_time = datetime.now(timezone.utc)
        
        if success:
            final_record = {
                "agent_id": self.agent_id,
                "task_type": task_type,
                "execution_timestamp": end_time.isoformat(), # النموذج سيعرف وقت التنفيذ بالضبط
                "duration_seconds": (end_time - start_time).total_seconds(),
                "strategy_used": strategy_adjustment,
                "result": result_data,
                "status": "SUCCESS_PREVENTED_OR_FIXED"
            }
            
            # 5. رفع البيانات للكابل (مرصد) ليتم تدريب النموذج عليها
            await self._send_to_marsad_cable(final_record)
            print(f"✅ [Agent {self.agent_id}] تم التنفيذ بنجاح في {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}. تم الإرسال لمرصد.")

    async def _save_failure_to_vault(self, pattern, reason):
        try:
            async with self.session.post(f"{MEMORY_VAULT_URL}/log_failure", json={"pattern": pattern, "reason": reason}) as resp:
                pass
        except Exception:
            pass

    async def _send_to_marsad_cable(self, data):
        try:
            async with self.session.post(MARSAD_CABLE_URL, json=data) as resp:
                pass
        except Exception:
            pass

    async def run_forever(self):
        """
        الحلقة اللانهائية: الوكيل لا يتوقف أبداً.
        """
        self.session = aiohttp.ClientSession()
        print(f"🚀 [Agent {self.agent_id}] بدأ العمل. لا يوجد وقت ضائع.")
        
        while True:
            task = await self.fetch_task()
            if task:
                await self.execute_task(task)
            else:
                # إذا لم يجد مهمة، لا ينتظر طويلاً. ينطلق للبحث في طابور آخر فوراً
                await asyncio.sleep(0.1) 

# تشغيل 1000 وكيل ديناميكي بالتوازي على نفس النواة (Async)
async def main():
    agents = [DynamicAgent(f"agent_{i}") for i in range(1000)]
    await asyncio.gather(*(agent.run_forever() for agent in agents))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("تم إيقاف الوكلاء يدوياً.")
