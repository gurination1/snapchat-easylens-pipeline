import os
import sys
import glob
import json
import subprocess
import requests

SNAPML_BASE = "https://gcp.api.snapchat.com/lens-studio-web-snapml"


def test_token(token: str, cookie_header: str = "") -> dict:
    url = f"{SNAPML_BASE}/api/me"
    headers = {
        "Authorization": f"Bearer {token}",
        "Origin": "https://easylens.snapchat.com",
        "Referer": "https://easylens.snapchat.com/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36"
    }
    if cookie_header:
        headers["Cookie"] = cookie_header

    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code == 200:
        return res.json()
    return None


def extract_from_har(har_path: str):
    print(f"Scanning HAR: {har_path} ({os.path.getsize(har_path) // 1024} KB)...")
    found_tokens = []

    with open(har_path, "r", encoding="utf-8", errors="ignore") as f:
        try:
            data = json.load(f)
            entries = data.get("log", {}).get("entries", [])
            for entry in reversed(entries):
                req = entry.get("request", {})
                url = req.get("url", "")
                if "snapchat.com" in url:
                    auth_header = None
                    cookie_header = None
                    for h in req.get("headers", []):
                        name = h.get("name", "").lower()
                        if name == "authorization" and "bearer" in h.get("value", "").lower():
                            auth_header = h.get("value", "").replace("Bearer ", "").replace("bearer ", "").strip()
                        elif name == "cookie":
                            cookie_header = h.get("value", "").strip()

                    if auth_header:
                        found_tokens.append({
                            "token": auth_header,
                            "cookie": cookie_header or "",
                            "url": url,
                            "time": entry.get("startedDateTime", "")
                        })
        except Exception as e:
            print(f"Error parsing HAR as full JSON ({e}), fallback text scanning...")
            pass

    return found_tokens


def sync_to_github(token: str, cookie_header: str):
    repo = "gurination1/snapchat-easylens-pipeline"
    print(f"[GITHUB] Syncing fresh credentials to repository secrets ({repo})...")
    subprocess.run(["gh", "secret", "set", "SNAP_SSO_TOKEN", "-b", token, "-R", repo], check=True)
    if cookie_header:
        subprocess.run(["gh", "secret", "set", "SNAP_COOKIE_HEADER", "-b", cookie_header, "-R", repo], check=True)
    print("[GITHUB SUCCESS] Secrets SNAP_SSO_TOKEN and SNAP_COOKIE_HEADER updated successfully!")


def watch_mode(poll_interval: int = 3):
    download_dir = "/sdcard/Download"
    print(f"[*] Watching {download_dir} for new Snapchat HAR or auth files...")
    print("[*] Simply tap 'Export HAR' in your mobile browser (Quetta/Kiwi) or save to Downloads.")
    seen_files = set(glob.glob(os.path.join(download_dir, "*")))

    while True:
        current_files = set(glob.glob(os.path.join(download_dir, "*")))
        new_files = current_files - seen_files

        for nf in new_files:
            if "har" in nf.lower() or "snap" in nf.lower() or "curl" in nf.lower():
                print(f"\n[NEW FILE DETECTED] {nf}")
                # Wait 1s for write to finish
                time.sleep(1)
                tokens = extract_from_har(nf)
                for cand in tokens:
                    t = cand["token"]
                    c = cand["cookie"]
                    user = test_token(t, c)
                    if user:
                        print(f"\n[AUTH SUCCESS!] Verified user: {user.get('displayName')} (@{user.get('username')})")
                        sync_to_github(t, c)
                        print("[PIPELINE READY] Triggering GitHub Actions workflow...")
                        subprocess.run([
                            "gh", "workflow", "run", "snapchat_easylens.yml",
                            "-R", "gurination1/snapchat-easylens-pipeline",
                            "-f", "account_id=1",
                            "-f", "use_gemini=true",
                            "-f", "auto_publish=true"
                        ])
                        print("[DONE] Workflow launched successfully!")
                        return True
        seen_files = current_files
        time.sleep(poll_interval)


def main():
    import time
    if "--watch" in sys.argv:
        watch_mode()
        return

    download_dir = "/sdcard/Download"
    pattern = os.path.join(download_dir, "*snap*.har*")
    har_files = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)

    if not har_files:
        har_files = sorted(glob.glob(os.path.join(download_dir, "*.har*")), key=os.path.getmtime, reverse=True)[:5]

    print(f"Discovered {len(har_files)} candidate HAR files.")

    for har in har_files:
        tokens = extract_from_har(har)
        for cand in tokens:
            t = cand["token"]
            c = cand["cookie"]
            print(f"Testing candidate token ({t[:12]}...):")
            user = test_token(t, c)
            if user:
                print(f"[VALID AUTH FOUND!] Logged in as: {user.get('displayName')} (@{user.get('username')})")
                sync_to_github(t, c)
                return True
            else:
                print("  -> Expired (401)")

    print("\n[INFO] Existing HAR tokens expired.")
    print("Run with `--watch` to auto-capture when you export from Quetta/Kiwi browser:")
    print("  python3 extract_fresh_snap_auth.py --watch")
    return False


if __name__ == "__main__":
    main()

