"""اختبارات رسمية لحلقة self_verify. استخرجها من هذا الملف إن أردتَ دمجها في مجموعة اختبارات مرصد."""
import unittest
import self_verify as sv


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, messages, **kw):
        self.calls.append(messages)
        return {"content": self.replies.pop(0)}


class FakeSandbox:
    def __init__(self, script):
        self.script, self.i, self.calls = script, 0, []

    def run_python(self, code, timeout):
        self.calls.append(code)
        r = self.script[self.i]
        self.i += 1
        return r


class SelfVerify(unittest.TestCase):
    def test_fixes_after_failure(self):
        llm = FakeLLM(["```python\nprint(1/0)\n```", "```python\nprint(1)\n```"])
        sb = FakeSandbox([{"status": "error", "stdout": "", "stderr": "ZeroDivisionError"},
                          {"status": "ok", "stdout": "1\n", "stderr": ""}])
        r = sv.verify_and_fix(llm, sb, "اطبع واحد", max_attempts=3)
        self.assertTrue(r["ok"])
        self.assertEqual(r["attempts"], 2)
        self.assertNotIn("1/0", r["code"])
        self.assertIn("ZeroDivisionError", llm.calls[1][-1]["content"])

    def test_gives_up_after_max_attempts(self):
        llm = FakeLLM(["```python\nx\n```"] * 5)
        sb = FakeSandbox([{"status": "error", "stdout": "", "stderr": "NameError"}] * 5)
        r = sv.verify_and_fix(llm, sb, "مهمة مستحيلة", max_attempts=3)
        self.assertFalse(r["ok"])
        self.assertEqual(len(sb.calls), 3)

    def test_handles_missing_code_block(self):
        llm = FakeLLM(["كلام بلا كود", "```python\nprint(9)\n```"])
        sb = FakeSandbox([{"status": "ok", "stdout": "9\n", "stderr": ""}])
        r = sv.verify_and_fix(llm, sb, "اطبع تسعة", max_attempts=3)
        self.assertTrue(r["ok"])
        self.assertEqual(len(sb.calls), 1)                 # لم يُنفَّذ الرد الفارغ من كود

    def test_succeeds_first_try(self):
        llm = FakeLLM(["```python\nprint(2)\n```"])
        sb = FakeSandbox([{"status": "ok", "stdout": "2\n", "stderr": ""}])
        r = sv.verify_and_fix(llm, sb, "اطبع اثنين")
        self.assertTrue(r["ok"])
        self.assertEqual(r["attempts"], 1)

    def test_history_records_every_attempt(self):
        llm = FakeLLM(["```python\nbad\n```", "```python\nprint(5)\n```"])
        sb = FakeSandbox([{"status": "error", "stdout": "", "stderr": "err"},
                          {"status": "ok", "stdout": "5\n", "stderr": ""}])
        r = sv.verify_and_fix(llm, sb, "اطبع خمسة")
        self.assertEqual(len(r["history"]), 2)


if __name__ == "__main__":
    unittest.main()
