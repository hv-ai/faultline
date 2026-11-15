"""Conservative per-request reservations, persisted across server restarts."""

import json, os, sqlite3, time, uuid, math
from pathlib import Path

PATH = Path(__file__).parent / "data" / "budget.sqlite"


def settings():
    def number(k):
        try:
            value = float(os.environ.get(k, "0"))
            return value if math.isfinite(value) and value > 0 else 0
        except ValueError:
            return 0

    return {
        k: number(k)
        for k in (
            "FAULTLINE_BUDGET_USD",
            "FAULTLINE_INPUT_USD_PER_M",
            "FAULTLINE_OUTPUT_USD_PER_M",
        )
    }


def db():
    PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(PATH, timeout=30)
    c.execute(
        "CREATE TABLE IF NOT EXISTS reservations(id TEXT PRIMARY KEY, amount REAL, created REAL)"
    )
    return c


def status():
    s = settings()
    with db() as c:
        used = c.execute("SELECT COALESCE(SUM(amount),0) FROM reservations").fetchone()[
            0
        ]
    return {
        "cap_usd": s["FAULTLINE_BUDGET_USD"],
        "reserved_usd": round(used, 6),
        "remaining_usd": round(max(0, s["FAULTLINE_BUDGET_USD"] - used), 6),
        "rates_configured": s["FAULTLINE_INPUT_USD_PER_M"] > 0
        and s["FAULTLINE_OUTPUT_USD_PER_M"] > 0,
    }


def reserve(payload):
    s = settings()
    if min(s.values()) <= 0:
        raise RuntimeError(
            "Set a positive spending cap and verified model rates before live execution."
        )
    # UTF-8 bytes upper-bound typical BPE input token counts; include tool framing headroom.
    estimate = (
        (len(json.dumps(payload, ensure_ascii=False).encode()) + 2048)
        * s["FAULTLINE_INPUT_USD_PER_M"]
        + payload["max_tokens"] * s["FAULTLINE_OUTPUT_USD_PER_M"]
    ) / 1_000_000
    with db() as c:
        c.execute("BEGIN IMMEDIATE")
        used = c.execute("SELECT COALESCE(SUM(amount),0) FROM reservations").fetchone()[
            0
        ]
        if used + estimate > s["FAULTLINE_BUDGET_USD"]:
            raise RuntimeError(
                "Local spending reservation limit reached; request was not sent."
            )
        c.execute(
            "INSERT INTO reservations VALUES (?,?,?)",
            (str(uuid.uuid4()), estimate, time.time()),
        )
    return estimate
