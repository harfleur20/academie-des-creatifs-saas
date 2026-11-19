"""Run on this machine the hourly jobs that GitHub runs in production.

GitHub cannot reach a backend on localhost, so in development start this script
next to uvicorn, from `backend`:

    python scripts/run_cron_jobs.py            # one pass
    python scripts/run_cron_jobs.py --every 15 # a pass every 15 minutes

It reads BILLING_CRON_URL and BILLING_CRON_SECRET from backend/.env and calls the
same routes as .github/workflows/billing-lifecycle.yml.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv


JOBS = (
    ("Abonnements des écoles", "/api/v1/billing/internal/lifecycle"),
    ("Paiements des étudiants", "/api/v1/commerce/internal/lifecycle"),
    ("Rappels de devoirs", "/api/v1/assignments/internal/reminders"),
    ("Suppressions d'écoles arrivées à échéance", "/api/v1/organizations/internal/deletion-lifecycle"),
)
# The last reminder opens one hour before the deadline: a longer pause could skip it.
MAX_INTERVAL_MINUTES = 60


def run_once(client: httpx.Client, secret: str) -> bool:
    """Call every job, even after a failure, like the `always()` steps of the workflow."""
    ok = True
    for label, path in JOBS:
        stamp = datetime.now().strftime("%H:%M:%S")
        try:
            response = client.post(path, headers={"X-Billing-Cron-Secret": secret})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            ok = False
            print(f"{stamp}  {label} : refusé ({exc.response.status_code} {exc.response.text[:200]})", file=sys.stderr)
        except httpx.HTTPError as exc:
            ok = False
            print(f"{stamp}  {label} : backend injoignable ({exc})", file=sys.stderr)
        else:
            print(f"{stamp}  {label} : {response.json()}")
    return ok


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        # Git Bash reads UTF-8, not the Windows code page; a log file must get each line at once.
        stream.reconfigure(encoding="utf-8", line_buffering=True)
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    parser = argparse.ArgumentParser(description="Lance en local les tâches horaires du SaaS.")
    parser.add_argument("--every", type=int, metavar="MINUTES", help=f"relancer toutes les N minutes (1 à {MAX_INTERVAL_MINUTES})")
    args = parser.parse_args()
    if args.every is not None and not 1 <= args.every <= MAX_INTERVAL_MINUTES:
        parser.error(f"--every doit être compris entre 1 et {MAX_INTERVAL_MINUTES} minutes, sinon des rappels seraient manqués.")

    base_url = os.getenv("BILLING_CRON_URL", "").strip().rstrip("/") or "http://localhost:8000"
    secret = os.getenv("BILLING_CRON_SECRET", "").strip()
    if not secret:
        print("BILLING_CRON_SECRET est vide dans backend/.env.", file=sys.stderr)
        return 2

    with httpx.Client(base_url=base_url, timeout=300) as client:
        if args.every is None:
            return 0 if run_once(client, secret) else 1
        print(f"Tâches lancées toutes les {args.every} min sur {base_url}. Ctrl+C pour arrêter.")
        try:
            while True:
                run_once(client, secret)
                time.sleep(args.every * 60)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
