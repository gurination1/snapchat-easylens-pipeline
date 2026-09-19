import os
import sys
import json

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

from easylens_api import EasyLensClient
from lens_verifier import LensVerifier
from gemini_lens_agent import generate_lens_prompt

SSO_TOKEN = os.getenv("SNAP_SSO_TOKEN")
COOKIE_HEADER = os.getenv("SNAP_COOKIE_HEADER", "")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "1")
USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() not in ("false", "0", "no")
CUSTOM_INSTRUCTIONS = os.getenv("CUSTOM_INSTRUCTIONS", "")

# Proven PBR head-anchored fallback if Gemini is not used
STATIC_PROMPT = os.getenv("LENS_PROMPT") or "Fitted mythic 3D dragon horn headpiece anchored strictly to head, crafted from anisotropic obsidian scales and liquid 24k gold filigree. 3-point contrast lighting with warm key light, cool 6500K rim light, and ray-traced contact shadows. Opening mouth triggers flowing emerald flame particles and rising embers. Smiling activates bright golden runic eye flares. PBR materials, no strobing, ultra-realistic."
STATIC_LENS_NAME = os.getenv("LENS_NAME") or "Aether Dragon Crown"
STATIC_TAGS = [t.strip() for t in (os.getenv("LENS_TAGS") or "dragon,3d,headpiece,horns,fantasy,pbr").split(",")]
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "true").lower() not in ("false", "0", "no")


def resolve_account_auth(account_id: str):
    aid = str(account_id)
    sso_token = (
        os.getenv(f"SNAP_SSO_TOKEN_ACC_{aid}")
        or os.getenv(f"SNAP_SSO_TOKEN_{aid}")
        or (os.getenv("SNAP_SSO_TOKEN") if aid == "1" else None)
    )
    cookie_header = (
        os.getenv(f"SNAP_COOKIE_HEADER_ACC_{aid}")
        or os.getenv(f"SNAP_COOKIE_HEADER_{aid}")
        or (os.getenv("SNAP_COOKIE_HEADER") if aid == "1" else "")
    )
    accounts_cookie = (
        os.getenv(f"SNAP_ACCOUNTS_COOKIE_ACC_{aid}")
        or os.getenv(f"SNAP_ACCOUNTS_COOKIE_{aid}")
        or (os.getenv("SNAP_ACCOUNTS_COOKIE") if aid == "1" else cookie_header)
    )
    username = (
        os.getenv(f"SNAP_USERNAME_ACC_{aid}")
        or os.getenv(f"SNAP_USERNAME_{aid}")
        or (os.getenv("SNAP_USERNAME") if aid == "1" else None)
    )
    password = (
        os.getenv(f"SNAP_PASSWORD_ACC_{aid}")
        or os.getenv(f"SNAP_PASSWORD_{aid}")
        or (os.getenv("SNAP_PASSWORD") if aid == "1" else None)
    )
    return sso_token, cookie_header, accounts_cookie, username, password


