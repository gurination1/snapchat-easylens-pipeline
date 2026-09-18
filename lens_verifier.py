import os
import sys
import io
import json
import hashlib
import zipfile
import requests

MAX_COMPRESSED_BYTES = 8 * 1024 * 1024       # 8 MB
MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024   # 20 MB


class LensVerifier:
    def __init__(self, lens_data: dict, session: requests.Session = None):
        self.lens_data = lens_data
        self.session = session or requests.Session()
        self.report = {
            "passed": False,
            "gates": {},
            "metrics": {},
            "errors": []
        }

    def verify_all(self) -> bool:
        g1 = self.verify_metadata_status()
        g2 = self.verify_icon()
        g3, bundle_bytes = self.verify_download_and_checksum()
        g4 = self.verify_archive_boundaries(bundle_bytes) if g3 else False
        g5 = self.verify_controller_and_assets(bundle_bytes) if g4 else False

        self.report["passed"] = all([g1, g2, g3, g4, g5])
        return self.report["passed"]

    def verify_metadata_status(self) -> bool:
        """Gate 1: Ensure AILC backend flagged lens and icon as SUCCESS"""
        statuses = self.lens_data.get("asset_statuses", {})
        lens_st = statuses.get("lens", {}).get("status")
        icon_st = statuses.get("icon", {}).get("status")

        passed = (lens_st == "SUCCESS") and (icon_st == "SUCCESS")
        self.report["gates"]["gate1_metadata_status"] = {
            "passed": passed,
            "lens_status": lens_st,
            "icon_status": icon_st
        }
        if not passed:
            self.report["errors"].append(f"Gate 1 Failed: lens_status={lens_st}, icon_status={icon_st}")
        return passed

    def verify_icon(self) -> bool:
        """Gate 2: Ensure icon is downloadable, non-empty, and valid PNG"""
        icon_url = self.lens_data.get("lens_icon_download_url")
        if not icon_url:
            self.report["gates"]["gate2_icon_health"] = {"passed": False, "error": "Missing icon download URL"}
            self.report["errors"].append("Gate 2 Failed: Missing lens_icon_download_url")
            return False

        try:
            res = self.session.get(icon_url, timeout=15)
            if res.status_code != 200:
                self.report["gates"]["gate2_icon_health"] = {"passed": False, "status_code": res.status_code}
                self.report["errors"].append(f"Gate 2 Failed: Icon HTTP {res.status_code}")
                return False

            content = res.content
            # Check PNG magic header \x89PNG
            is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
            passed = is_png and len(content) > 500
            self.report["gates"]["gate2_icon_health"] = {
                "passed": passed,
                "size_bytes": len(content),
                "is_png": is_png
            }
            if not passed:
                self.report["errors"].append(f"Gate 2 Failed: Invalid PNG or corrupt icon size ({len(content)}b)")
            return passed
        except Exception as e:
            self.report["gates"]["gate2_icon_health"] = {"passed": False, "error": str(e)}
            self.report["errors"].append(f"Gate 2 Failed: Exception {e}")
            return False

    def verify_download_and_checksum(self):
        """Gate 3: Download .lns bundle and verify SHA256 integrity"""
        archive_url = self.lens_data.get("download_url") or (self.lens_data.get("lens_bundle_data") or {}).get("lens_archive_url")
        expected_checksum = self.lens_data.get("checksum") or (self.lens_data.get("lens_bundle_data") or {}).get("checksum")

        if not archive_url:
            self.report["gates"]["gate3_checksum_integrity"] = {"passed": False, "error": "Missing archive URL"}
            self.report["errors"].append("Gate 3 Failed: Missing archive URL")
            return False, None

        try:
            res = self.session.get(archive_url, timeout=30)
            if res.status_code != 200:
                self.report["gates"]["gate3_checksum_integrity"] = {"passed": False, "status_code": res.status_code}
                self.report["errors"].append(f"Gate 3 Failed: Bundle HTTP {res.status_code}")
                return False, None

            bundle_bytes = res.content
            actual_checksum = hashlib.sha256(bundle_bytes).hexdigest()

            matches = True
            if expected_checksum:
                matches = (actual_checksum.lower() == expected_checksum.lower())

            passed = matches and (len(bundle_bytes) > 1000)
            self.report["gates"]["gate3_checksum_integrity"] = {
                "passed": passed,
                "expected_checksum": expected_checksum,
                "actual_checksum": actual_checksum,
                "matches": matches,
                "downloaded_bytes": len(bundle_bytes)
            }
            if not passed:
                self.report["errors"].append(f"Gate 3 Failed: Checksum mismatch (actual={actual_checksum}, expected={expected_checksum})")
            return passed, bundle_bytes
        except Exception as e:
            self.report["gates"]["gate3_checksum_integrity"] = {"passed": False, "error": str(e)}
            self.report["errors"].append(f"Gate 3 Failed: Exception {e}")
            return False, None

    def verify_archive_boundaries(self, bundle_bytes: bytes) -> bool:
        """Gate 4: Verify compressed size < 8MB and uncompressed size < 20MB"""
        compressed_size = len(bundle_bytes)
        self.report["metrics"]["compressed_size_bytes"] = compressed_size

        if compressed_size > MAX_COMPRESSED_BYTES:
            self.report["gates"]["gate4_size_limits"] = {
                "passed": False,
                "error": f"Compressed size {compressed_size} exceeds {MAX_COMPRESSED_BYTES} limit"
            }
            self.report["errors"].append(f"Gate 4 Failed: Compressed size {compressed_size} > 8MB")
            return False

        try:
            with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as z:
                total_uncompressed = sum(info.file_size for info in z.infolist())
                file_count = len(z.infolist())

            self.report["metrics"]["uncompressed_size_bytes"] = total_uncompressed
            self.report["metrics"]["file_count"] = file_count

            passed = (total_uncompressed <= MAX_UNCOMPRESSED_BYTES)
            self.report["gates"]["gate4_size_limits"] = {
                "passed": passed,
                "compressed_size_bytes": compressed_size,
                "uncompressed_size_bytes": total_uncompressed,
                "file_count": file_count,
                "under_20mb_limit": passed
            }
            if not passed:
                self.report["errors"].append(f"Gate 4 Failed: Uncompressed size {total_uncompressed} > 20MB limit")
            return passed
        except Exception as e:
            self.report["gates"]["gate4_size_limits"] = {"passed": False, "error": f"Invalid zip: {e}"}
            self.report["errors"].append(f"Gate 4 Failed: Zip extraction error {e}")
            return False

    def verify_controller_and_assets(self, bundle_bytes: bytes) -> bool:
        """Gate 5: Verify 3D/particle prefetched assets and face event bindings"""
        prefetched = self.lens_data.get("asset_statuses", {}).get("prefetched_assets", {})
        has_assets = len(prefetched) > 0

        # Check for controller script inside archive
        controller_found = False
        event_bindings = []
        try:
            with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as z:
                for name in z.namelist():
                    if name.endswith(".js") or "controller" in name.lower():
                        content = z.read(name).decode("utf-8", errors="ignore")
                        controller_found = True
                        for trigger in ["MouthOpenedEvent", "SmileStartedEvent", "BrowsRaisedEvent", "FaceFoundEvent", "createEvent"]:
                            if trigger in content:
                                event_bindings.append(trigger)
        except Exception:
            pass

        passed = has_assets or controller_found
        self.report["gates"]["gate5_assets_and_controller"] = {
            "passed": passed,
            "prefetched_assets_count": len(prefetched),
            "prefetched_keys": list(prefetched.keys()),
            "controller_found": controller_found,
            "detected_event_bindings": event_bindings
        }
        if not passed:
            self.report["errors"].append("Gate 5 Failed: No prefetched assets or controller script found in bundle")
        return passed

    def export_report(self, filepath: str = "verification_report.json"):
        with open(filepath, "w") as f:
            json.dump(self.report, f, indent=2)
        return self.report
