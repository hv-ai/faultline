"""Start the local desk with a hidden, process-only Nebius credential."""

import getpass
import os
import runpy
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Run this in an interactive Mac or VS Code terminal.")
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", 8770))
        except OSError:
            raise SystemExit(
                "Port 8770 is busy. Stop the existing Faultline server with Ctrl+C, then retry."
            )
    print("Faultline — Nebius live setup")
    print("Model: Qwen/Qwen3-30B-A3B-Instruct-2507")
    print("Rates: $0.10 input / $0.30 output per million tokens.")
    print("Local reservation ceiling: $1 total, including prior reservations.")
    print("Starting the desk does not itself send a model request.")
    key = getpass.getpass("Paste Nebius API key (hidden), then press Enter: ").strip()
    if not key:
        raise SystemExit("No key entered. Live testing remains off.")
    os.environ.update(
        NEBIUS_API_KEY=key,
        FAULTLINE_PROVIDER="nebius",
        FAULTLINE_MODEL="Qwen/Qwen3-30B-A3B-Instruct-2507",
        FAULTLINE_BUDGET_USD="1",
        FAULTLINE_INPUT_USD_PER_M="0.1",
        FAULTLINE_OUTPUT_USD_PER_M="0.3",
        FAULTLINE_LIVE_ENABLED="1",
    )
    del key
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    try:
        runpy.run_path(str(ROOT / "server.py"), run_name="__main__")
    except KeyboardInterrupt:
        print("\nFaultline stopped.")
    finally:
        os.environ.pop("NEBIUS_API_KEY", None)


if __name__ == "__main__":
    main()
