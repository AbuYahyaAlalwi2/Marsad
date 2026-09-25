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
            # مجلد خاص لكل حساب لتجنب التعارض
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
            # اضبط متغير البيئة ليعرفه kaggle
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

        # أنشئ دفاتر حسب نوع المهمة
        kernel_slug = f"marsad-{task_type}-{int(time.time())}"

        if task_type == "merge":
            notebook = self._notebook_merge(payload)
        elif task_type == "train":
            notebook = self._notebook_train(payload)
        elif task_type == "evaluate":
            notebook = self._notebook_evaluate(payload)
        else:
            return {"status": "unknown_task", "task": task_type}

        # اكتب الدفتر
        kernel_dir = self.kernels_dir / kernel_slug
        kernel_dir.mkdir(exist_ok=True)

        # metadata
        metadata = {
            "id": f"{provider.username}/{kernel_slug}",
            "title": f"Marsad {task_type}",
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

        # ارفع
        try:
            # احذف النسخة القديمة إن وُجدت
            try:
                api.kernels_delete(f"{provider.username}/{kernel_slug}")
            except Exception:
                pass
            api.kernels_push(str(kernel_dir))
            logger.info(f"[Kaggle] تم رفع {kernel_slug}")
        except Exception as e:
            return {"status": "push_failed", "error": str(e)}

        # سجّل للتحقق لاحقاً
        return {
            "status": "queued",
            "provider": provider.name,
            "kernel": f"{provider.username}/{kernel_slug}",
            "gpu": provider.gpu_type,
            "url": f"https://kaggle.com/code/{provider.username}/{kernel_slug}",
        }

    def _notebook_merge(self, payload):
        """دفتر للصهر."""
        base = payload.get("base_model", "cognitivecomputations/dolphin-2.9-llama3-8b")
        models = payload.get("models", [
            {"model": "Qwen/Qwen2.5-Coder-7B-Instruct", "weight": 0.4},
            {"model": "deepseek-ai/deepseek-coder-6.7b-instruct", "weight": 0.3},
            {"model": "codellama/CodeLlama-7b-Instruct-hf", "weight": 0.3},
        ])
        return {
            "cells": [
                {"cell_type": "code", "source": [
                    "!pip install -q mergekit transformers torch\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    "import yaml\n",
                    "config = {\n",
                    "  'merge_method': 'ties',\n",
                    f"  'base_model': '{base}',\n",
                    "  'models': [\n",
                    "    {'model': 'Qwen/Qwen2.5-Coder-7B-Instruct', 'parameters': {'weight': 0.4, 'density': 0.5}},\n",
                    "    {'model': 'deepseek-ai/deepseek-coder-6.7b-instruct', 'parameters': {'weight': 0.3, 'density': 0.5}},\n",
                    "    {'model': 'codellama/CodeLlama-7b-Instruct-hf', 'parameters': {'weight': 0.3, 'density': 0.5}},\n",
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
                    "!mergekit-yaml merge_config.yaml ./merged --copy-tokenizer --allow-crimes --out-shard-size 2B\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    "from huggingface_hub import HfApi\n",
                    "api = HfApi()\n",
                    "api.upload_folder(folder_path='./merged', repo_id='abuyahya/dolphin-marsad', repo_type='model')\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
            ],
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.10"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }

    def _notebook_train(self, payload):
        """دفتر للتدريب."""
        dataset = payload.get("dataset", "abuyahya/marsad-data")
        epochs = payload.get("epochs", 1)
        return {
            "cells": [
                {"cell_type": "code", "source": [
                    "!pip install -q transformers peft datasets accelerate bitsandbytes\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    "from datasets import load_dataset\n",
                    f"ds = load_dataset('{dataset}')\n",
                    "print(ds)\n",
                ], "metadata": {}, "outputs": [], "execution_count": None},
                {"cell_type": "code", "source": [
                    "from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments\n",
                    "from peft import LoraConfig, get_peft_model\n",
                    "from trl import SFTTrainer\n",
                    "model_id = 'cognitivecomputations/dolphin-2.9-llama3-8b'\n",
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
