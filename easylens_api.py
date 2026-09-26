"""
Snapchat EasyLens (LensStudioWeb) Automation Client
Implements reverse-engineered API flow extracted from easylens HAR and chunk bundles.
"""

import os
import json
import time
import uuid
import subprocess
import requests

AILC_BASE = "https://gcp.api.snapchat.com/lens-studio-web-ailc"
BOLT_BASE = "https://aws.api.snapchat.com/lens-studio-web-bolt"
SNAPML_BASE = "https://gcp.api.snapchat.com/lens-studio-web-snapml"


ACCOUNTS_BASE = "https://accounts.snapchat.com"
REPO = "gurination1/snapchat-easylens-pipeline"


def update_github_secret(secret_name: str, secret_value: str, repo: str = REPO):
    """Safely updates a GitHub repository secret using gh CLI if available."""
    if not secret_value:
        return
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not token:
        return
    try:
        subprocess.run(
            ["gh", "secret", "set", secret_name, "--repo", repo],
            input=secret_value.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        print(f"[GITHUB SECRET] Persisted {secret_name} successfully")
    except Exception as e:
        print(f"[GITHUB SECRET WARN] {secret_name}: {e}")


RETRIABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class EasyLensClient:
    def __init__(self, sso_token: str = "", cookie_header: str = "", accounts_cookie: str = "", account_id: str = "1"):
        self.account_id = str(account_id)
        self.sso_token = sso_token
        self.accounts_cookie = accounts_cookie or cookie_header
        self.cookie_header = self.accounts_cookie
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {sso_token}" if sso_token else "",
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

    def _request_with_retry(self, method: str, url: str, max_retries: int = 4, backoff_base: float = 2.0, **kwargs) -> requests.Response:
        """Robust request wrapper with exponential backoff and automatic 401 SSO ticket refresh"""
        last_exception = None
        res = None
        for attempt in range(max_retries):
            try:
                res = self.session.request(method, url, **kwargs)
                if res.status_code == 401:
                    print(f"[AUTH 401] {url} returned 401. Triggering self-healing SSO refresh (attempt {attempt+1}/{max_retries})...")
                    new_ticket = self.refresh_sso_ticket()
                    if new_ticket:
                        continue
                if res.status_code in RETRIABLE_STATUS_CODES:
                    wait_time = backoff_base ** attempt
                    print(f"[HTTP {res.status_code}] Retrying {method} {url} in {wait_time:.1f}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                return res
            except (requests.RequestException, ConnectionError, TimeoutError) as e:
                last_exception = e
                wait_time = backoff_base ** attempt
                print(f"[NET ERROR] {e}. Retrying {method} {url} in {wait_time:.1f}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_time)
        if last_exception:
            raise last_exception
        return res

    def refresh_sso_ticket(self) -> str:
        """Calls accounts.snapchat.com/accounts/sso with persistent session cookies to mint a new Bearer ticket"""
        import base64
        url = f"{ACCOUNTS_BASE}/accounts/sso"
        cookie = self.accounts_cookie or self.session.headers.get("Cookie", "")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Origin": "https://easylens.snapchat.com",
            "Referer": "https://easylens.snapchat.com/",
            "User-Agent": self.session.headers.get("User-Agent"),
            "Cookie": cookie
        }
        data = "client_id=web-ar-applier"
        try:
            print("[SSO] Requesting fresh Bearer ticket from accounts.snapchat.com/accounts/sso...")
            res = requests.post(url, headers=headers, data=data, timeout=15)
            if res.status_code == 200 and not res.text.strip().startswith("<"):
                raw = res.text.strip()
                try:
                    padded = raw + "=" * (-len(raw) % 4)
                    ticket = base64.b64decode(padded).decode("utf-8", errors="ignore").strip()
                except Exception:
                    ticket = raw
                if ticket.startswith("hCgw"):
                    print(f"[SSO SUCCESS] Minted fresh Bearer ticket: {ticket[:16]}...")
                    self.sso_token = ticket
                    self.session.headers["Authorization"] = f"Bearer {ticket}"
                    secret_name = f"SNAP_SSO_TOKEN_ACC_{self.account_id}" if self.account_id != "1" else "SNAP_SSO_TOKEN"
                    update_github_secret(secret_name, ticket)
                    return ticket
            print(f"[SSO WARN] Refresh response status {res.status_code} (body starts: {res.text[:60]})")
        except Exception as e:
            print(f"[SSO ERROR] Refresh exception: {e}")
        return ""

    def verify_auth(self):
        url = f"{SNAPML_BASE}/api/me"
        if not self.sso_token and self.accounts_cookie:
            self.refresh_sso_ticket()

        res = self._request_with_retry("GET", url, timeout=15)
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
        res = self._request_with_retry("POST", url, json=payload, timeout=20)
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
        res = self._request_with_retry("POST", url, json=payload, timeout=20)
        res.raise_for_status()
        print(f"[PROMPT SENT] Action submitted successfully: {prompt}")
        return res.json()

    def poll_lens(self, conversation_id: str, max_wait_sec: int = 180, poll_interval: int = 5):
        url = f"{AILC_BASE}/assistant/get_lens?conversation_id={conversation_id}"
        start_time = time.time()
        print(f"[POLLING] Waiting for lens generation (timeout: {max_wait_sec}s)...")
        while time.time() - start_time < max_wait_sec:
            res = self._request_with_retry("GET", url, timeout=15)
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

    @staticmethod
    def encrypt_bolt_asset(data_bytes: bytes) -> tuple[bytes, str]:
        """
        Encrypts media asset using AES-128-GCM according to Snapchat Bolt CDN requirements:
        Payload format: 12-byte IV + ciphertext + 16-byte auth tag.
        Returns: (payload_bytes, base64_encryption_key)
        """
        import base64
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = AESGCM.generate_key(bit_length=128)
        aesgcm = AESGCM(key)
        iv = os.urandom(12)
        ciphertext_and_tag = aesgcm.encrypt(iv, data_bytes, None)
        payload = iv + ciphertext_and_tag
        b64_key = base64.b64encode(key).decode("utf-8")
        return payload, b64_key

    def get_bolt_upload_location(self) -> tuple[str, str]:
        """
        Calls snapchat.content.v2.MediaDeliveryService/getUploadLocations via gRPC-Web
        Returns: (upload_url, content_url)
        """
        import re
        url = f"{BOLT_BASE}/snapchat.content.v2.MediaDeliveryService/getUploadLocations"
        headers = {
            "Content-Type": "application/grpc-web+proto",
            "x-grpc-web": "1"
        }
        # Protobuf: batchSize: 1 (field 2, varint 1: \x10\x01)
        # gRPC framing prefix: 1 byte 0x00 flag + 4 bytes big-endian length
        proto_body = b"\x10\x01"
        grpc_payload = b"\x00\x00\x00\x00\x02" + proto_body

        res = self._request_with_retry("POST", url, headers=headers, data=grpc_payload, timeout=20)
        res.raise_for_status()

        # Parse protobuf response
        raw = res.content
        upload_url = None
        content_url = None

        # 1. Wire protobuf parser
        try:
            def read_varint(data, offset):
                res_v = 0
                shift = 0
                while offset < len(data):
                    b = data[offset]
                    offset += 1
                    res_v |= (b & 0x7F) << shift
                    if not (b & 0x80):
                        break
                    shift += 7
                return res_v, offset

            if len(raw) >= 5:
                msg_len = int.from_bytes(raw[1:5], "big")
                proto_data = raw[5:5 + msg_len]
                offset = 0
                while offset < len(proto_data):
                    tag, offset = read_varint(proto_data, offset)
                    wire_type = tag & 0x07
                    field_num = tag >> 3
                    if wire_type == 2:
                        length, offset = read_varint(proto_data, offset)
                        val = proto_data[offset:offset + length]
                        offset += length
                        if field_num == 1:  # uploadLocations
                            sub_off = 0
                            while sub_off < len(val):
                                s_tag, sub_off = read_varint(val, sub_off)
                                s_wire = s_tag & 0x07
                                s_field = s_tag >> 3
                                if s_wire == 2:
                                    s_len, sub_off = read_varint(val, sub_off)
                                    s_val = val[sub_off:sub_off + s_len]
                                    sub_off += s_len
                                    if s_field == 1 and not upload_url:
                                        upload_url = s_val.decode("utf-8", errors="ignore")
                                    elif s_field == 4:  # contentReference
                                        c_off = 0
                                        while c_off < len(s_val):
                                            c_tag, c_off = read_varint(s_val, c_off)
                                            c_wire = c_tag & 0x07
                                            c_field = c_tag >> 3
                                            if c_wire == 2:
                                                c_len, c_off = read_varint(s_val, c_off)
                                                c_val = s_val[c_off:c_off + c_len]
                                                c_off += c_len
                                                if c_field == 2 and not content_url:
                                                    content_url = c_val.decode("utf-8", errors="ignore")
                                            elif c_wire == 0:
                                                _, c_off = read_varint(s_val, c_off)
                                            else:
                                                break
                                elif s_wire == 0:
                                    _, sub_off = read_varint(val, sub_off)
                                else:
                                    break
                    elif wire_type == 0:
                        _, offset = read_varint(proto_data, offset)
                    else:
                        break
        except Exception as e:
            print(f"[BOLT PROTO WARN] Wire parser error: {e}")

        # 2. Regex fallback if wire parser missed either
        if not upload_url or not content_url:
            raw_str = raw.decode("latin-1", errors="ignore")
            if not upload_url:
                m_up = re.search(r"https://[^\s\"\'\x00-\x1f]+(?:storage\.googleapis\.com|upload)[^\s\"\'\x00-\x1f]+", raw_str)
                if m_up:
                    upload_url = m_up.group(0)
            if not content_url:
                m_cdn = re.search(r"https://bolt[^\s\"\'\x00-\x1f]+", raw_str)
                if m_cdn:
                    content_url = m_cdn.group(0)

        if not upload_url or not content_url:
            raise RuntimeError(f"Could not parse upload locations from Bolt response (status {res.status_code})")

        return upload_url, content_url

    def upload_preview_video(self, video_bytes: bytes) -> tuple[str, str]:
        """
        Encrypts preview video and uploads to Bolt CDN.
        Returns: (content_url, b64_encryption_key)
        """
        if not self.sso_token and self.accounts_cookie:
            self.refresh_sso_ticket()

        print(f"[BOLT] Encrypting preview video ({len(video_bytes)} bytes) with AES-128-GCM...")
        payload, b64_key = self.encrypt_bolt_asset(video_bytes)

        print("[BOLT] Requesting pre-signed upload location from MediaDeliveryService...")
        upload_url, content_url = self.get_bolt_upload_location()

        print(f"[BOLT] Uploading encrypted payload ({len(payload)} bytes) to Bolt storage...")
        put_headers = {"Content-Type": "application/octet-stream"}
        put_res = requests.put(upload_url, headers=put_headers, data=payload, timeout=45)
        put_res.raise_for_status()

        print(f"[BOLT SUCCESS] Video uploaded successfully to: {content_url}")
        return content_url, b64_key

    @staticmethod
    def sanitize_tags(tags: list) -> list:
        """
        Sanitizes tags to strictly match Snapchat EasyLens V0 client rules:
        - Max 8 tags
        - Alphanumeric only [a-z0-9] (no spaces, punctuation, or underscores)
        - Max 15 characters per tag
        - Lowercase & deduplicated
        """
        if not tags:
            return []
        import re
        sanitized = []
        for t in tags:
            if not isinstance(t, str):
                continue
            cleaned = re.sub(r'[^a-zA-Z0-9]', '', t)[:15].lower()
            if cleaned and cleaned not in sanitized:
                sanitized.append(cleaned)
            if len(sanitized) >= 8:
                break
        return sanitized

    def publish_lens(
        self,
        conversation_id: str,
        lens_name: str,
        tags: list,
        preview_url: str = None,
        preview_encryption_key: str = None,
        icon_url: str = None,
        icon_encryption_key: str = None,
        preview_image_url: str = None,
        preview_image_encryption_key: str = None
    ):
        url = f"{AILC_BASE}/assistant/publish"
        sanitized_tags = self.sanitize_tags(tags)
        payload = {
            "conversation_id": conversation_id,
            "lens_name": lens_name,
            "tags": sanitized_tags if sanitized_tags else tags,
            "source_application": "LensStudioWeb",
            "enroll_in_payouts": True,
            "remixable": True,
            "lens_visibility": "PUBLIC"
        }
        if preview_url:
            payload["lens_preview_url"] = preview_url
            payload["preview_video_url"] = preview_url
        if preview_encryption_key:
            payload["lens_preview_encryption_key"] = preview_encryption_key
            payload["preview_video_encryption_key"] = preview_encryption_key
        if icon_url:
            payload["lens_icon_url"] = icon_url
            payload["icon_url"] = icon_url
        if icon_encryption_key:
            payload["lens_icon_encryption_key"] = icon_encryption_key
            payload["icon_encryption_key"] = icon_encryption_key
        if preview_image_url:
            payload["lens_preview_image_url"] = preview_image_url
            payload["preview_image_url"] = preview_image_url
            payload["web_lens_preview_url"] = preview_image_url
        if preview_image_encryption_key:
            payload["lens_preview_image_encryption_key"] = preview_image_encryption_key
            payload["preview_image_encryption_key"] = preview_image_encryption_key

        res = self._request_with_retry("POST", url, json=payload, timeout=25)
        res.raise_for_status()
        data = res.json()
        print(f"[PUBLISH SUBMITTED] Response: {json.dumps(data)}")
        return data

    def get_publish_status(self, checkpoint_id: str, max_wait_sec: int = 45):
        url = f"{AILC_BASE}/assistant/me/lenses?page_number=1&page_size=20&filter_by=submitted"
        start = time.time()
        while time.time() - start < max_wait_sec:
            try:
                res = self.session.get(url, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("items", []):
                        if item.get("checkpoint_id") == checkpoint_id:
                            status = item.get("status")
                            print(f"[PUBLISH STATUS] Status: {status}, Lens ID: {item.get('lens_central_lens_id')}")
                            return item
            except Exception as e:
                print(f"[STATUS CHECK WARN] Polling transient error: {e}")
            time.sleep(4)
        return None