def main():
    sso_token, cookie_header, accounts_cookie, username, password = resolve_account_auth(ACCOUNT_ID)
    client = EasyLensClient(
        sso_token=sso_token,
        cookie_header=cookie_header,
        accounts_cookie=accounts_cookie,
        account_id=ACCOUNT_ID
    )

    print(f"\n=== STEP 1: VERIFYING SNAPCHAT AUTHENTICATION (ACCOUNT #{ACCOUNT_ID}) ===")
    user = None
    try:
        if sso_token or accounts_cookie:
            user = client.verify_auth()
    except Exception as e:
        print(f"[AUTH EXPIRED / 401] Initial auth check failed ({e}). Triggering autonomous recovery...")

    if not user:
        print(f"[AUTO-AUTH] Calling Autonomous Snapchat Auth Automator for Account #{ACCOUNT_ID}...")
        try:
            from snap_auth_automator import obtain_valid_snap_session
            fresh_session = obtain_valid_snap_session(
                account_id=ACCOUNT_ID,
                username=username,
                password=password
            )
            client = EasyLensClient(
                sso_token=fresh_session["ticket"],
                cookie_header=fresh_session.get("cookie_header", ""),
                accounts_cookie=fresh_session.get("cookie_header", ""),
                account_id=ACCOUNT_ID
            )
            user = fresh_session.get("user") or client.verify_auth()
        except Exception as auth_err:
            print(f"[FATAL AUTH ERROR] Autonomous auth failed: {auth_err}")
            sys.exit(1)

    print(f"Logged in as: {user.get('displayName')} (@{user.get('username')})")

    # Step 0: Determine Prompt, Lens Name, and Tags
    gemini_plan = None
    if USE_GEMINI:
        print(f"\n=== STEP 0: AUTONOMOUS GEMINI PROMPT ARCHITECT (ACCOUNT #{ACCOUNT_ID}) ===")
        try:
            gemini_plan = generate_lens_prompt(account_id=ACCOUNT_ID, custom_instructions=CUSTOM_INSTRUCTIONS)
            prompt = gemini_plan["prompt"]
            lens_name = gemini_plan["lens_name"]
            tags = gemini_plan.get("tags", STATIC_TAGS)
            with open("gemini_generation_plan.json", "w") as f:
                json.dump(gemini_plan, f, indent=2)
            print(f"[GEMINI SUCCESS] Lens: {lens_name}")
            print(f"[GEMINI SUCCESS] Hook: {gemini_plan.get('visual_hook')}")
        except Exception as e:
            print(f"[GEMINI WARN] Gemini synthesis failed ({e}), falling back to static prompt...")
            prompt = STATIC_PROMPT
            lens_name = STATIC_LENS_NAME
            tags = STATIC_TAGS
    else:
        prompt = STATIC_PROMPT
        lens_name = STATIC_LENS_NAME
        tags = STATIC_TAGS

    print("\n=== STEP 2: CREATING LENS CONVERSATION ===")
    cid = client.create_conversation()

    print("\n=== STEP 3: SUBMITTING PROMPT TO SNAPCHAT AILC ===")
    print(f"Prompt: {prompt}")
    client.send_prompt(cid, prompt)

    print("\n=== STEP 4: POLLING FOR LENS GENERATION ===")
    lens_data = client.poll_lens(cid, max_wait_sec=200)

    checkpoint_id = lens_data.get("checkpoint_id")
    archive_url = lens_data.get("download_url") or (lens_data.get("lens_bundle_data") or {}).get("lens_archive_url")
    checksum = lens_data.get("checksum") or (lens_data.get("lens_bundle_data") or {}).get("checksum")
    icon_url = lens_data.get("lens_icon_download_url")

    # Save metadata
    with open("generated_lens_metadata.json", "w") as f:
        json.dump(lens_data, f, indent=2)

    print("\n=== STEP 5: 7-GATE COMPREHENSIVE LENS & JUDGE AI VERIFICATION ===")
    plan_data = gemini_plan if USE_GEMINI else {"prompt": prompt, "lens_name": lens_name}
    verifier = LensVerifier(lens_data=lens_data, session=client.session, plan=plan_data)
    passed = verifier.verify_all()
    report = verifier.export_report("verification_report.json")

    print(f"Gate 1 (Metadata Status): {report['gates'].get('gate1_metadata_status', {}).get('passed')}")
    print(f"Gate 2 (Icon Health):     {report['gates'].get('gate2_icon_health', {}).get('passed')}")
    print(f"Gate 3 (Checksum Hash):   {report['gates'].get('gate3_checksum_integrity', {}).get('passed')}")
    print(f"Gate 4 (Size Boundaries): {report['gates'].get('gate4_size_limits', {}).get('passed')} (Compressed: {report['metrics'].get('compressed_size_bytes', 0) // 1024}KB, Unpacked: {report['metrics'].get('uncompressed_size_bytes', 0) // 1024}KB)")
    print(f"Gate 5 (Assets & Events): {report['gates'].get('gate5_assets_and_controller', {}).get('passed')}")
    print(f"Gate 6 (Judge AI Score):  {report['gates'].get('gate6_judge_ai', {}).get('passed')} ({report['gates'].get('gate6_judge_ai', {}).get('score')}/100 - {report['gates'].get('gate6_judge_ai', {}).get('verdict')})")
    g7 = report['gates'].get('gate7_visual_simulation', {})
    print(f"Gate 7 (Vision Simulation): {g7.get('passed')} (Score: {g7.get('score')}/100, 3D Mesh: {g7.get('has_3d_mesh')}, BG Only: {g7.get('is_background_only')})")
    print(f"OVERALL VERIFICATION VERDICT: {'PASSED (100%)' if passed else 'FAILED'}")

    if not passed:
        print("\n[FATAL ERROR] Lens verification failed! Aborting publish to protect account catalog.")
        print(f"Errors: {json.dumps(report['errors'], indent=2)}")
        sys.exit(1)

    if AUTO_PUBLISH:
        print("\n=== STEP 6: PUBLISHING VERIFIED LENS TO SNAPCHAT CATALOG ===")
        final_lens_name = lens_name or lens_data.get("lens_name") or "Obsidian Pyrodrake 3D"

        # Check for simulated preview video from Gate 7
        preview_url = None
        preview_key = None
        preview_path = g7.get("preview_video") or "preview_video.mp4"
        if os.path.exists(preview_path):
            print("\n=== STEP 5.5: UPLOADING AES-128-GCM PREVIEW VIDEO TO BOLT CDN ===")
            try:
                with open(preview_path, "rb") as f:
                    v_bytes = f.read()
                preview_url, preview_key = client.upload_preview_video(v_bytes)
                print(f"[PREVIEW VIDEO OK] CDN URL: {preview_url}")
                print(f"[PREVIEW VIDEO OK] AES Key: {preview_key[:10]}...")
            except Exception as e:
                print(f"[PREVIEW VIDEO WARN] Bolt upload failed ({e}). Proceeding without preview video.")

        pub_res = client.publish_lens(
            conversation_id=cid,
            lens_name=final_lens_name,
            tags=tags,
            preview_url=preview_url,
            preview_encryption_key=preview_key
        )
        print("Publish response:", pub_res)

        status_data = None
        if checkpoint_id:
            print("\n=== STEP 7: MONITORING SNAPCODE & SUBMISSION STATUS ===")
            status_data = client.get_publish_status(checkpoint_id)
            if status_data:
                print(f"[SUCCESS] Published Lens ID: {status_data.get('lens_central_lens_id')}")
                print(f"[SUCCESS] Catalog Status: {status_data.get('status')}")
                with open("publish_status.json", "w") as f:
                    json.dump(status_data, f, indent=2)

        # Record into deduplication state file (persisted in git like yt-auto)
        import time
        history_file = "published_lenses.json"
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except Exception:
                history = []

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "account_id": str(ACCOUNT_ID),
            "lens_name": final_lens_name,
            "lens_id": (status_data or {}).get("lens_central_lens_id") or pub_res.get("lens_central_lens_id"),
            "checkpoint_id": checkpoint_id,
            "prompt": prompt,
            "tags": tags,
            "visual_hook": (gemini_plan or {}).get("visual_hook", "") if USE_GEMINI else "",
            "has_preview_video": bool(preview_url),
            "preview_url": preview_url,
            "status": (status_data or {}).get("status", "pending")
        }
        history.append(entry)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
        print(f"[STATE] Recorded '{final_lens_name}' to {history_file} (Total fleet lenses: {len(history)})")

    print("\n=== PIPELINE FINISHED SUCCESSFULLY WITH 100% VERIFICATION ===")


if __name__ == "__main__":
    main()
