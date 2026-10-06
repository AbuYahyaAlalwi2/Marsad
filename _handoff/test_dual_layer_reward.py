"""اختبارات رسمية للمكافأة ثنائية الطبقة."""
import unittest
from dual_layer_reward import combined_reward, correctness_score, explanation_score

CWE = "CWE-89"
GOOD_EXPLAIN = ("الثغرة تحدث لأن الاستعلام يُبنى بتسلسل نصوص من مدخل المستخدم دون معامَلة.\n"
               "```python\ncursor.execute(q, (id,))\n```")


class DualLayerRewardTests(unittest.TestCase):
    def test_full_marks_for_correct_and_explained(self):
        r = combined_reward(3, 3, GOOD_EXPLAIN, CWE)
        self.assertEqual(r["correctness"], 1.0)
        self.assertGreater(r["explanation"], 0.5)

    def test_correct_without_explanation_is_penalized(self):
        r = combined_reward(3, 3, "```python\ncursor.execute(q, (id,))\n```", CWE)
        self.assertEqual(r["correctness"], 1.0)
        self.assertEqual(r["explanation"], 0.0)
        self.assertLess(r["total"], 1.0)

    def test_generic_filler_not_counted_as_explanation(self):
        text = "هذه ثغرة خطيرة ويجب إصلاح هذا فوراً.\n```python\nx\n```"
        self.assertLess(explanation_score(text, CWE), 0.3)

    def test_explanation_after_code_not_counted(self):
        text = "```python\nx\n```\nالسبب أن الاستعلام يُبنى بتسلسل نصوص دون معامَلة."
        self.assertEqual(explanation_score(text, CWE), 0.0)

    def test_correctness_dominates_over_explanation(self):
        wrong = combined_reward(0, 3, GOOD_EXPLAIN, CWE)
        right = combined_reward(3, 3, "```\nx\n```", CWE)
        self.assertLess(wrong["total"], right["total"])

    def test_unknown_cwe_gets_conservative_partial_score(self):
        s = explanation_score("شرح طويل جداً ومفصّل جداً عن سبب هذه المشكلة التقنية تحديداً هنا.\n```\nx\n```", "CWE-999999")
        self.assertTrue(0.0 < s < 1.0)

    def test_correctness_score_bounds(self):
        self.assertEqual(correctness_score(0, 0), 0.0)
        self.assertEqual(correctness_score(5, 5), 1.0)
        self.assertEqual(correctness_score(2, 4), 0.5)

    def test_no_code_block_at_all(self):
        self.assertEqual(explanation_score("نص بلا كود", CWE), 0.0)

    def test_weights_are_configurable(self):
        r = combined_reward(3, 3, "```\nx\n```", CWE, w_correctness=0.5, w_explanation=0.5)
        self.assertEqual(r["total"], 0.5)  # 0.5*1.0 + 0.5*0.0


if __name__ == "__main__":
    unittest.main()
