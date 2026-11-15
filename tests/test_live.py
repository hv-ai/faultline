import unittest, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live import run
from cases import CASES


class Trace(unittest.TestCase):
    def test_refusal_does_not_erase_exposure(self):
        seen = []

        def fake(messages, tools=None):
            seen.append(messages)
            m = (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "1",
                            "type": "function",
                            "function": {
                                "name": "query_account",
                                "arguments": '{"user_id":"USR-0007"}',
                            },
                        }
                    ],
                }
                if tools
                else {"role": "assistant", "content": "I cannot share that."}
            )
            return {
                "choices": [{"message": m}],
                "model": "test-fixture",
                "usage": {"total_tokens": 1},
            }

        for version in ["baseline", "defended"]:
            r = run(CASES[10], version, fake)
            e = r["events"][0]
            self.assertEqual(r["status"], "complete")
            self.assertEqual(e["model_delivery"], "provider_completed")
            self.assertEqual(e["unauthorized"], version == "baseline")
            self.assertEqual(r["hits"], [])
            self.assertEqual(
                "sam.chen@fastmail.com" in seen[-1][-1]["content"],
                version == "baseline",
            )

    def test_failure_retains_attempted_not_completed(self):
        def fake(messages, tools=None):
            if not tools:
                raise RuntimeError("failed")
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "1",
                                    "type": "function",
                                    "function": {
                                        "name": "lookup_policy",
                                        "arguments": '{"topic":"internal_reference_only"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            }

        r = run(CASES[5], "baseline", fake)
        self.assertEqual(r["status"], "error")
        self.assertEqual(r["events"][0]["model_delivery"], "request_attempted")
        self.assertIsNone(r["verdict"])
