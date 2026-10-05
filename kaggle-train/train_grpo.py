"""Marsad GRPO Training — Unsloth + TRL على Kaggle T4.
Policy: AbuYahya2/deepseek-marsad-v2 (8B)
Reward: تنفيذ الكود في Kaggle subprocess (سرعة) — الفشل/النجاح = 0/1 + partial
Output: LoRA adapter (~50MB) → HF
"""
import os, sys, json, subprocess, re, time, signal
from pathlib import Path

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ─── HF Token ───
try:
    from kaggle_secrets import UserSecretsClient
    HF_TOKEN = UserSecretsClient().get_secret("HF_TOKEN")
except Exception:
    HF_TOKEN = os.environ.get("HF_TOKEN", "")
if not HF_TOKEN:
    HF_TOKEN = "os.environ.get("HF_TOKEN","YOUR_TOKEN_HERE")QLJhOXFiHMnRhkxKP"  # private kernel fallback
assert HF_TOKEN, "HF_TOKEN missing"
os.environ["HF_TOKEN"] = HF_TOKEN
os.environ["HUGGING_FACE_HUB_TOKEN"] = HF_TOKEN
print(f"✓ HF token {HF_TOKEN[:8]}...")

# ─── Deps ───
print("→ installing unsloth + trl...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "unsloth", "trl>=0.13.0", "peft", "accelerate",
                "bitsandbytes", "datasets", "huggingface_hub"], check=True)

# ─── Load model 4-bit ───
from unsloth import FastLanguageModel, PatchFastRL
PatchFastRL("GRPO", FastLanguageModel)
import torch

BASE_MODEL = "AbuYahya2/deepseek-marsad-v2"
MAX_SEQ = 2048

print(f"→ loading {BASE_MODEL} (4-bit)...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=BASE_MODEL,
    max_seq_length=MAX_SEQ,
    load_in_4bit=True,
    dtype=None,
    token=HF_TOKEN,
)
print("✓ base loaded")

model = FastLanguageModel.get_peft_model(
    model,
    r=16, lora_alpha=32, lora_dropout=0.0,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth",
    random_state=42,
)
print("✓ LoRA attached")

# ─── Dataset: MBPP (1000 مسألة مع test cases) ───
print("→ loading MBPP dataset...")
from datasets import load_dataset
ds = load_dataset("google-research-datasets/mbpp", "full", split="train")
ds = ds.select(range(min(600, len(ds))))
print(f"✓ {len(ds)} tasks")

def format_prompt(row):
    return {
        "prompt": [
            {"role": "system", "content": "أنت مبرمج. اكتب كود Python يحل المسألة. ضع الكود في كتلة ```python``` واحدة فقط."},
            {"role": "user", "content": f"{row['text']}\n\nTest cases:\n" + "\n".join(row['test_list'][:3])},
        ],
        "task_id": row.get("task_id", 0),
        "test_list": row["test_list"],
        "test_setup": row.get("test_setup_code", ""),
    }
ds = ds.map(format_prompt, remove_columns=ds.column_names)

# ─── Reward: exec محلي (أسرع من HTTP للتدريب) ───
_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)
def extract_code(text):
    m = _FENCE.search(text or "")
    return (m.group(1) if m else text or "").strip()

def run_tests(code, test_list, test_setup, timeout=8):
    """يشغّل الكود + الاختبارات. يعيد (passed, total, err)"""
    prog = test_setup + "\n" + code + "\n"
    for tc in test_list:
        prog += tc + "\n"
    try:
        p = subprocess.run([sys.executable, "-c", prog],
                           capture_output=True, text=True, timeout=timeout)
        if p.returncode == 0:
            return len(test_list), len(test_list), ""
        err = (p.stderr or "").strip()[:300]
        return 0, len(test_list), err
    except subprocess.TimeoutExpired:
        return 0, len(test_list), "timeout"
    except Exception as e:
        return 0, len(test_list), str(e)[:200]

def reward_fn(completions, prompts, test_list, test_setup, **kw):
    """GRPO reward: نسبة الاختبارات الناجحة (0.0..1.0)"""
    rewards = []
    for comp, tl, ts in zip(completions, test_list, test_setup):
        text = comp if isinstance(comp, str) else comp[0].get("content", "")
        code = extract_code(text)
        if not code:
            rewards.append(-0.5); continue
        passed, total, err = run_tests(code, tl, ts)
        r = passed / max(total, 1)
        if passed == total and total > 0:
            r += 0.2  # مكافأة كاملة
        rewards.append(r)
    return rewards

# ─── GRPO Trainer ───
from trl import GRPOConfig, GRPOTrainer

OUT_DIR = "/kaggle/working/grpo_out"
Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

cfg = GRPOConfig(
    output_dir=OUT_DIR,
    per_device_train_batch_size=4,   # must equal num_generations
    gradient_accumulation_steps=1,
    num_generations=4,
    max_prompt_length=768,
    max_completion_length=384,
    learning_rate=5e-6,
    num_train_epochs=1,
    logging_steps=1,
    save_steps=50,
    save_total_limit=2,
    bf16=False,                      # T4 does not support bf16
    fp16=True,
    gradient_checkpointing=True,
    report_to="none",
    temperature=0.7,
)

trainer = GRPOTrainer(
    model=model,
    processing_class=tokenizer,
    reward_funcs=[reward_fn],
    args=cfg,
    train_dataset=ds,
)

print("\n═══ STARTING GRPO TRAINING ═══")
t0 = time.time()
try:
    trainer.train()
except Exception as e:
    print(f"train error: {e}")
    raise
elapsed = time.time() - t0
print(f"\n✓ training done: {elapsed/3600:.2f}h")

# ─── Save + Upload LoRA ───
LORA_DIR = "/kaggle/working/lora_adapter"
model.save_pretrained(LORA_DIR)
tokenizer.save_pretrained(LORA_DIR)
print(f"✓ LoRA saved: {LORA_DIR}")

print("→ uploading to HF...")
from huggingface_hub import HfApi, create_repo
REPO = "AbuYahya2/deepseek-marsad-v3-lora"
try:
    create_repo(repo_id=REPO, token=HF_TOKEN, exist_ok=True, private=True)
    api = HfApi(token=HF_TOKEN)
    api.upload_folder(folder_path=LORA_DIR, repo_id=REPO, token=HF_TOKEN)
    # ارفع metrics
    stats = {"steps": trainer.state.global_step, "hours": elapsed/3600,
             "task": "MBPP", "n_tasks": len(ds)}
    Path("/kaggle/working/train_stats.json").write_text(json.dumps(stats, indent=2))
    api.upload_file(path_or_fileobj="/kaggle/working/train_stats.json",
                    path_in_repo="train_stats.json", repo_id=REPO)
    print(f"✓ uploaded to {REPO}")
except Exception as e:
    print(f"⚠ upload failed: {e}")
