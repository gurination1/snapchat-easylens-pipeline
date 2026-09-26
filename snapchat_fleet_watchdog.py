#!/usr/bin/env python3
"""
Autonomous Snapchat Fleet Cloud Watchdog
Audits fleet quota, detects dropped GHA scheduled runs, and automatically dispatches catch-ups.
Ensures strict 15/15 daily upload target across all 5 Snapchat accounts.
"""

import sys
import os
import json
import subprocess
from datetime import datetime, timezone

from resolve_target_account import resolve_fleet_target

REPO = "gurination1/snapchat-easylens-pipeline"


def check_active_runs(repo: str = REPO) -> bool:
    """Check if any pipeline run is currently in progress or queued."""
    cmd = [
        "gh", "run", "list",
        "--repo", repo,
        "--workflow", "snapchat_easylens.yml",
        "--limit", "3",
        "--json", "databaseId,status"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20)
        if res.returncode != 0:
            return False
        runs = json.loads(res.stdout)
        for r in runs:
            if r.get("status") in ("in_progress", "queued"):
                print(f"[WATCHDOG] Active run detected on GHA: Run ID {r.get('databaseId')} ({r.get('status')})")
                return True
        return False
    except Exception as e:
        print(f"[WATCHDOG WARN] Could not check active runs: {e}")
        return False


def dispatch_catchup(account_id: str = "auto", repo: str = REPO) -> bool:
    """Dispatches snapchat_easylens.yml on GHA cloud."""
    cmd = [
        "gh", "workflow", "run",
        "snapchat_easylens.yml",
        "--repo", repo,
        "-f", f"account_id={account_id}"
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
        if res.returncode == 0:
            print(f"[WATCHDOG SUCCESS] Dispatched catch-up run for Account #{account_id} on {repo}")
            return True
        else:
            print(f"[WATCHDOG ERROR] Dispatch failed: {res.stderr.strip()}")
            return False
    except Exception as e:
        print(f"[WATCHDOG ERROR] Exception during dispatch: {e}")
        return False


def run_watchdog(auto_dispatch: bool = True):
    print("=================================================================")
    print(f"👻 Snapchat Fleet Autonomous Watchdog — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=================================================================")

    decision = resolve_fleet_target()
    should_run = decision.get("should_run", False)
    target_acc = decision.get("account_id")

    if not should_run:
        print(f"\n✅ Fleet pacing optimal. All accounts within cooldown or completed quota.")
        return

    print(f"\n⚠️  Fleet Catch-Up Required: Account #{target_acc} is eligible ({decision.get('reason')}).")

    if check_active_runs():
        print(f"⏸️  Catch-up delayed: Pipeline run already active on GHA runner. Will re-evaluate on next cycle.")
        return

    if auto_dispatch:
        print(f"🚀 Triggering cloud autonomous catch-up dispatch for Account #{target_acc}...")
        dispatch_catchup(account_id=target_acc)
    else:
        print(f"💡 Run with '--dispatch' to trigger catch-up on GHA.")


if __name__ == "__main__":
    auto = "--no-dispatch" not in sys.argv
    run_watchdog(auto_dispatch=auto)
