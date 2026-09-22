#!/usr/bin/env python3
"""
Autonomous Snapchat Fleet Account & Pacing Resolver
Enforces strict 3x daily posts per account across all 5 fleet accounts (15 daily fleet uploads).
Uses rolling 24-hour window quotas, 6.0h minimum cooldown, and fair rotation to catch up missed runs.
"""

import sys
import os
import json
import argparse
from datetime import datetime, timezone

def resolve_fleet_target(
    history_file: str = None,
    active_accounts: list = None,
    min_cooldown_hours: float = 4.0,
    max_daily_posts: int = 3,
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
            "posts_24h": None,
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
        lenses.sort(key=lambda x: x.get("timestamp") or "")
        lenses_24h = []
        for x in lenses:
            ts_str = x.get("timestamp")
            if ts_str:
                try:
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if (now - dt).total_seconds() <= 86400.0:
                        lenses_24h.append(x)
                except Exception:
                    pass

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
                "posts_24h": len(lenses_24h),
                "count": len(lenses)
            }
        else:
            account_stats[aid] = {
                "last_timestamp": None,
                "elapsed_hours": 9999.0,
                "posts_24h": 0,
                "count": 0
            }

    print("=== SNAPCHAT FLEET AUTONOMOUS PACING & QUOTA STATUS ===")
    total_fleet_24h = sum(s["posts_24h"] for s in account_stats.values())
    print(f"Total Fleet 24h Output: {total_fleet_24h}/{len(active_accounts) * max_daily_posts} posts")
    for aid, s in account_stats.items():
        ts_display = s["last_timestamp"] if s["last_timestamp"] else "Never"
        print(f"  Account #{aid}: {s['posts_24h']}/{max_daily_posts} posts (24h) | {s['count']} all-time | Last: {ts_display} ({s['elapsed_hours']:.1f}h ago)")

    # Filter eligible accounts: must be under daily quota AND meet cooldown
    eligible = [
        aid for aid, s in account_stats.items()
        if s["posts_24h"] < max_daily_posts and s["elapsed_hours"] >= min_cooldown_hours
    ]

    if eligible:
        # Priority order:
        # 1. Fewest posts in last 24h (prioritize accounts needing catch-up)
        # 2. Longest elapsed idle hours (fair tie-breaking)
        selected_aid = min(
            eligible,
            key=lambda a: (account_stats[a]["posts_24h"], -account_stats[a]["elapsed_hours"])
        )
        s = account_stats[selected_aid]
        should_run = True
        reason = (
            f"Account #{selected_aid} auto-selected: {s['posts_24h']}/{max_daily_posts} posts in last 24h, "
            f"idle for {s['elapsed_hours']:.1f}h (>= {min_cooldown_hours}h cooldown). Catching up fleet quota."
        )
    else:
        # Check if all accounts have reached the 3x quota
        under_quota = [aid for aid, s in account_stats.items() if s["posts_24h"] < max_daily_posts]
        if not under_quota:
            selected_aid = max(account_stats.keys(), key=lambda a: account_stats[a]["elapsed_hours"])
            s = account_stats[selected_aid]
            should_run = False
            reason = (
                f"All {len(active_accounts)} fleet accounts have completed their 3x daily quota "
                f"({total_fleet_24h}/{len(active_accounts) * max_daily_posts} total). Pacing resting until rolling 24h window shifts."
            )
        else:
            # Under quota accounts exist, but all are within the min_cooldown_hours window
            selected_aid = max(under_quota, key=lambda a: account_stats[a]["elapsed_hours"])
            s = account_stats[selected_aid]
            time_left = max(0.0, min_cooldown_hours - s["elapsed_hours"])
            should_run = False
            reason = (
                f"Accounts under quota ({', '.join('#' + a for a in under_quota)}) are within cooldown. "
                f"Next Account #{selected_aid} ({s['posts_24h']}/{max_daily_posts} posts, idle {s['elapsed_hours']:.1f}h) "
                f"will be eligible in {time_left:.1f}h."
            )

    print(f"\n[RESOLVER DECISION] Target: Account #{selected_aid} | Should Run: {should_run}")
    print(f"[RESOLVER REASON]   {reason}")

    return {
        "account_id": selected_aid,
        "should_run": should_run,
        "elapsed_hours": account_stats[selected_aid]["elapsed_hours"],
        "posts_24h": account_stats[selected_aid]["posts_24h"],
        "reason": reason
    }


def main():
    parser = argparse.ArgumentParser(description="Resolve target Snapchat account for scheduled run.")
    parser.add_argument("--force-account", type=str, default=None, choices=["1", "2", "3", "4", "5"], help="Force specific account ID (1, 2, 3, 4, or 5)")
    parser.add_argument("--min-hours", type=float, default=4.0, help="Minimum cooldown hours between publishes per account")
    parser.add_argument("--max-daily-posts", type=int, default=3, help="Maximum publishes per account in rolling 24-hour window")
    parser.add_argument("--env-file", type=str, default=None, help="File path to write export commands")
    args = parser.parse_args()

    # Check environment variable overrides
    env_force = os.environ.get("TARGET_ACC") or os.environ.get("FORCE_ACCOUNT")
    if env_force and env_force.strip().lower() in ["auto", "none", ""]:
        env_force = None
    force_acc = args.force_account or (env_force.strip() if env_force else None)

    decision = resolve_fleet_target(
        min_cooldown_hours=args.min_hours,
        max_daily_posts=args.max_daily_posts,
        forced_account=force_acc
    )

    if args.env_file:
        with open(args.env_file, "w") as f:
            f.write(f"export TARGET_ACCOUNT='{decision['account_id']}'\n")
            f.write(f"export SHOULD_RUN='{'true' if decision['should_run'] else 'false'}'\n")
            f.write(f"export ELAPSED_HOURS='{decision.get('elapsed_hours', 0)}'\n")
            f.write(f"export POSTS_24H='{decision.get('posts_24h', 0)}'\n")

    # Also set GITHUB_ENV if running inside GitHub Actions
    gh_env = os.environ.get("GITHUB_ENV")
    if gh_env and os.path.exists(gh_env):
        with open(gh_env, "a") as f:
            f.write(f"TARGET_ACCOUNT={decision['account_id']}\n")
            f.write(f"SHOULD_RUN={'true' if decision['should_run'] else 'false'}\n")
            f.write(f"ELAPSED_HOURS={decision.get('elapsed_hours', 0)}\n")
            f.write(f"POSTS_24H={decision.get('posts_24h', 0)}\n")

    return 0 if decision["should_run"] else 0


if __name__ == "__main__":
    sys.exit(main())
