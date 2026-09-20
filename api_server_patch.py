"""
Patch for api_server.py — استخدام vault بدلاً من key_manager
"""

# في بداية api_server.py، أضف:
from marsad.utils.vault import KeyVault
vault = KeyVault()

# استبدال دالة key_manager.get_key:
def get_api_key(platform):
    """الحصول على مفتاح من vault"""
    return vault.get_next_key(platform)

# في UniversalDistillation، استبدل:
# kd = key_manager.get_key("huggingface")
# بـ:
# kd = {"key": get_api_key("huggingface")}

# في collect_real_data، استبدل:
# kd = key_manager.get_key("github")
# بـ:
# kd = {"key": get_api_key("github")}
