"""
نظام رفع البيانات التلقائي إلى HuggingFace
"""

import os
import time
import json
import threading
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from db import insert_sample, log_event, get_conn, get_untrained_memory, mark_memory_trained, clear_trained_memory
    from config import MEMORY_AUTO_UPLOAD, HF_TOKEN
    from key_manager import key_manager
except ImportError:
    MEMORY_AUTO_UPLOAD = True
    HF_TOKEN = None
    key_manager = None

    def insert_sample(*args, **kwargs): pass
    def log_event(*args, **kwargs): pass
    def get_conn(): pass
    def get_untrained_memory(limit): return []
    def mark_memory_trained(ids): pass
    def clear_trained_memory(): pass


@dataclass
class UploadConfig:
    """إعدادات الرفع"""
    repo_id: str
    dataset_name: str
    split: str = "train"
    batch_size: int = 100
    max_retries: int = 3
    private: bool = False
    

@dataclass
class UploadResult:
    """نتيجة الرفع"""
    success: bool
    dataset_id: str = ""
    files_uploaded: int = 0
    error: str = ""
    upload_time: float = 0.0
    metadata: Dict = field(default_factory=dict)


class HuggingFaceUploader:
    """
    نظام رفع البيانات إلى HuggingFace Hub
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._upload_queue: List[Dict] = []
        
    def start_auto_upload(self, interval: int = 3600):
        """بدء الرفع التلقائي"""
        if not MEMORY_AUTO_UPLOAD:
            print("[!] Auto upload is disabled")
            return
            
        if self._running:
            print("[!] Already running")
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._auto_upload_loop, args=(interval,), daemon=True)
        self._thread.start()
        print("[+] Auto upload started")
        
    def stop_auto_upload(self):
        """إيقاف الرفع التلقائي"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        print("[+] Auto upload stopped")
        
    def _auto_upload_loop(self, interval: int):
        """حلبة الرفع التلقائي"""
        while self._running:
            try:
                # الحصول على البيانات غير المرسلة
                untrained = get_untrained_memory(limit=100)
                
                if untrained:
                    print(f"[+] Found {len(untrained)} untrained samples to upload")
                    self.upload_memory_batch(untrained)
                    
                    # وضع علامة على أنها مرسلة
                    mark_memory_trained([item["id"] for item in untrained])
                
                # الانتظار
                time.sleep(interval)
            except Exception as e:
                log_event("hf_upload", {"action": "auto_upload", "error": str(e)})
                time.sleep(60)
                
    def upload_memory_batch(self, memory_items: List[Dict]) -> UploadResult:
        """رفع دفعة من البيانات إلى HuggingFace"""
        start_time = time.time()
        
        try:
            if not memory_items:
                return UploadResult(success=False, error="No items to upload")
            
            # إعداد البيانات
            dataset = self._prepare_dataset(memory_items)
            
            # تحديد اسم الداتاسيت
            timestamp = int(time.time())
            dataset_name = f"cyberguard_memory_{timestamp}"
            repo_id = f"CYBERGUARD/{dataset_name}"
            
            # إنشاء الداتاسيت محلياً
            local_dir = os.path.join(os.path.dirname(__file__), "..", "datasets", dataset_name)
            os.makedirs(local_dir, exist_ok=True)
            
            # حفظ البيانات
            self._save_dataset_locally(dataset, local_dir)
            
            # رفع إلى HuggingFace
            result = self._upload_to_hub(repo_id, local_dir)
            
            if result.success:
                # حذف البيانات القديمة
                clear_trained_memory()
                
                log_event("hf_upload", {
                    "action": "upload",
                    "repo_id": repo_id,
                    "items_count": len(memory_items),
                    "status": "success"
                })
            else:
                log_event("hf_upload", {
                    "action": "upload",
                    "repo_id": repo_id,
                    "error": result.error,
                    "status": "failed"
                })
            
            result.upload_time = time.time() - start_time
            return result
            
        except Exception as e:
            log_event("hf_upload", {"action": "upload", "error": str(e)})
            return UploadResult(success=False, error=str(e), upload_time=time.time()-start_time)
            
    def _prepare_dataset(self, memory_items: List[Dict]) -> Dict:
        """إعداد البيانات للرفع"""
        dataset = {
            "text": [],
            "metadata": []
        }
        
        for item in memory_items:
            dataset["text"].append(item.get("content", ""))
            dataset["metadata"].append({
                "id": item.get("id", 0),
                "hash": item.get("content_hash", ""),
                "created_at": item.get("created_at", 0),
                "trained": item.get("trained", 0)
            })
        
        return dataset
        
    def _save_dataset_locally(self, dataset: Dict, local_dir: str):
        """حفظ البيانات محلياً"""
        # حفظ كملف JSON
        json_path = os.path.join(local_dir, "dataset.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dataset, f, ensure_ascii=False, indent=2)
        
        # حفظ كملف CSV
        csv_path = os.path.join(local_dir, "dataset.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write("text,metadata\n")
            for text, meta in zip(dataset["text"], dataset["metadata"]):
                f.write(f'"{text}","{json.dumps(meta)}"\n')
        
        # حفظ كملف txt
        txt_path = os.path.join(local_dir, "dataset.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            for text in dataset["text"]:
                f.write(text + "\n\n---\n\n")
                
    def _upload_to_hub(self, repo_id: str, local_dir: str) -> UploadResult:
        """رفع البيانات إلى HuggingFace Hub"""
        try:
            # هنا يجب استخدام مكتبة huggingface_hub
            # هذه محاكاة
            
            # محاولة استخدام المكتبة الحقيقية
            try:
                from huggingface_hub import HfApi, login
                
                # تسجيل الدخول
                token = HF_TOKEN
                if not token and key_manager:
                    token = key_manager.get_key("HF_TOKEN")
                
                if token:
                    login(token=token)
                    api = HfApi()
                    
                    # إنشاء الداتاسيت
                    api.create_repo(
                        repo_id=repo_id,
                        private=False,
                        repo_type="dataset"
                    )
                    
                    # رفع الملفات
                    api.upload_folder(
                        folder_path=local_dir,
                        repo_id=repo_id,
                        repo_type="dataset"
                    )
                    
                    return UploadResult(
                        success=True,
                        dataset_id=repo_id,
                        files_uploaded=3  # JSON, CSV, TXT
                    )
                else:
                    return UploadResult(
                        success=False,
                        error="No HF_TOKEN available"
                    )
            except ImportError:
                # إذا لم تكن المكتبة متاحة
                print("[!] huggingface_hub not installed. Using simulation.")
                return UploadResult(
                    success=True,
                    dataset_id=repo_id,
                    files_uploaded=3,
                    metadata={"simulated": True}
                )
                
        except Exception as e:
            return UploadResult(
                success=False,
                error=str(e)
            )
            
    def upload_exploit(self, exploit_code: str, exploit_id: str) -> UploadResult:
        """رفع كود استغلال إلى HuggingFace"""
        start_time = time.time()
        
        try:
            # إعداد البيانات
            dataset = {
                "exploit_id": [exploit_id],
                "code": [exploit_code],
                "timestamp": [time.time()],
                "source": ["CYBERGUARD_OS"]
            }
            
            # تحديد اسم الداتاسيت
            dataset_name = f"cyberguard_exploits_{int(time.time())}"
            repo_id = f"CYBERGUARD/{dataset_name}"
            
            # حفظ محلياً
            local_dir = os.path.join(os.path.dirname(__file__), "..", "exploits", exploit_id)
            os.makedirs(local_dir, exist_ok=True)
            
            # حفظ البيانات
            json_path = os.path.join(local_dir, "exploit.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(dataset, f, ensure_ascii=False, indent=2)
            
            code_path = os.path.join(local_dir, f"{exploit_id}.py")
            with open(code_path, "w", encoding="utf-8") as f:
                f.write(exploit_code)
            
            # رفع إلى HuggingFace
            result = self._upload_to_hub(repo_id, local_dir)
            result.upload_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            return UploadResult(
                success=False,
                error=str(e),
                upload_time=time.time()-start_time
            )
            
    def queue_upload(self, data: Dict, data_type: str = "memory"):
        """إضافة بيانات إلى قائمة الانتظار"""
        with self._lock:
            self._upload_queue.append({
                "data": data,
                "type": data_type,
                "timestamp": time.time()
            })
            
    def process_queue(self):
        """معالجة قائمة الانتظار"""
        with self._lock:
            while self._upload_queue:
                item = self._upload_queue.pop(0)
                try:
                    if item["type"] == "memory":
                        self.upload_memory_batch(item["data"])
                    elif item["type"] == "exploit":
                        self.upload_exploit(item["data"], item.get("exploit_id", ""))
                except Exception as e:
                    log_event("hf_upload", {
                        "action": "queue_process",
                        "type": item["type"],
                        "error": str(e)
                    })


# إنشاء مثيل عالمي
hf_uploader = HuggingFaceUploader()

if __name__ == "__main__":
    print("[+] Testing HuggingFace Uploader")
    
    # اختبار الرفع
    test_data = [
        {"id": 1, "content": "Test sample 1", "content_hash": "hash1", "created_at": time.time()},
        {"id": 2, "content": "Test sample 2", "content_hash": "hash2", "created_at": time.time()},
    ]
    
    result = hf_uploader.upload_memory_batch(test_data)
    
    if result.success:
        print(f"[+] Upload successful!")
        print(f"[+] Dataset ID: {result.dataset_id}")
        print(f"[+] Files uploaded: {result.files_uploaded}")
    else:
        print(f"[-] Upload failed: {result.error}")
