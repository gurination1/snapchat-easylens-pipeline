import os
import sys
import json
from easylens_api import EasyLensClient

SSO_TOKEN = os.getenv("SNAP_SSO_TOKEN")
COOKIE_HEADER = os.getenv("SNAP_COOKIE_HEADER", "")
PROMPT = os.getenv("LENS_PROMPT") or "Create a Greek mythology lens inspired by Tiresias and Cassius: ancient marble temple ruins with glowing ethereal oracle runes, mystic golden laurel, and mythical interactive particle effects reacting to user facial movements"
LENS_NAME = os.getenv("LENS_NAME") or "Greek Myth - Cassius Oracle"
TAGS = [t.strip() for t in (os.getenv("LENS_TAGS") or "greek,mythology,cassius,oracle").split(",")]
AUTO_PUBLISH = (os.getenv("AUTO_PUBLISH") or "true").lower() == "true"


def main():
    if not SSO_TOKEN:
        print("[ERROR] SNAP_SSO_TOKEN environment variable is required!")
        print("Please set SNAP_SSO_TOKEN in GitHub repository secrets.")
        sys.exit(1)

    client = EasyLensClient(sso_token=SSO_TOKEN, cookie_header=COOKIE_HEADER)

    print("=== STEP 1: VERIFYING SNAPCHAT AUTHENTICATION ===")
    user = client.verify_auth()
    print(f"Logged in as: {user.get('displayName')} (@{user.get('username')})")

    print("\n=== STEP 2: CREATING LENS CONVERSATION ===")
    cid = client.create_conversation()

    print("\n=== STEP 3: SUBMITTING PROMPT TO AILC ===")
    client.send_prompt(cid, PROMPT)

    print("\n=== STEP 4: POLLING FOR LENS GENERATION & VERIFICATION ===")
    lens_data = client.poll_lens(cid, max_wait_sec=180)

    checkpoint_id = lens_data.get("checkpoint_id")
    archive_url = lens_data.get("download_url") or (lens_data.get("lens_bundle_data") or {}).get("lens_archive_url")
    checksum = lens_data.get("checksum") or (lens_data.get("lens_bundle_data") or {}).get("checksum")
    icon_url = lens_data.get("lens_icon_download_url")

    print("\n=== LENS VERIFICATION RESULTS ===")
    print(f"Generated Lens Name: {lens_data.get('lens_name')}")
    print(f"Checkpoint ID: {checkpoint_id}")
    print(f"Archive URL: {archive_url}")
    print(f"Checksum: {checksum}")
    print(f"Icon URL: {icon_url}")

    # Save output metadata for GHA artifact upload
    with open("generated_lens_metadata.json", "w") as f:
        json.dump(lens_data, f, indent=2)

    if AUTO_PUBLISH:
        print("\n=== STEP 5: PUBLISHING LENS TO SNAPCHAT ===")
        final_lens_name = LENS_NAME or lens_data.get("lens_name") or "Greek Myth - Cassius Oracle"
        pub_res = client.publish_lens(
            conversation_id=cid,
            lens_name=final_lens_name,
            tags=TAGS
        )
        print("Publish response:", pub_res)

        if checkpoint_id:
            print("\n=== STEP 6: MONITORING SNAPCODE & PUBLISH STATUS ===")
            status_data = client.get_publish_status(checkpoint_id)
            if status_data:
                print(f"[SUCCESS] Lens ID: {status_data.get('lens_central_lens_id')}")
                print(f"[SUCCESS] Status: {status_data.get('status')}")
                with open("publish_status.json", "w") as f:
                    json.dump(status_data, f, indent=2)

    print("\n=== PIPELINE FINISHED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
