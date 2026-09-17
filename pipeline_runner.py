import os
import sys
import json
from easylens_api import EasyLensClient

SSO_TOKEN = os.getenv("SNAP_SSO_TOKEN")
COOKIE_HEADER = os.getenv("SNAP_COOKIE_HEADER", "")
PROMPT = os.getenv(
    "LENS_PROMPT",
    "Create a Greek mythology lens inspired by Tiresias and Cassius: ancient marble temple ruins with glowing ethereal oracle runes, mystic golden laurel, and mythical interactive particle effects reacting to user facial movements"
)
LENS_NAME = os.getenv("LENS_NAME", "Greek Myth - Cassius Oracle")
TAGS = [t.strip() for t in os.getenv("LENS_TAGS", "greek,mythology,cassius,oracle").split(",")]
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "true").lower() == "true"


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

    bundle = lens_data.get("lens_bundle_data") or {}
    checkpoint_id = lens_data.get("checkpoint_id")

    print("\n=== LENS VERIFICATION RESULTS ===")
    print(f"Checkpoint ID: {checkpoint_id}")
    print(f"Archive URL: {bundle.get('lens_archive_url')}")
    print(f"Checksum: {bundle.get('checksum')}")
    print(f"Preview Video: {bundle.get('preview_video_url')}")

    # Save output metadata for GHA artifact upload
    with open("generated_lens_metadata.json", "w") as f:
        json.dump(lens_data, f, indent=2)

    if AUTO_PUBLISH:
        print("\n=== STEP 5: PUBLISHING LENS TO SNAPCHAT ===")
        preview_url = bundle.get("preview_video_url") or bundle.get("preview_image_url")
        icon_url = bundle.get("preview_image_url")
        pub_res = client.publish_lens(
            conversation_id=cid,
            lens_name=LENS_NAME,
            tags=TAGS,
            preview_url=preview_url,
            icon_url=icon_url
        )
        print("Publish response:", pub_res)

        if checkpoint_id:
            print("\n=== STEP 6: MONITORING SNAPCODE & PUBLISH STATUS ===")
            status_data = client.get_publish_status(checkpoint_id)
            if status_data:
                print(f"[SUCCESS] Lens Snapcode: {status_data.get('snapcode')}")
                print(f"[SUCCESS] Status: {status_data.get('state')}")
                with open("publish_status.json", "w") as f:
                    json.dump(status_data, f, indent=2)

    print("\n=== PIPELINE FINISHED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
