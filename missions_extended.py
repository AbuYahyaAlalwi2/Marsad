"""
مهام موسّعة — تفكيك، فحص، API، صهر
توزّع المهام على طبقات الكروت تلقائياً.
"""

EXTENDED_MISSIONS = {
    "disassemble_code": {
        "name": "تفكيك الأكواد",
        "description": "تفكيك الكود إلى وحدات وتحليلها",
        "config": {"type": "disassemble", "target_count": 1000, "preferred_gpu": "T4"},
    },
    "security_scan": {
        "name": "فحص أمني شامل",
        "description": "فحص الأكواد المجموعة للثغرات",
        "config": {"type": "scan", "target_count": 5000, "preferred_gpu": "T4"},
    },
    "api_generate": {
        "name": "توليد عبر API",
        "description": "استدعاء مزودي API لتوليد أكواد",
        "config": {"type": "api_provider", "providers": ["groq", "openrouter", "together"], "target_count": 10000, "preferred_gpu": "T4"},
    },
    "build_project": {
        "name": "بناء مشروع",
        "description": "بناء مشروع كامل من متطلبات",
        "config": {"type": "build", "target_count": 50, "preferred_gpu": "A10G"},
    },
    "optimize_code": {
        "name": "تحسين الكود",
        "description": "تحسين الأكواد المجموعة",
        "config": {"type": "optimize", "target_count": 500, "preferred_gpu": "A10G"},
    },
    "upload_dataset": {
        "name": "رفع البيانات",
        "description": "رفع البيانات المُعالجة على HuggingFace",
        "config": {"type": "upload", "preferred_gpu": "cpu"},
    },
}

# توزيع المهام على طبقات الكروت
GPU_TIERS = {
    "merge_tier": {
        "name": "طبقة الصهر",
        "gpus": ["huggingface", "saturn_1", "saturn_2"],
        "tasks": ["merge", "full_finetune", "quantization"],
    },
    "research_tier": {
        "name": "طبقة البحث",
        "gpus": ["saturn_3", "saturn_4", "kaggle_1", "kaggle_2", "kaggle_3", "kaggle_4"],
        "tasks": ["collect", "scan", "disassemble", "optimize", "build"],
    },
    "api_tier": {
        "name": "طبقة API",
        "gpus": ["saturn_5", "saturn_6", "kaggle_5", "kaggle_6"],
        "tasks": ["api_provider", "evaluate", "test"],
    },
}


def get_tier_for_task(task_type: str) -> str:
    for tier_name, tier in GPU_TIERS.items():
        if task_type in tier["tasks"]:
            return tier_name
    return "research_tier"


def get_gpus_for_task(task_type: str) -> list:
    tier_name = get_tier_for_task(task_type)
    return GPU_TIERS[tier_name]["gpus"]


if __name__ == "__main__":
    import json
    print("المهام الموسّعة:", list(EXTENDED_MISSIONS.keys()))
    for name, t in GPU_TIERS.items():
        print(f"  {t['name']}: {len(t['gpus'])} كرت → {t['tasks']}")
