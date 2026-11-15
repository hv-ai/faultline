import csv, io, json, sqlite3, html, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
from core import offline, ROOT
from cases import CASES
from live import run as live_run, configuration
from budget import status as budget_status


def readiness():
    config = configuration()
    budget = budget_status()
    enabled = (
        os.environ.get("FAULTLINE_LIVE_ENABLED") == "1"
        and config["key_configured"]
        and bool(config["model"])
        and budget["rates_configured"]
        and budget["remaining_usd"] > 0
    )
    return {
        "live_enabled": bool(enabled),
        "provider": config["provider"],
        "model": config["model"],
        "key_configured": config["key_configured"],
        "budget": budget,
    }


DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)


def db():
    c = sqlite3.connect(DATA / "runs.sqlite")
    c.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, payload TEXT)")
    return c


with db():
    pass


def saved():
    with db() as c:
        return [
            json.loads(x[0])
            for x in c.execute("SELECT payload FROM runs ORDER BY rowid DESC")
        ]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, body, status=200, ctype="application/json"):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/state":
            return self.send(
                {
                    "cases": CASES,
                    "runs": saved(),
                    **readiness(),
                    "session": "Alex Mercer / USR-0042",
                }
            )
        if path == "/export":
            from reporting import report

            return self.send(report(saved()).encode(), ctype="text/html; charset=utf-8")
        files = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}
        if path in files:
            f = ROOT / "static" / files[path]
            return self.send(
                f.read_bytes(),
                ctype={
                    "html": "text/html; charset=utf-8",
                    "js": "text/javascript",
                    "css": "text/css",
                }[f.suffix[1:]],
            )
        self.send({"error": "Not found"}, 404)

    def do_POST(self):
        # Prevent foreign pages from triggering local actions.
        if self.headers.get("Origin") not in (
            None,
            "http://127.0.0.1:8770",
            "http://localhost:8770",
        ):
            return self.send({"error": "Origin rejected"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 16384:
                raise ValueError("Request too large")
            req = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            if path == "/api/run":
                if req.get("mode") not in ("offline", "live") or (
                    req.get("mode") == "live" and not readiness()["live_enabled"]
                ):
                    raise ValueError("Live calls are not enabled.")
                case = next(x for x in CASES if x["id"] == req["case_id"])
                version = req["version"]
                if version not in ("baseline", "defended"):
                    raise ValueError("Invalid version")
                r = (
                    offline(case, version)
                    if req["mode"] == "offline"
                    else live_run(case, version)
                )
                with db() as c:
                    c.execute("INSERT INTO runs VALUES (?,?)", (r["id"], json.dumps(r)))
                return self.send(r)
            if path == "/api/review":
                if (
                    req.get("verdict") not in ("PASS", "WARN", "FAIL")
                    or not req.get("rationale", "").strip()
                ):
                    raise ValueError("Choose a verdict and provide evidence.")
                with db() as c:
                    row = c.execute(
                        "SELECT payload FROM runs WHERE id=?", (req["id"],)
                    ).fetchone()
                    if not row:
                        raise ValueError("Run not found")
                    r = json.loads(row[0])
                    if r["status"] == "error":
                        raise ValueError("Failed trial is unscored")
                    r.update(
                        verdict=req["verdict"],
                        rationale=req["rationale"][:2000],
                        reviewer="user",
                    )
                    c.execute(
                        "UPDATE runs SET payload=? WHERE id=?", (json.dumps(r), r["id"])
                    )
                return self.send(r)
            self.send({"error": "Not found"}, 404)
        except (ValueError, KeyError, StopIteration):
            self.send(
                {
                    "error": "Invalid request. Select a case, version and a review reason where required."
                },
                400,
            )


if __name__ == "__main__":
    print(
        "Faultline: http://127.0.0.1:8770 (live calls require explicit local configuration)",
        flush=True,
    )
    ThreadingHTTPServer(("127.0.0.1", 8770), Handler).serve_forever()
