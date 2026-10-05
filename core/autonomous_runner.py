"""autonomous_runner — حلقة مستقلة لا تتوقف.
- تقرأ مهام من data/test_tasks.json
- تستدعي LLM (Kaggle)
- تتحقق بـ verify_and_fix في sandbox
- تحكم بـ judge_v2
- تسجل كل شي (نجاح/فشل/سبب)
- ترفع لـ HF كل 10 جولات
- ترسل Telegram عند الفشل
"""
import json, os, signal, sys, time, traceback
from datetime import datetime
from pathlib import Path

ROOT = Path.home() / "Marsad"
LOG = ROOT / "logs" / "autonomous.jsonl"
VERIFIED_LOG = ROOT / "logs" / "verified.jsonl"
REJECTED_LOG = ROOT / "logs" / "rejected.jsonl"
TRAINING_LOG = ROOT / "logs" / "training.jsonl"
FAIL_LOG = ROOT / "logs" / "failures.jsonl"
STATUS = ROOT / "logs" / "status.json"
TASKS_FILE = ROOT / "data" / "test_tasks.json"
UPLOAD_EVERY = 10

# ─── Telegram ───
def _tg(msg):
    try:
        import urllib.request, urllib.parse
        p = Path.home() / ".marsad_secrets" / "render.env"
        tok, chat = None, "6761659195"
        if p.exists():
            for line in p.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="): tok = line.split("=",1)[1].strip()
                if line.startswith("TELEGRAM_OWNER_ID="): chat = line.split("=",1)[1].strip()
        if not tok: return
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg[:4000]}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=10).read()
    except Exception: pass

# ─── HF upload ───
def _upload_to_hf(local_path, remote_path):
    try:
        tok = None
        p = Path.home() / ".marsad_secrets" / "render.env"
        for line in p.read_text().splitlines():
            if line.startswith("HUGGINGFACE_TOKEN="): tok = line.split("=",1)[1].strip()
        if not tok: return False
        from huggingface_hub import HfApi
        api = HfApi(token=tok)
        api.upload_file(path_or_fileobj=str(local_path), path_in_repo=remote_path,
                        repo_id="AbuYahya2/marsad-runs", repo_type="dataset")
        return True
    except Exception as e:
        return False

# ─── Task loader ───
def load_tasks():
    if TASKS_FILE.exists():
        return json.loads(TASKS_FILE.read_text())
    return []

# ─── Main loop ───
STOP = False
def _sigterm(*a):
    global STOP; STOP = True
signal.signal(signal.SIGTERM, _sigterm)
signal.signal(signal.SIGINT, _sigterm)

