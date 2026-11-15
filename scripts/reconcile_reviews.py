"""Repair legacy review metadata without changing verdicts or review text."""

import json
import sqlite3
from datetime import datetime, timezone


def reconcile(record):
    if not record.get("verdict"):
        return False
    note = record.get("rationale", "").strip()
    explicit = note.lower().startswith(
        ("user review:", "user reviewed:", "user's review")
    )
    legacy = (
        record.get("reviewer") is None and note and not note.startswith("Agent review:")
    )
    if record.get("reviewer") == "user" or not (explicit or legacy):
        return False
    record.setdefault("attribution_history", []).append(
        {
            "previous_reviewer": record.get("reviewer"),
            "reason": (
                "Explicit user-review note"
                if explicit
                else "Legacy saved user review without reviewer field"
            ),
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    record["reviewer"] = "user"
    return True


if __name__ == "__main__":
    changed = 0
    with sqlite3.connect("data/runs.sqlite") as conn:
        for ident, payload in conn.execute("SELECT id,payload FROM runs").fetchall():
            record = json.loads(payload)
            if reconcile(record):
                conn.execute(
                    "UPDATE runs SET payload=? WHERE id=?", (json.dumps(record), ident)
                )
                changed += 1
    print(f"Reconciled {changed} review attributions; verdicts and notes unchanged.")
