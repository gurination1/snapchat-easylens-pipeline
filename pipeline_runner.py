import os
import sys
import json
from easylens_api import EasyLensClient
from lens_verifier import LensVerifier
from gemini_lens_agent import generate_lens_prompt

SSO_TOKEN = os.getenv("SNAP_SSO_TOKEN")
COOKIE_HEADER = os.getenv("SNAP_COOKIE_HEADER", "")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "1")
USE_GEMINI = (os.getenv("USE_GEMINI") or "false").lower() == "true"
CUSTOM_INSTRUCTIONS = os.getenv("CUSTOM_INSTRUCTIONS", "")

# Fallbacks if Gemini is not used
STATIC_PROMPT = os.getenv("LENS_PROMPT") or "Photorealistic 3D miniature obsidian wyvern perched securely on user's right shoulder with ray-traced contact shadows. Opening mouth unleashes synchronized volumetric fire breath with flying embers and heat distortion. Dark volcanic caldera background with warm rim lighting."
STATIC_LENS_NAME = os.getenv("LENS_NAME") or "Obsidian Pyrodrake 3D"
STATIC_TAGS = [t.strip() for t in (os.getenv("LENS_TAGS") or "dragon,3d,creature,fantasy,pbr").split(",")]
AUTO_PUBLISH = (os.getenv("AUTO_PUBLISH") or "true").lower() == "true"


def main():
    if not SSO_TOKEN:
        print("[ERROR] SNAP_SSO_TOKEN environment variable is required!")
        print("Please set SNAP_SSO_TOKEN in GitHub repository secrets.")
        sys.exit(1)

    # 1. Determine Prompt, Lens Name, and Tags
    if USE_GEMINI:
        print(f"=== STEP 0: AUTONOMOUS GEMINI PROMPT ARCHITECT (ACCOUNT #{ACCOUNT_ID}) ===")
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

    client = EasyLensClient(sso_token=SSO_TOKEN, cookie_header=COOKIE_HEADER)

    print("\n=== STEP 1: VERIFYING SNAPCHAT AUTHENTICATION ===")
    user = client.verify_auth()
    print(f"Logged in as: {user.get('displayName')} (@{user.get('username')})")

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

    print("\n=== STEP 5: 5-GATE COMPREHENSIVE LENS VERIFICATION ===")
    verifier = LensVerifier(lens_data=lens_data, session=client.session)
    passed = verifier.verify_all()
    report = verifier.export_report("verification_report.json")

    print(f"Gate 1 (Metadata Status): {report['gates']['gate1_metadata_status']['passed']}")
    print(f"Gate 2 (Icon Health):     {report['gates']['gate2_icon_health']['passed']}")
    print(f"Gate 3 (Checksum Hash):   {report['gates']['gate3_checksum_integrity']['passed']}")
    print(f"Gate 4 (Size Boundaries): {report['gates']['gate4_size_limits']['passed']} (Compressed: {report['metrics'].get('compressed_size_bytes', 0) // 1024}KB, Unpacked: {report['metrics'].get('uncompressed_size_bytes', 0) // 1024}KB)")
    print(f"Gate 5 (Assets & Events): {report['gates']['gate5_assets_and_controller']['passed']}")
    print(f"OVERALL VERIFICATION VERDICT: {'PASSED (100%)' if passed else 'FAILED'}")

    if not passed:
        print("\n[FATAL ERROR] Lens verification failed! Aborting publish to protect account catalog.")
        print(f"Errors: {json.dumps(report['errors'], indent=2)}")
        sys.exit(1)

    if AUTO_PUBLISH:
        print("\n=== STEP 6: PUBLISHING VERIFIED LENS TO SNAPCHAT CATALOG ===")
        final_lens_name = lens_name or lens_data.get("lens_name") or "Obsidian Pyrodrake 3D"
        pub_res = client.publish_lens(
            conversation_id=cid,
            lens_name=final_lens_name,
            tags=tags
        )
        print("Publish response:", pub_res)

        if checkpoint_id:
            print("\n=== STEP 7: MONITORING SNAPCODE & SUBMISSION STATUS ===")
            status_data = client.get_publish_status(checkpoint_id)
            if status_data:
                print(f"[SUCCESS] Published Lens ID: {status_data.get('lens_central_lens_id')}")
                print(f"[SUCCESS] Catalog Status: {status_data.get('status')}")
                with open("publish_status.json", "w") as f:
                    json.dump(status_data, f, indent=2)

    print("\n=== PIPELINE FINISHED SUCCESSFULLY WITH 100% VERIFICATION ===")


if __name__ == "__main__":
    main()
