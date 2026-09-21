#!/usr/bin/env python3
"""
Autonomous Snapchat Fleet Account & Pacing Resolver
Selects target account (Account 1 vs Account 2) based on real elapsed time since last published lens.
Prevents duplicate posts, ensures fair fleet alternation, and automatically catches up missed runs.
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone

def resolve_fleet_target(
    history_file: str = None,
    active_accounts: list = None,
    min_cooldown_hours: float = 7.0,
    forced_account: str = None
) -> dict:
    if not history_file:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        history_file = os.path.join(script_dir, "published_lenses.json")
    active_accounts = active_accounts or ["1", "2", "3", "4", "5"]
    now = datetime.now(timezone.utc)

    if forced_account:
        if str(forced_account) not in ["1", "2", "3", "4", "5"]:
            raise ValueError(f"Invalid account target '{forced_account}'. Fleet strictly enforces Accounts 1, 2, 3, 4, and 5.")
        print(f"[RESOLVER DECISION] Target: Account #{forced_account} | Forced: True")
        return {
            "account_id": str(forced_account),
            "should_run": True,
            "elapsed_hours": None,
            "reason": f"Manually forced run for Account #{forced_account}"
        }

    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception as e:
            print(f"[RESOLVER WARN] Could not parse {history_file}: {e}")
            history = []

    account_stats = {}
    for aid in active_accounts:
        lenses = [x for x in history if str(x.get("account_id")) == str(aid)]
        if lenses:
            last_ts_str = lenses[-1].get("timestamp")
            try:
                last_dt = datetime.fromisoformat(last_ts_str.replace("Z", "+00:00"))
                elapsed = (now - last_dt).total_seconds() / 3600.0
            except Exception:
                elapsed = 999.0
            account_stats[aid] = {
                "last_timestamp": last_ts_str,
                "elapsed_hours": elapsed,
                "count": len(lenses)
            }
        else:
            account_stats[aid] = {
                "last_timestamp": None,
                "elapsed_hours": 9999.0,
                "count": 0
            }

    print("=== SNAPCHAT FLEET AUTONOMOUS PACING STATUS ===")
    for aid, s in account_stats.items():
        ts_display = s["last_timestamp"] if s["last_timestamp"] else "Never"
        print(f"  Account #{aid}: {s['count']} published | Last: {ts_display} ({s['elapsed_hours']:.1f}h ago)")

    # Pick the account that has been waiting the longest
    selected_aid = max(account_stats.keys(), key=lambda a: account_stats[a]["elapsed_hours"])
    selected_stat = account_stats[selected_aid]

    if selected_stat["elapsed_hours"] < min_cooldown_hours:
        should_run = False
        reason = (
            f"Account #{selected_aid} last posted {selected_stat['elapsed_hours']:.1f}h ago "
            f"(< {min_cooldown_hours}h cooldown). Pacing optimal, skipping run to protect account health."
        )
    else:
        should_run = True
        reason = (
            f"Account #{selected_aid} has been idle for {selected_stat['elapsed_hours']:.1f}h "
            f"(>= {min_cooldown_hours}h cooldown). Auto-selected for publishing."
        )

    print(f"\n[RESOLVER DECISION] Target: Account #{selected_aid} | Should Run: {should_run}")
    print(f"[RESOLVER REASON]   {reason}")

    return {
        "account_id": selected_aid,
        "should_run": should_run,
        "elapsed_hours": selected_stat["elapsed_hours"],
        "reason": reason
    }


def main():
    parser = argparse.ArgumentParser(description="Resolve target Snapchat account for scheduled run.")
    parser.add_argument("--force-account", type=str, default=None, choices=["1", "2", "3", "4", "5"], help="Force specific account ID (1, 2, 3, 4, or 5)")
    parser.add_argument("--min-hours", type=float, default=7.0, help="Minimum cooldown hours between publishes per account")
    parser.add_argument("--env-file", type=str, default=None, help="File path to write export commands")
    args = parser.parse_args()

    # Check environment variable overrides
    env_force = os.environ.get("TARGET_ACC") or os.environ.get("FORCE_ACCOUNT")
    if env_force and env_force.strip().lower() in ["auto", "none", ""]:
        env_force = None
    force_acc = args.force_account or (env_force.strip() if env_force else None)

    decision = resolve_fleet_target(
        min_cooldown_hours=args.min_hours,
        forced_account=force_acc
    )

    if args.env_file:
        with open(args.env_file, "w") as f:
            f.write(f"export TARGET_ACCOUNT='{decision['account_id']}'\n")
            f.write(f"export SHOULD_RUN='{'true' if decision['should_run'] else 'false'}'\n")
            f.write(f"export ELAPSED_HOURS='{decision.get('elapsed_hours', 0)}'\n")

    # Also set GITHUB_ENV if running inside GitHub Actions
    gh_env = os.environ.get("GITHUB_ENV")
    if gh_env and os.path.exists(gh_env):
        with open(gh_env, "a") as f:
            f.write(f"TARGET_ACCOUNT={decision['account_id']}\n")
            f.write(f"SHOULD_RUN={'true' if decision['should_run'] else 'false'}\n")
            f.write(f"ELAPSED_HOURS={decision.get('elapsed_hours', 0)}\n")

    return 0 if decision["should_run"] else 0


if __name__ == "__main__":
    sys.exit(main())
