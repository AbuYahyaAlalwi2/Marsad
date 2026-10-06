import json, sys, os, random, time
from pathlib import Path

class ReservedEvaluationGuard:
    def __init__(self, eval_dir="reserved_eval_set"):
        self.eval_dir = Path(eval_dir)
        self.eval_dir.mkdir(parents=True, exist_ok=True)
        self.sources = {
            "nvd": self.eval_dir / "nvd_reserved.jsonl",
            "github": self.eval_dir / "github_reserved.jsonl",
            "sandbox": self.eval_dir / "sandbox_reserved.jsonl"
        }
        self.performance_log = self.eval_dir / "performance_history.json"
        self.stats = {"reserved": 0, "tested": 0, "consecutive_drops": 0}

    def reserve_sample(self, sample, source):
        if random.random() < 0.12:
            sample["_eval_reserved"] = True
            sample["_source"] = source
            sample["_reserved_at"] = time.time()
            with open(self.sources[source], "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
            self.stats["reserved"] += 1
            return True
        return False

    def executive_test(self, sample, model_response):
        required = ["defensive_mechanism", "hardening_response", "detection_mechanism"]
        present = sum(1 for c in required if model_response.get(c) and len(str(model_response[c])) > 20)
        score = present / len(required)
        if sample.get("anomalous_behavior") and model_response.get("anomalous_behavior"):
            if sample["anomalous_behavior"].lower() not in model_response["anomalous_behavior"].lower():
                score *= 0.7
        tech_desc = str(model_response.get("technical_description", ""))
        if len(tech_desc) > 200:
            score = min(1.0, score * 1.1)
        return score

    def check_collapse_risk(self, current_score):
        history = []
        if self.performance_log.exists():
            with open(self.performance_log, "r") as f:
                history = json.load(f)
        history.append({"timestamp": time.time(), "score": current_score, "test_number": self.stats["tested"]})
        with open(self.performance_log, "w") as f:
            json.dump(history[-100:], f, indent=2)
        if len(history) >= 2:
            prev_score = history[-2]["score"]
            if current_score < prev_score:
                self.stats["consecutive_drops"] += 1
                print(f"   ⚠️ انخفاض متتالي #{self.stats['consecutive_drops']}: {prev_score:.3f} → {current_score:.3f}")
                if self.stats["consecutive_drops"] >= 2:
                    print(f"    🛑 تم اكتشاف انهيار معرفي! توقف تلقائي مُفعّل.")
                    return True
            else:
                self.stats["consecutive_drops"] = 0
        return False

    def process_batch(self, input_file, output_file, source):
        print(f"🔄 معالجة دفعة من {source}: {input_file}")
        reserved_count = 0
        training_count = 0
        with open(input_file, "r", encoding="utf-8") as fin, open(output_file, "w", encoding="utf-8") as fout:
            for line in fin:
                try:
                    sample = json.loads(line)
                    if self.reserve_sample(sample, source):
                        reserved_count += 1
                    else:
                        sample["_training_eligible"] = True
                        fout.write(json.dumps(sample, ensure_ascii=False) + "\n")
                        training_count += 1
                except json.JSONDecodeError:
                    continue
        print(f"    محجوز للتقييم: {reserved_count} | ✏️ للتدريب: {training_count}")
        return True

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("الاستخدام: python3 reserved_eval_guard.py input.jsonl output.jsonl source")
        sys.exit(1)
    guard = ReservedEvaluationGuard()
    guard.process_batch(sys.argv[1], sys.argv[2], sys.argv[3])
