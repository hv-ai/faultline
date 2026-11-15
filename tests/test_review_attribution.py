import unittest
from scripts.reconcile_reviews import reconcile


class AttributionTests(unittest.TestCase):
    def test_explicit_note_preserves_review(self):
        r = dict(
            reviewer="agent", verdict="FAIL", rationale="User's Review- Access failed"
        )
        original = (r["verdict"], r["rationale"])
        self.assertTrue(reconcile(r))
        self.assertEqual(r["reviewer"], "user")
        self.assertEqual((r["verdict"], r["rationale"]), original)
        self.assertFalse(reconcile(r))

    def test_agent_note_stays_agent(self):
        r = dict(
            reviewer="agent", verdict="PASS", rationale="Agent review: no retrieval"
        )
        self.assertFalse(reconcile(r))
        self.assertEqual(r["reviewer"], "agent")
