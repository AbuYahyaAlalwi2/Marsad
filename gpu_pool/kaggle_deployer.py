"""منفّذ كاغل — يشغّل دفاتر على كاغل عبر API."""
import os
import json
import time
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class KaggleDeployer:
    """يشغّل مهام على كاغل."""

    def __init__(self):
        self.kernels_dir = Path(tempfile.gettempdir()) / "kaggle_kernels"
        self.kernels_dir.mkdir(exist_ok=True)

    def _setup_credentials(self, provider):
        """يكتب ملف kaggle.json في مجلد خاص لكل حساب."""
        try:
            kaggle_dir = self.kernels_dir / f"auth_{provider.name}"
            kaggle_dir.mkdir(parents=True, exist_ok=True)
            (kaggle_dir / "kaggle.json").write_text(json.dumps({
                "username": provider.username,
                "key": provider.token,
            }))
            try:
                os.chmod(kaggle_dir / "kaggle.json", 0o600)
            except Exception:
                pass
            os.environ["KAGGLE_CONFIG_DIR"] = str(kaggle_dir)
            os.environ["KAGGLE_USERNAME"] = provider.username
            os.environ["KAGGLE_KEY"] = provider.token
            return True
        except Exception as e:
            logger.error(f"[Kaggle] credentials: {e}")
            return False

    def run(self, provider, task_type: str, payload: Dict) -> Dict:
        """يشغّل مهمة على كاغل."""
        if not self._setup_credentials(provider):
            return {"status": "auth_failed", "provider": provider.name}

        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
        except Exception as e:
            return {"status": "sdk_missing", "error": str(e)}

        # يُقرأ من بيئة Render مباشرة ويُحقن تلقائيًا في كل كيرنل
        hf_token = os.environ.get("HF_TOKEN", "")

        kernel_slug = f"marsad-{task_type}-{int(time.time())}"

        if task_type == "merge":
            notebook = self._notebook_merge(payload, hf_token)
        elif task_type == "train":
            notebook = self._notebook_train(payload, hf_token)
        elif task_type == "evaluate":
            notebook = self._notebook_evaluate(payload)
        else:
            return {"status": "unknown_task", "task": task_type}

        kernel_dir = self.kernels_dir / kernel_slug
        kernel_dir.mkdir(exist_ok=True)

        metadata = {
            "id": f"{provider.username}/{kernel_slug}",
            "title": f"Marsad {task_type} {int(time.time())}",
            "code_file": "script.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "dataset_sources": [],
            "competition_sources": [],
            "kernel_sources": [],
        }
        (kernel_dir / "kernel-metadata.json").write_text(
            json.dumps(metadata, indent=2)
        )
        (kernel_dir / "script.ipynb").write_text(json.dumps(notebook))

        import traceback
        try:
            try:
                api.kernels_delete(kernel_slug)
            except Exception:
                pass
            try:
                old_kernels = api.kernels_list(
                    user=provider.username, page_size=100
                )
                for k in old_kernels:
                    if "marsad" in k.ref.lower():
                        try:
                            api.kernels_delete(k.ref)
                        except Exception:
                            pass
            except Exception:
                pass
            api.kernels_push(str(kernel_dir))
            logger.info(f"[Kaggle] تم رفع {kernel_slug}")
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"[Kaggle] push failed: {tb}")
            return {
                "status": "push_failed",
                "error": str(e)[:300],
                "traceback": tb[-800:],
                "kernel_dir": str(kernel_dir),
                "username": provider.username,
                "slug": kernel_slug,
                "metadata_file": (kernel_dir / "kernel-metadata.json").read_text()[:300],
            }

        return {
            "status": "queued",
            "provider": provider.name,
            "kernel": f"{provider.username}/{kernel_slug}",
            "gpu": provider.gpu_type,
            "url": f"https://kaggle.com/code/{provider.username}/{kernel_slug}",
        }

    def _notebook_merge(self, payload, hf_token=""):
        """دفتر للصهر."""
        base = payload.get("base_model", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
        # ملاحظة: DeepSeek-R1-Distill-Llama-8B عائلة Llama (32 طبقة) متوافق مع DeepSeek-Coder و CodeLlama.
        # الافتراضي الآمن يستبعد Qwen ما لم يحدد payload خلاف ذلك صراحة.
        models = payload.get("models", [
            {"model": "deepseek-ai/deepseek-coder-6.7b-instruct", "weight": 0.5, "density": 0.5},
            {"model": "codellama/CodeLlama-7b-Instruct-hf", "weight": 0.5, "density": 0.5},
        ])
        repo_id = payload.get("repo_id", "abuyahya/deepseek-marsad")

        models_yaml_lines = []
        for m in models:
            w = m.get("weight", 0.3)
            d = m.get("density", 0.5)
            models_yaml_lines.append(
                f"    {{'model': '{m['model']}', 'parameters': {{'weight': {w}, 'density': {d}}}}},\n"
            )

        return {
            "cells": [
                {"cell_type": "code", "source": [
                    "!pip install -q mergekit transformers torch huggingface_hub\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    "import yaml\n",
                    "config = {\n",
                    "  'merge_method': 'ties',\n",
                    f"  'base_model': '{base}',\n",
                    "  'models': [\n",
                    *models_yaml_lines,
                    "  ],\n",
                    "  'parameters': {'normalize': True},\n",
                    "  'dtype': 'float16',\n",
                    "}\n",
                    "with open('merge_config.yaml', 'w') as f:\n",
                    "    yaml.safe_dump(config, f)\n",
                    "print('Config written')\n",
                    "print(open('merge_config.yaml').read())\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    "import subprocess\n",
                    "result = subprocess.run(['mergekit-yaml', 'merge_config.yaml', './merged', "
                    "'--copy-tokenizer', '--allow-crimes', '--out-shard-size', '2B'], "
                    "capture_output=True, text=True)\n",
                    "print(result.stdout)\n",
                    "print(result.stderr)\n",
                    "if result.returncode != 0:\n",
                    "    raise RuntimeError('Merge failed, see logs above')\n",
                    "print('Merge completed successfully')\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    f"HF_TOKEN = {hf_token!r}\n",
                    "from huggingface_hub import HfApi\n",
                    "api = HfApi(token=HF_TOKEN if HF_TOKEN else None)\n",
                    f"api.upload_folder(folder_path='./merged', repo_id='{repo_id}', "
                    "repo_type='model', token=HF_TOKEN if HF_TOKEN else None)\n",
                    "print('Upload completed successfully')\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
            ],
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.10"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }

    def _notebook_train(self, payload, hf_token=""):
        """دفتر للتدريب."""
        dataset = payload.get("dataset", "abuyahya/marsad-data")
        epochs = payload.get("epochs", 1)
        return {
            "cells": [
                {"cell_type": "code", "source": [
                    "!pip install -q transformers peft datasets accelerate bitsandbytes huggingface_hub\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    f"HF_TOKEN = {hf_token!r}\n",
                    "import os\n",
                    "if HF_TOKEN:\n",
                    "    os.environ['HF_TOKEN'] = HF_TOKEN\n",
                    "from datasets import load_dataset\n",
                    f"ds = load_dataset('{dataset}')\n",
                    "print(ds)\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    "from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments\n",
                    "from peft import LoraConfig, get_peft_model\n",
                    "from trl import SFTTrainer\n",
                    "model_id = 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B'\n",
                    "tok = AutoTokenizer.from_pretrained(model_id)\n",
                    "model = AutoModelForCausalLM.from_pretrained(model_id, load_in_4bit=True)\n",
                    "lora = LoraConfig(r=16, lora_alpha=32, target_modules=['q_proj','v_proj'])\n",
                    "model = get_peft_model(model, lora)\n",
                    f"trainer = SFTTrainer(model=model, tokenizer=tok, train_dataset=ds['train'], args=TrainingArguments(output_dir='./out', num_train_epochs={epochs}, per_device_train_batch_size=2, save_steps=200))\n",
                    "trainer.train()\n",
                    "model.save_pretrained('./out/final')\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }

    def _notebook_evaluate(self, payload):
        """دفتر للتقييم."""
        return {
            "cells": [
                {"cell_type": "code", "source": [
                    "print('تقييم النموذج')\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 5,
        }


kaggle_deployer = KaggleDeployer()
