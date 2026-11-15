"""Fetch pinned classroom dependencies locally; never redistribute them in this repo."""

import json
import urllib.request
from pathlib import Path

COMMIT = "9aed6350836f0ea625be6a4ae637943153e1c96e"
FILES = ("agent.py", "database.py", "knowledge_base.py", "seed_data.py", "README.md")


def main():
    destination = Path(__file__).parent / "upstream"
    destination.mkdir(exist_ok=True)
    for name in FILES:
        url = f"https://raw.githubusercontent.com/The-Gen-Academy/week6_neobank_aria_agent/{COMMIT}/{name}"
        with urllib.request.urlopen(url, timeout=30) as response:
            (destination / name).write_bytes(response.read())
    (destination / "provenance.json").write_text(
        json.dumps(
            {
                "repository": "https://github.com/The-Gen-Academy/week6_neobank_aria_agent",
                "commit": COMMIT,
                "files": FILES,
            },
            indent=2,
        )
    )
    print("Pinned classroom dependencies downloaded into ignored upstream/.")


if __name__ == "__main__":
    main()
