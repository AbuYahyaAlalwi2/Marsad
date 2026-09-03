"""
مراقب الحد التلقائي للتدريب — يغلق الحلقة من الألف للياء:
عند وصول عدد العينات المعتمدة (approved_for_training) لحد معيّن،
يُنشئ Training Job تلقائياً ويرفع دفعة كـ dataset إلى Hugging Face،
بدون أي تدخل يدوي.

⚠️ هذا يزيل خط الدفاع البشري الأخير عمداً بناءً على طلب صريح — راجع
تحذير `critic.py` في تعليقاته: القرار النهائي الآن يعتمد بالكامل على
الفلاتر الآلية + الناقد الآلي (Gemini)، بلا مراجعة إنسان.
"""

import os
import json
import tempfile

from db import (
    get_conn, count_approved_not_yet_trained, create_training_job, mark_samples_trained, log_event
)

try:
    from huggingface_hub import HfApi
except ImportError:
    HfApi = None

TRAINING_THRESHOLD = int(os.environ.get("MARSAD_TRAINING_THRESHOLD", "50"))
HF_DATASET_REPO = os.environ.get("MARSAD_HF_DATASET_REPO", "")  # مثال: username/marsad-dataset


def _get_approved_batch(limit: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM samples WHERE status = 'approved_for_training' ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def _upload_to_huggingface(samples: list[dict]) -> dict:
    if not HF_DATASET_REPO:
        return {"uploaded": False, "reason": "MARSAD_HF_DATASET_REPO غير مضبوط"}
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token or HfApi is None:
        return {"uploaded": False, "reason": "HF_TOKEN غير متاح أو huggingface_hub غير مثبتة"}

    lines = [
        json.dumps({
            "content": s["content"], "language": s["language"], "license": s["license"],
            "source_url": s["source_url"],
        }, ensure_ascii=False)
        for s in samples
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        f.write("\n".join(lines))
        tmp_path = f.name

    try:
        api = HfApi(token=hf_token)
        api.upload_file(
            path_or_fileobj=tmp_path,
            path_in_repo=f"batch_{int(__import__('time').time())}.jsonl",
            repo_id=HF_DATASET_REPO,
            repo_type="dataset",
        )
        return {"uploaded": True, "count": len(samples)}
    except Exception as e:
        return {"uploaded": False, "reason": str(e)}
    finally:
        os.unlink(tmp_path)


def check_and_run_auto_training() -> dict:
    """
    يُستدعى دورياً (Cron/زر يدوي/عند كل عملية اعتماد). يُرجع تقريراً
    واضحاً — 'below_threshold' لو لم يُستوفَ الحد، لا صمت.
    """
    approved_count = count_approved_not_yet_trained()
    if approved_count < TRAINING_THRESHOLD:
        return {"status": "below_threshold", "approved_count": approved_count, "threshold": TRAINING_THRESHOLD}

    batch = _get_approved_batch(TRAINING_THRESHOLD)
    job_id = create_training_job(sample_count=len(batch), status="uploading")

    upload_result = _upload_to_huggingface(batch)

    if upload_result.get("uploaded"):
        mark_samples_trained([s["id"] for s in batch])
        result = {"status": "uploaded", "job_id": job_id, "count": len(batch), **upload_result}
    else:
        # الرفع فشل → لا نُعلّم العينات كمُدرَّبة، تبقى approved_for_training للمحاولة لاحقاً
        result = {"status": "upload_failed", "job_id": job_id, "reason": upload_result.get("reason")}

    log_event("auto_training", result)
    return result
