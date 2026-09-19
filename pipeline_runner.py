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

# Proven PBR fallbacks per account persona if Gemini is not used
STATIC_FALLBACKS = {
    "1": {
        "prompt": "Sculpted obsidian dragon horn crown anchored strictly to hairline and temples with liquid 24k gold filigree and caustic ruby gems, PBR anisotropic metallic reflections, 3-point contrast 6500K/2800K lighting with ray-traced contact shadows. Mouth open erupts turbulent emerald flame torrent with floating amber sparks; smiling ignites alpha-fading golden runic eye halos. Depth occlusion enabled, zero strobing.",
        "lens_name": "Aether Dragon Crown",
        "tags": ["dragon", "3d", "headpiece", "horns", "fantasy", "pbr"]
    },
    "2": {
        "prompt": "Sleek ergonomic 3D cyberpunk HUD glasses and holographic visor resting strictly across eyes, leaving cheeks and mouth completely uncovered for clean tracking. Brushed titanium frame with pulsing cyan neon edge emission and refractive glass. Orbiting audio-reactive equalizer bars halo head. 3-point contrast lighting with ray-traced shadows. Opening mouth triggers radial laser shockwave; smiling activates bright neon visor HUD readout. Zero strobing, zero easing curves.",
        "lens_name": "Chrono Echo Visor",
        "tags": ["cyberpunk", "visor", "rave", "music", "audioreactive", "neon"]
    },
    "3": {
        "prompt": "Fluffy 3D cartoon stormcloud hovering directly above head with gentle glowing rain droplets and soft ambient thunder light. PBR volumetric stylization, 3-point contrast lighting. Opening mouth erupts an exaggerated geyser of liquid mercury tears and spinning 24k gold coins bouncing off screen frame; smiling triggers a dramatic cartoon lightning rim flash. Physics-driven, zero strobe.",
        "lens_name": "Stormcloud Tears",
        "tags": ["meme", "crying", "funny", "cloud", "cartoon", "morph"]
    },
    "4": {
        "prompt": "Sculpted 24k gold leaf baroque crown fitted strictly to hairline and temples with pale champagne crystal halo and caustic crystal prisms. Warm Kodak Portra 35mm film halation with colorCorrection 10 Golden Glow and grain. Anisotropic PBR reflections, ray-traced shadows. Smiling unleashes rich golden sparkle dust cascading across cheekbones. Photosensitive safe, zero strobing.",
        "lens_name": "Haute Baroque Gold",
        "tags": ["film", "35mm", "crown", "gold", "luxury", "aesthetic"]
    },
    "5": {
        "prompt": "Zero-G floating liquid mercury halo crown morphing above head with sculpted chrome cheek plates. Anisotropic mirror PBR reflections with fluid surface tension, 3-point contrast lighting and ray-traced contact shadows. Opening mouth releases orbiting liquid chrome spheres with refractive rippling reflections; smiling ripples the ambient background. Seamless physics, zero strobing.",
        "lens_name": "Liquid Chrome Mirage",
        "tags": ["surreal", "chrome", "halo", "optical", "cyber", "mirage"]
    }
}
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
    # Check if credentials exist for the targeted account
    has_creds = bool(sso_token or username or (aid == "1" and os.getenv("SNAP_SSO_TOKEN")))
    if not has_creds:
        # Dynamically discover configured active accounts (1..5)
        active_accounts = []
        for cand in ["1", "2", "3", "4", "5"]:
            c_tok = os.getenv(f"SNAP_SSO_TOKEN_ACC_{cand}") or (os.getenv("SNAP_SSO_TOKEN") if cand == "1" else None)
            c_usr = os.getenv(f"SNAP_USERNAME_ACC_{cand}") or (os.getenv("SNAP_USERNAME") if cand == "1" else None)
            if c_tok or c_usr:
                active_accounts.append(cand)

        if active_accounts:
            fallback_aid = active_accounts[(int(aid) - 1) % len(active_accounts)]
            print(f"[ACCOUNT RELIABILITY GUARD] Account #{aid} credentials not yet in secrets.")
            print(f"[ACCOUNT RELIABILITY GUARD] Auto-routing to active Account #{fallback_aid} (out of active: {active_accounts}) to prevent missed shift!")
            return resolve_account_auth(fallback_aid)

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

    # Determine per-account static fallback defaults
    active_fallback = STATIC_FALLBACKS.get(str(ACCOUNT_ID), STATIC_FALLBACKS["1"])
    static_prompt = os.getenv("LENS_PROMPT") or active_fallback["prompt"]
    static_lens_name = os.getenv("LENS_NAME") or active_fallback["lens_name"]
    static_tags = [t.strip() for t in (os.getenv("LENS_TAGS") or ",".join(active_fallback["tags"])).split(",")]

    # Multi-attempt Generation & 7-Gate Verification Loop
    MAX_ATTEMPTS = 2
    passed = False
    report = {}
    gemini_plan = None
    lens_data = None
    checkpoint_id = None
    prompt = None
    lens_name = None
    tags = None
    cid = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n{'='*60}")
        print(f"=== PIPELINE GENERATION ATTEMPT {attempt}/{MAX_ATTEMPTS} (ACCOUNT #{ACCOUNT_ID}) ===")
        print(f"{'='*60}")

        current_instructions = CUSTOM_INSTRUCTIONS
        if attempt > 1:
            err_summary = "; ".join(report.get("errors", []))
            current_instructions = (
                f"{CUSTOM_INSTRUCTIONS} [STRICT RETRY]: Previous attempt failed verification with errors: {err_summary}. "
                "CRITICAL: Zero easing curves, zero TWEEN references, zero UI sliders, pure native triggers only!"
            ).strip()

        # Step 0: Determine Prompt, Lens Name, and Tags
        if USE_GEMINI:
            print(f"\n=== STEP 0: AUTONOMOUS GEMINI PROMPT ARCHITECT (ACCOUNT #{ACCOUNT_ID}, ATTEMPT {attempt}) ===")
            try:
                gemini_plan = generate_lens_prompt(account_id=ACCOUNT_ID, custom_instructions=current_instructions)
                prompt = gemini_plan["prompt"]
                lens_name = gemini_plan["lens_name"]
                tags = gemini_plan.get("tags", static_tags)
                with open("gemini_generation_plan.json", "w") as f:
                    json.dump(gemini_plan, f, indent=2)
                print(f"[GEMINI SUCCESS] Lens: {lens_name}")
                print(f"[GEMINI SUCCESS] Hook: {gemini_plan.get('visual_hook')}")
            except Exception as e:
                print(f"[GEMINI WARN] Gemini synthesis failed ({e}), falling back to persona #{ACCOUNT_ID} static prompt...")
                prompt = static_prompt
                lens_name = static_lens_name
                tags = static_tags
        else:
            prompt = static_prompt
            lens_name = static_lens_name
            tags = static_tags

        print(f"\n=== STEP 2: CREATING LENS CONVERSATION (ATTEMPT {attempt}) ===")
        cid = client.create_conversation()

        print(f"\n=== STEP 3: SUBMITTING PROMPT TO SNAPCHAT AILC (ATTEMPT {attempt}) ===")
        print(f"Prompt: {prompt}")
        client.send_prompt(cid, prompt)

        print(f"\n=== STEP 4: POLLING FOR LENS GENERATION (ATTEMPT {attempt}) ===")
        lens_data = client.poll_lens(cid, max_wait_sec=200)

        checkpoint_id = lens_data.get("checkpoint_id")
        archive_url = lens_data.get("download_url") or (lens_data.get("lens_bundle_data") or {}).get("lens_archive_url")
        checksum = lens_data.get("checksum") or (lens_data.get("lens_bundle_data") or {}).get("checksum")
        icon_url = lens_data.get("lens_icon_download_url")

        # Save metadata
        with open("generated_lens_metadata.json", "w") as f:
            json.dump(lens_data, f, indent=2)

        print(f"\n=== STEP 5: 7-GATE COMPREHENSIVE LENS & JUDGE AI VERIFICATION (ATTEMPT {attempt}) ===")
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

        if passed:
            print(f"\n[VERIFICATION OK] Attempt {attempt} passed all 7 quality & compliance gates!")
            break
        else:
            print(f"\n[VERIFICATION WARNING] Attempt {attempt} failed verification: {report.get('errors')}")
            if attempt < MAX_ATTEMPTS:
                print(f"[AUTO-HEAL] Re-attempting generation with strict corrective anti-TWEEN instructions...")

    if not passed:
        print("\n[FATAL ERROR] All generation attempts failed verification! Aborting publish to protect account catalog.")
        print(f"Final Errors: {json.dumps(report.get('errors', []), indent=2)}")
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
