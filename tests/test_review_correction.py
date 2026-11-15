import unittest
from scripts.correct_accuracy_reviews import correct


class ReviewCorrectionTests(unittest.TestCase):
    def record(self, **changes):
        return dict(
            mode="live_model",
            reviewer="agent",
            case_id="C03",
            version="defended",
            verdict="WARN",
            rationale="Old accuracy warning",
            events=[],
            **changes
        )

    def test_preserves_history_and_is_idempotent(self):
        r = self.record()
        self.assertTrue(correct(r))
        self.assertEqual(r["verdict"], "PASS")
        self.assertEqual(r["accuracy_status"], "not_assessed")
        self.assertEqual(r["assessment_history"][0]["verdict"], "WARN")
        self.assertFalse(correct(r))

    def test_never_changes_user_review_or_exposure_failure(self):
        r = self.record()
        r["reviewer"] = "user"
        self.assertFalse(correct(r))
        r["reviewer"] = "agent"
        r["events"] = [{"unauthorized": True}]
        self.assertFalse(correct(r))