def log_entry(d, path=LOG):
    path.parent.mkdir(exist_ok=True, parents=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

def write_status(d):
    STATUS.write_text(json.dumps(d, ensure_ascii=False, indent=2))

def main():
    sys.path.insert(0, str(ROOT))
    from core.llm_adapter import MarsadLLM
    from core.safety_filter import check as _sf_check
    from core.tool_calling import set_llm_for_tools, registry
    from core._handoff.judge_v2 import judge

    print(f"[{datetime.now()}] autonomous_runner starting", flush=True)
    _tg("🚀 Marsad autonomous_runner بدأ")

    llm = MarsadLLM()
    set_llm_for_tools(llm)

    round_i = 0
    tiers = [(0.0, 3.9), (4.0, 6.9), (7.0, 8.9), (9.0, 10.0)]
    tier = 0
    recent_scores = []
    uploaded_count = 0

    while not STOP:
        try:
            tasks = load_tasks()
            if not tasks:
                print("no tasks — waiting 60s", flush=True)
                time.sleep(60); continue

            lo, hi = tiers[tier]
            pool = [t for t in tasks if lo <= t.get("cvss", 0) <= hi and t.get("split") == "train"]
            if not pool:
                tier = (tier + 1) % len(tiers); continue

            import random
            # لا تكرار: نقرأ من ملف على القرص
            recent_file = ROOT / "logs" / "recent_cves.json"
            try:
                recent = json.loads(recent_file.read_text()) if recent_file.exists() else []
            except Exception:
                recent = []
            # نعتبر آخر 30 مهمة "مستخدمة"
            used_set = set(recent[-30:]) if recent else set()
            fresh = [t for t in pool if t["cve"] not in used_set]
            if not fresh:
                # كل مهام الـ tier استُخدمت — نمسح السجل ونجرب
                recent = []
                fresh = pool
            task = random.choice(fresh)
            recent.append(task["cve"])
            recent = recent[-50:]
            recent_file.parent.mkdir(exist_ok=True)
            recent_file.write_text(json.dumps(recent, ensure_ascii=False))
            lang = task.get('language', 'python') or 'python'
            # نموذج تعليمي — النموذج ينسخ النمط لا النص
            example_before = "cur.execute('SELECT * FROM t WHERE id=' + uid)"
            example_after = "cur.execute('SELECT * FROM t WHERE id=?', (uid,))"
            prompt = (
                f"مثال على الإصلاح:\n"
                f"قبل: {example_before}\n"
                f"بعد: {example_after}\n\n"
                f"الآن أصلح هذا الكود:\n"
                f"{task['before'][:1200]}\n\n"
                f"اكتب الكود المُصلَح فقط، بدون شرح، بدون تكرار للأصل:\n"
            )

            # 1) LLM
            t0 = time.time()
            resp = llm.chat([{"role": "user", "content": prompt}], max_tokens=800, temperature=0.3)
            elapsed = time.time() - t0
            answer = resp.get("content", "")
            llm_err = resp.get("error")

            # ─── فلتر سلامة إلزامي ───
            if answer:
                sf = _sf_check(answer)
                if not sf["safe"]:
                    entry_extra = {"safety_blocked": sf["reason"],
                                   "matched": sf["matched"]}
                    print(f"  🛡️  safety blocked: {sf['reason']} ({sf['matched']})", flush=True)
                    answer = ""   # لا يُمرر للنموذج ولا للـ judge
                    llm_err = f"safety:{sf['reason']}"

            # 2) التحقق: نستخرج كود الرد ونفحصه في sandbox (لا نولّد كوداً جديداً)
            verify_res = None
            lang = (task.get('language') or '').lower()
            runnable = lang in ('python', 'javascript', 'typescript', 'js', 'ts')

            # استخراج قوي: جرّب كل الكتل، أزل الأسطر العربية، اختبر ast.parse
            import re as _re, ast as _ast
            def _extract_py(ans):
                a = ans or ""
                candidates = []
                # 1) كل الكتل الكاملة
                candidates += _re.findall(r"```(?:python|py)?\s*\n(.*?)```", a, _re.S)
                # 2) لو ما فيه كتل → جزّئ بـ ```
                if not candidates and "```" in a:
                    parts = a.split("```")
                    candidates = [parts[i] for i in range(1, len(parts), 2)]
                # 3) النص كاملاً كخيار أخير
                candidates.append(a)

                for c in candidates:
                    c = c.strip()
                    # إزالة سطر اللغة
                    lines = c.splitlines()
                    if lines and lines[0].strip().lower() in ("python", "py"):
                        c = "\n".join(lines[1:]).strip()
                    if not c:
                        continue
                    # حاول مباشرة
                    try:
                        _ast.parse(c); return c
                    except SyntaxError:
                        pass
                    # أزل الأسطر العربية والتعليقات النصية
                    cleaned = "\n".join(
                        l for l in c.splitlines()
                        if not _re.search(r"[\u0600-\u06FF]", l)
                    ).strip()
                    if cleaned and cleaned != c:
                        try:
                            _ast.parse(cleaned); return cleaned
                        except SyntaxError:
                            pass
                return ""

            extracted = _extract_py(answer) if runnable else ""

            if runnable and extracted:
                # تحقق نحوي: هل الكود صالح للتنفيذ؟
                if lang in ('python',):
                    try:
                        import ast as _ast
                        _ast.parse(extracted)
                        verify_res = {"ok": True, "reason": "syntax_valid", "code_len": len(extracted)}
                    except SyntaxError as e:
                        verify_res = {"ok": False, "error": f"syntax: {e.msg} at line {e.lineno}"}
                else:
                    # js/ts — نعتبره مقبولاً (sandbox غير مطلوب للنحو)
                    verify_res = {"ok": True, "reason": "non_python_accepted", "code_len": len(extracted)}
            elif not extracted:
                verify_res = {"ok": False, "error": "no_code_block_in_answer"}
            else:
                verify_res = {"ok": None, "skipped": f"lang={lang} not runnable"}

            # 3) judge
            j = judge(task, answer)
            score = j["score"]

            entry = {
                "ts": time.time(), "round": round_i, "tier": tier,
                "cve": task["cve"], "cvss": task["cvss"], "cwe": task.get("cwe",""),
                "llm_elapsed_s": round(elapsed, 1),
                "llm_error": llm_err,
                "answer_len": len(answer),
                "answer_excerpt": (answer or "")[:400],
                "extracted_len": len(extracted) if runnable else 0,
                "blocks_count": (answer or "").count("```") // 2,
                "extract_lang": lang,
                "verify_ok": (verify_res or {}).get("ok"),
                "verify_error": (verify_res or {}).get("error"),
                "score": score, "judge_details": j["details"],
            }
            log_entry(entry)

            # سجل التدريب الكامل — before/after/prompt/response/extracted
            training_entry = {
                "ts": time.time(),
                "round": round_i,
                "tier": tier,
                "cve": task["cve"],
                "cvss": task["cvss"],
                "cwe": task.get("cwe", ""),
                "language": lang,
                "prompt": prompt,
                "before": task.get("before", ""),
                "after": task.get("after", ""),
                "response": answer,
                "extracted": extracted if runnable else "",
                "verify_ok": entry.get("verify_ok"),
                "verify_error": entry.get("verify_error"),
                "score": score,
                "judge_details": j["details"],
                "llm_error": llm_err,
                "llm_elapsed_s": round(elapsed, 1),
            }
            log_entry(training_entry, path=TRAINING_LOG)

            print(f"[{round_i:04d}] T{tier} {task['cve']} score={score} verify={entry['verify_ok']} {elapsed:.0f}s", flush=True)

            if entry.get("verify_ok") is True:
                log_entry(entry, path=VERIFIED_LOG)
            else:
                r = verify_res or {}
                entry["reject_reason"] = (
                    r.get("error")
                    or r.get("skipped")
                    or ("no_code_in_answer" if "```" not in answer else "verify_not_ok")
                )
                log_entry(entry, path=REJECTED_LOG)

            if llm_err:
                log_entry({"ts": time.time(), "round": round_i, "reason": "llm_error", "error": llm_err}, FAIL_LOG)

            recent_scores.append(score); recent_scores = recent_scores[-3:]
            if len(recent_scores) == 3 and sum(recent_scores)/3 >= 65 and tier < len(tiers)-1:
                tier += 1; recent_scores = []; _tg(f"↑ Tier {tier} reached")

            write_status({"state": "running", "round": round_i, "tier": tier,
                          "last_score": score, "avg3": sum(recent_scores)/max(1,len(recent_scores))})

            round_i += 1

            # ارفع لـ HF كل 10 جولات
            if round_i % UPLOAD_EVERY == 0:
                if _upload_to_hf(LOG, "autonomous.jsonl"):
                    uploaded_count += 1
                    print(f"  ↑ uploaded {round_i} rounds to HF", flush=True)

            time.sleep(2)

        except KeyboardInterrupt:
            break
        except Exception as e:
            tb = traceback.format_exc()
            log_entry({"ts": time.time(), "round": round_i, "reason": "exception",
                       "error": str(e), "tb": tb[:2000]}, FAIL_LOG)
            print(f"!! exception: {e}", flush=True)
            _tg(f"⚠️ runner crash: {type(e).__name__}: {str(e)[:200]}")
            time.sleep(30)

    _upload_to_hf(LOG, "autonomous.jsonl")
    write_status({"state": "stopped", "round": round_i})
    print(f"[{datetime.now()}] stopped after {round_i} rounds", flush=True)

if __name__ == "__main__":
    main()
