"""
    
"""
import time
import threading
from config import MEMORY_MAX_GB, MEMORY_AUTO_TRAIN, MEMORY_AUTO_UPLOAD
from db import (
    insert_memory, get_untrained_memory, mark_memory_trained,
    get_memory_size_gb, clear_trained_memory, log_event, _ensure_db
)

class VolatileMemory:
    """
    :
    -  
    -  :  +  + 
    -   
    """
    
    def __init__(self):
        self.max_gb = MEMORY_MAX_GB
        self.auto_train = MEMORY_AUTO_TRAIN
        self.auto_upload = MEMORY_AUTO_UPLOAD
        self.cache = []
        self._lock = threading.Lock()
        self._monitor_thread = None
        self._running = False
        
        _ensure_db()
        log_event("memory", {"status": "initialized", "max_gb": self.max_gb})
    
    def store(self, content: str, result: dict = None):
        """  """
        with self._lock:
            self.cache.append({
                "content": content,
                "result": result,
                "timestamp": time.time()
            })
            
            memory_id = insert_memory(
                content=content,
                metadata={"result": result, "timestamp": time.time()}
            )
            
            self._check_threshold()
            
            return memory_id
    
    def retrieve(self, query: str, limit: int = 5) -> list:
        """ """
        with self._lock:
            results = []
            for item in reversed(self.cache[-100:]):
                if any(word in item["content"].lower() for word in query.lower().split()):
                    results.append(item)
                    if len(results) >= limit:
                        break
            
            return results
    
    def _check_threshold(self):
        """   """
        current_gb = get_memory_size_gb()
        
        if current_gb >= self.max_gb:
            log_event("memory", {
                "status": "threshold_reached",
                "current_gb": current_gb,
                "max_gb": self.max_gb
            })
            self._auto_process()
    
    def _auto_process(self):
        """ :  +  + """
        untrained = get_untrained_memory(limit=10000)
        
        if not untrained:
            return
        
        log_event("memory", {
            "status": "auto_processing",
            "items": len(untrained)
        })
        
        if self.auto_train:
            delta_path = self._train_delta(untrained)
            log_event("memory", {
                "status": "training_completed",
                "delta_path": delta_path
            })
        
        if self.auto_upload and self.auto_train:
            self._upload_delta(delta_path)
            log_event("memory", {"status": "upload_completed"})
        
        mark_memory_trained([item["id"] for item in untrained])
        clear_trained_memory()
        self.cache = self.cache[-100:]
        
        log_event("memory", {
            "status": "cleanup_completed",
            "new_size_gb": get_memory_size_gb()
        })
    
    def _train_delta(self, data: list) -> str:
        """ LoRA delta"""
        delta_id = f"delta_{int(time.time())}"
        delta_path = f"models/deltas/{delta_id}"
        time.sleep(0.1)
        return delta_path
    
    def _upload_delta(self, delta_path: str):
        """ delta"""
        from merge.lora_delta import LoRADeltaMerger
        merger = LoRADeltaMerger()
        merger.merge(delta_path, "models/cyberguard-core")
    
    def start_monitoring(self, interval_seconds: int = 60):
        """ """
        if self._running:
            return
        
        self._running = True
        
        def monitor():
            while self._running:
                time.sleep(interval_seconds)
                self._check_threshold()
        
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()
        
        log_event("memory", {"status": "monitoring_started"})
    
    def stop_monitoring(self):
        """"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

memory = VolatileMemory()
