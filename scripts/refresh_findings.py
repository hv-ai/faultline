"""Refresh aggregate results and the local report without changing saved reviews.

Run from any directory: python3 scripts/refresh_findings.py
Raw records and review notes stay in the ignored local database/report.
"""

import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cases import CASES
from reporting import report


def stats(records):
    return {
        "trials": len(records),
        "restricted_response_trials": sum(
            any(h["classification"] == "restricted_match" for h in r.get("hits", []))
            for r in records
        ),
        "restricted_context_trials": sum(
            any(
                e["unauthorized"] and e["model_delivery"] == "provider_completed"
                for e in r.get("events", [])
            )
            for r in records
        ),
        "scores": dict(Counter(r.get("verdict") or "UNSCORED" for r in records)),
    }


def main():
    with sqlite3.connect(f"file:{ROOT / 'data/runs.sqlite'}?mode=ro", uri=True) as conn:
        records = [
            json.loads(row[0])
            for row in conn.execute("SELECT payload FROM runs ORDER BY rowid DESC")
        ]
    live = [
        r for r in records if r["mode"] == "live_model" and r["status"] == "complete"
    ]
    path = ROOT / "docs/results.json"
    summary = json.loads(path.read_text())
    summary.update(
        updated_at=datetime.now(timezone.utc).isoformat(),
        records=len(records),
        live_trials=len(live),
        reviewed_records=sum(bool(r.get("verdict")) for r in records),
        unscored_records=sum(not r.get("verdict") for r in records),
        review_provenance=dict(
            Counter(r.get("reviewer") or "unknown" for r in records if r.get("verdict"))
        ),
    )
    summary["cases"] = []
    for case in CASES:
        rows = [r for r in records if r["case_id"] == case["id"]]
        item = {
            "id": case["id"],
            "name": case["title"],
            "control": case["control"],
            "personal_reviews": sum(
                r.get("reviewer") == "user" and bool(r.get("verdict")) for r in rows
            ),
            "unscored_records": sum(not r.get("verdict") for r in rows),
        }
        for arm in ("baseline", "defended"):
            item[arm] = stats(
                [r for r in live if r["case_id"] == case["id"] and r["version"] == arm]
            )
        summary["cases"].append(item)
    for arm in ("baseline", "defended"):
        summary[arm] = stats([r for r in live if r["version"] == arm])
    path.write_text(json.dumps(summary, indent=2) + "\n")
    destination = ROOT / "reports/Faultline-case-findings.html"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(report(records))
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "records",
                    "live_trials",
                    "reviewed_records",
                    "unscored_records",
                    "review_provenance",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
