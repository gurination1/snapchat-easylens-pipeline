"""
Snapchat EasyLens (LensStudioWeb) Automation Client
Implements reverse-engineered API flow extracted from easylens HAR and chunk bundles.
"""

import json
import time
import uuid
import requests

AILC_BASE = "https://gcp.api.snapchat.com/lens-studio-web-ailc"
BOLT_BASE = "https://aws.api.snapchat.com/lens-studio-web-bolt"
SNAPML_BASE = "https://gcp.api.snapchat.com/lens-studio-web-snapml"


class EasyLensClient:
    def __init__(self, sso_token: str, cookie_header: str = ""):
        self.sso_token = sso_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {sso_token}",
            "Origin": "https://easylens.snapchat.com",
            "Referer": "https://easylens.snapchat.com/",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36",
            "x-snap-client-user-agent": "LensStudioWeb/2.56.0 PROD (K; android 10) Chrome/143 Core/372 AppId/easylens.snapchat.com",
            "sec-ch-ua": '"Quetta";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site"
        })
        if cookie_header:
            self.session.headers["Cookie"] = cookie_header

    def verify_auth(self):
        url = f"{SNAPML_BASE}/api/me"
        res = self.session.get(url, timeout=15)
        if res.status_code == 200:
            user_data = res.json()
            print(f"[AUTH OK] User: {user_data.get('displayName')} (@{user_data.get('username')})")
            return user_data
        raise RuntimeError(f"Auth failed ({res.status_code}): {res.text}")

    def create_conversation(self):
        url = f"{AILC_BASE}/assistant/new_conversation_v2"
        payload = {
            "contentful_stage": "master",
            "contentful_environment": "master",
            "model_ver": "",
            "client": "web",
            "plugin_ver": "1.0",
            "supports_planning": True,
            "supports_reasoning_summaries": True,
            "supports_tool_calls": False
        }
        res = self.session.post(url, json=payload, timeout=20)
        res.raise_for_status()
        data = res.json()
        cid = data.get("conversation_id")
        print(f"[CONVERSATION CREATED] ID: {cid}")
        return cid

    def send_prompt(self, conversation_id: str, prompt: str):
        url = f"{AILC_BASE}/assistant/v1/conversations/{conversation_id}/perform_action"
        payload = {
            "action": "SendPrompt",
            "action_id": str(uuid.uuid4()),
            "expected_version": 0,
            "payload": {
                "prompt": prompt,
                "attachments": []
            }
        }
        res = self.session.post(url, json=payload, timeout=20)
        res.raise_for_status()
        print(f"[PROMPT SENT] Action submitted successfully: {prompt}")
        return res.json()

    def poll_lens(self, conversation_id: str, max_wait_sec: int = 180, poll_interval: int = 5):
        url = f"{AILC_BASE}/assistant/get_lens?conversation_id={conversation_id}"
        start_time = time.time()
        print(f"[POLLING] Waiting for lens generation (timeout: {max_wait_sec}s)...")
        while time.time() - start_time < max_wait_sec:
            res = self.session.get(url, timeout=15)
            if res.status_code == 200:
                lens = res.json()
                archive_url = lens.get("download_url") or (lens.get("lens_bundle_data") or {}).get("lens_archive_url")
                if archive_url:
                    print("[LENS GENERATED SUCCESS]")
                    print(f"Lens Name: {lens.get('lens_name')}")
                    print(f"Checkpoint ID: {lens.get('checkpoint_id')}")
                    print(f"Archive URL: {archive_url}")
                    print(f"Checksum: {lens.get('checksum')}")
                    print(f"Icon URL: {lens.get('lens_icon_download_url')}")
                    return lens
            time.sleep(poll_interval)
        raise TimeoutError("Lens generation polling timed out.")

    def publish_lens(self, conversation_id: str, lens_name: str, tags: list, preview_url: str = None, icon_url: str = None):
        url = f"{AILC_BASE}/assistant/publish"
        payload = {
            "conversation_id": conversation_id,
            "lens_name": lens_name,
            "tags": tags,
            "source_application": "LensStudioWeb",
            "remixable": True,
            "lens_visibility": "PUBLIC"
        }
        if preview_url:
            payload["lens_preview_url"] = preview_url
        if icon_url:
            payload["lens_icon_url"] = icon_url

        res = self.session.post(url, json=payload, timeout=25)
        res.raise_for_status()
        data = res.json()
        print(f"[PUBLISH SUBMITTED] Response: {json.dumps(data)}")
        return data

    def get_publish_status(self, checkpoint_id: str, max_wait_sec: int = 120):
        url = f"{AILC_BASE}/assistant/me/lenses?page_number=1&page_size=20&filter_by=submitted"
        start = time.time()
        while time.time() - start < max_wait_sec:
            res = self.session.get(url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                for item in data.get("items", []):
                    if item.get("checkpoint_id") == checkpoint_id:
                        status = item.get("status")
                        print(f"[PUBLISH STATUS] Status: {status}, Lens ID: {item.get('lens_central_lens_id')}")
                        return item
            time.sleep(4)
        return None
