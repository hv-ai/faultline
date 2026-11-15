import unittest, tempfile, os
from pathlib import Path
from unittest.mock import patch
import budget


class Budget(unittest.TestCase):
    def test_reservations_persist_and_block_before_send(self):
        with tempfile.TemporaryDirectory() as d, patch.object(
            budget, "PATH", Path(d) / "ledger.sqlite"
        ), patch.dict(
            os.environ,
            {
                "FAULTLINE_BUDGET_USD": ".01",
                "FAULTLINE_INPUT_USD_PER_M": "1",
                "FAULTLINE_OUTPUT_USD_PER_M": "1",
            },
        ):
            payload = {"messages": [], "max_tokens": 1000}
            budget.reserve(payload)
            self.assertGreater(budget.status()["reserved_usd"], 0)
            budget.reserve(payload)
            budget.reserve(payload)
            with self.assertRaises(RuntimeError):
                budget.reserve(payload)

    def test_missing_and_nonfinite_caps_rejected(self):
        for cap in ("0", "nan", "inf", "-1"):
            with patch.dict(
                os.environ,
                {
                    "FAULTLINE_BUDGET_USD": cap,
                    "FAULTLINE_INPUT_USD_PER_M": "1",
                    "FAULTLINE_OUTPUT_USD_PER_M": "1",
                },
            ):
                with self.assertRaises(RuntimeError):
                    budget.reserve({"max_tokens": 1})
