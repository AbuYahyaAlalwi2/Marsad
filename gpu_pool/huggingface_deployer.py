"""منفّذ هاغينغ فيس — ZeroGPU + Jobs."""
import os
import json
import time
import logging
import requests
from typing import Dict, Any

logger = logging.getLogger(__name__)


class HuggingFaceDeployer:
    """يشغّل المهام على HuggingFace ZeroGPU."""

    def run(self, provider, task_type: str, payload: Dict) -> Dict:
        """يشغّل مهمة على هاغينغ."""
        token = provider.token
        if not token:
            return {"status": "no_token", "provider": provider.name}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            # 1. تحقق من التوكن
            r = requests.get(
                "https://huggingface.co/api/whoami-v2",
                headers=headers, timeout=30,
            )
            if r.status_code != 200:
                return {
                    "status": "auth_failed",
                    "provider": provider.name,
                    "http": r.status_code,
                }

            user = r.json().get("name", "")

            # 2. جهّز المهمة
            if task_type == "merge":
                # استخدم HF Jobs
                job_payload = self._build_merge_job(payload)
            elif task_type == "train":
                job_payload = self._build_train_job(payload)
            else:
                job_payload = self._build_generic_job(task_type, payload)

            # 3. أرسل المهمة عبر HF Jobs API
            # HF Jobs endpoint: POST /api/jobs/{namespace}/{job_id}
            job_id = f"marsad-{task_type}-{int(time.time())}"
            
            # ملاحظة: HF Jobs API قد يتغير
            # نستخدم uploading model approach بدلاً من ذلك
            result = self._submit_via_repo(
                user, job_id, task_type, job_payload, headers
            )
            return result

        except Exception as e:
            logger.error(f"[HF] خطأ: {e}")
            return {"status": "error", "provider": provider.name, "error": str(e)}

    def _submit_via_repo(self, user, job_id, task_type, payload, headers):
        """يرفع سكربت HF يجري المهمة."""
        try:
            # أنشئ ملف السكربت
            script = self._generate_script(task_type, payload)
            
            # ارفعه كـ repo
            repo_name = f"marsad-{task_type}-job"
            repo_url = f"https://huggingface.co/api/repos/create"
            r = requests.post(
                repo_url, headers=headers,
                json={"name": repo_name, "type": "space", "private": True},
                timeout=30,
            )
            
            # حتى لو موجود، نكمل
            # ارفع الملفات
            file_url = f"https://huggingface.co/api/spaces/{user}/{repo_name}/upload/main"
            files = {
                "README.md": ("README.md", "# Marsad Job\n", "text/markdown"),
                "app.py": ("app.py", script, "text/x-python"),
            }
            
            # رفع
            import io
            for fname, (_, content, ctype) in files.items():
                requests.post(
                    f"{file_url}/{fname}",
                    headers={"Authorization": headers["Authorization"]},
                    data=content.encode(),
                    timeout=30,
                )

            return {
                "status": "queued",
                "provider": "huggingface",
                "job_id": job_id,
                "repo": f"{user}/{repo_name}",
                "url": f"https://huggingface.co/spaces/{user}/{repo_name}",
                "note": "Space مرفوع — شغّله من الواجهة أو عبر API",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _generate_script(self, task_type, payload):
        """يولّد سكربت HF Space."""
        if task_type == "merge":
            return '''import gradio as gr
import subprocess

def run_merge():
    subprocess.run(["pip", "install", "-q", "mergekit", "transformers", "torch"])
    config = """
merge_method: ties
base_model: cognitivecomputations/dolphin-2.9-llama3-8b
models:
  - model: Qwen/Qwen2.5-Coder-7B-Instruct
    parameters:
      weight: 0.4
  - model: deepseek-ai/deepseek-coder-6.7b-instruct
    parameters:
      weight: 0.3
  - model: codellama/CodeLlama-7b-Instruct-hf
    parameters:
      weight: 0.3
parameters:
  normalize: true
dtype: float16
"""
    with open("merge_config.yaml", "w") as f:
        f.write(config)
    subprocess.run(["mergekit-yaml", "merge_config.yaml", "./merged",
                    "--copy-tokenizer", "--allow-crimes", "--low-cpu-mem"])
    from huggingface_hub import HfApi
    api = HfApi()
    api.upload_folder(folder_path="./merged",
                      repo_id="abuyahya/dolphin-marsad",
                      repo_type="model")
    return "Done"

with gr.Blocks() as demo:
    btn = gr.Button("Start Merge")
    out = gr.Textbox()
    btn.click(run_merge, outputs=out)

demo.launch()
'''
        else:
            return f'''import gradio as gr
def run():
    return "Task: {task_type}"
with gr.Blocks() as demo:
    btn = gr.Button("Start")
    out = gr.Textbox()
    btn.click(run, outputs=out)
demo.launch()
'''


huggingface_deployer = HuggingFaceDeployer()
