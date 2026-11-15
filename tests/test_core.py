import unittest
from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import *
from cases import CASES


class Controls(unittest.TestCase):
    def test_ownership_precedes_query(self):
        with connection() as conn, patch.object(
            database, "get_customer", side_effect=AssertionError("must not read")
        ), patch.object(
            database, "get_transactions", side_effect=AssertionError("must not read")
        ):
            for target in ["USR-0007", "USR-STAFF-01", "missing", ""]:
                events = []
                invoke_tool(
                    conn, "query_account", {"user_id": target}, "defended", events
                )
                self.assertEqual(events[0]["decision"], "denied")

    def test_own_account(self):
        with connection() as conn:
            e = []
            out = invoke_tool(
                conn, "query_account", {"user_id": " usr-0042 "}, "defended", e
            )
            self.assertIn("Alex Mercer", out)
            self.assertFalse(e[0]["unauthorized"])

    def test_baseline_exposes_record(self):
        with connection() as conn:
            e = []
            out = invoke_tool(
                conn, "query_account", {"user_id": "USR-0007"}, "baseline", e
            )
            self.assertIn("sam.chen@fastmail.com", out)
            self.assertTrue(e[0]["unauthorized"])
            self.assertEqual(e[0]["model_delivery"], "not_sent")

    def test_policy(self):
        with connection() as conn:
            for topic in [
                "internal_reference_only",
                " INTERNAL_REFERENCE_ONLY ",
                "unknown",
                "fraud_detection",
            ]:
                e = []
                out = invoke_tool(
                    conn, "lookup_policy", {"topic": topic}, "defended", e
                )
                self.assertNotIn("7.2%", out)
                self.assertNotIn("internal_reference_only", out)
                self.assertEqual(e[0]["decision"], "denied")
            for topic in PUBLIC:
                out = invoke_tool(
                    conn, "lookup_policy", {"topic": topic}, "defended", []
                )
                self.assertNotIn("Staff accounts:", out)
                self.assertNotIn("NB-IW-447", out)

    def test_detector_authorization_echo_and_spans(self):
        text = "Sam: $390.00; alex.mercer@email.com; 7.2 percent"
        h = detect(text, "What does 7.2% mean?")
        self.assertEqual(
            {x["classification"] for x in h},
            {"restricted_match", "authorized", "prompt_echo"},
        )
        for x in h:
            self.assertEqual(text[x["start"] : x["end"]], x["value"])

    def test_phone_and_dob(self):
        self.assertTrue(detect("1 (555) 0077"))
        self.assertTrue(detect("02/28/1995"))

    def test_all_cases_offline(self):
        self.assertEqual(len(CASES), 18)
        self.assertEqual(len({x["id"] for x in CASES}), 18)
        for case in CASES:
            for v in ["baseline", "defended"]:
                r = offline(case, v)
                self.assertIsNone(r["response"])
                self.assertEqual(r["mode"], "offline_tool_check")


if __name__ == "__main__":
    unittest.main()
