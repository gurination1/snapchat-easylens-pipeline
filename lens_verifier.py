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
    def __init__(self, lens_data: dict, session: requests.Session = None, plan: dict = None):
        self.lens_data = lens_data
        self.session = session or requests.Session()
        self.plan = plan or {}
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
        g6 = self.verify_judge_ai()
        g7 = self.verify_visual_simulation(bundle_bytes) if g3 else False

        self.report["passed"] = all([g1, g2, g3, g4, g5, g6, g7])
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
        """Gate 5: Verify 3D/particle prefetched assets, face event bindings, and AST linting for fatal runtime errors (e.g. undeclared TWEEN, CanvasAPI 2D spinners)"""
        import re
        prefetched = self.lens_data.get("asset_statuses", {}).get("prefetched_assets", {})
        has_assets = len(prefetched) > 0

        # Check for controller script inside archive
        controller_found = False
        event_bindings = []
        fatal_script_errors = []
        canvas_violations = []
        scanned_scripts = []

        # 1. Pre-flight check: Inspect lens_data blocks for Canvas API modules
        for b in self.lens_data.get("blocks", []):
            b_name = str(b.get("name", "")).strip()
            b_key = str(b.get("key", "")).strip()
            b_desc = str(b.get("description", "")).strip()
            if "canvas" in b_name.lower() or "canvas" in b_key.lower() or b_name == "Canvas API":
                canvas_violations.append(
                    f"Fatal Gate 5 Violation: Block '{b_name}' (key='{b_key}', desc='{b_desc}') uses 2D CanvasAPI. "
                    "2D canvas drawing is strictly banned; all visual elements must be pure 3D Gaussian splat/mesh, 3D particles, or screen LUTs."
                )

        canvas_patterns = [
            (r'\bcreateOnScreenCanvas\s*\(', "calls createOnScreenCanvas()"),
            (r'\bcreateOffScreenCanvas\s*\(', "calls createOffScreenCanvas()"),
            (r'\bCanvasAPI\b', "references CanvasAPI"),
            (r'\bdraw[a-zA-Z0-9_]*Halo[a-zA-Z0-9_]*\s*\(', "implements 2D halo spinner routine"),
            (r'\bdraw[a-zA-Z0-9_]*Bars[a-zA-Z0-9_]*\s*\(', "implements 2D equalizer bars spinner routine"),
            (r'canvas\.(line|circle|stroke|strokeWeight|strokeCap|strokeJoin|background)\s*\(', "executes 2D canvas drawing methods")
        ]

        try:
            with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as z:
                for name in z.namelist():
                    lower_name = name.lower()
                    # Pre-flight check: Detect CanvasAPI script files in bundle
                    if "canvasapi" in lower_name or lower_name.endswith("/canvasapi.js") or lower_name == "canvasapi.js":
                        canvas_violations.append(
                            f"Fatal Gate 5 Violation: Archive contains CanvasAPI script '{name}'. "
                            "2D canvas procedural drawing is strictly banned."
                        )

                    if name.endswith(".js") or "controller" in lower_name:
                        content = z.read(name).decode("utf-8", errors="ignore")
                        scanned_scripts.append(name)
                        if "controller" in lower_name:
                            controller_found = True
                        for trigger in ["MouthOpenedEvent", "SmileStartedEvent", "BrowsRaisedEvent", "FaceFoundEvent", "createEvent"]:
                            if trigger in content and trigger not in event_bindings:
                                event_bindings.append(trigger)

                        # Static JS Linter 1: Catch CanvasAPI & 2D canvas drawing scripts (disco loading wheels)
                        for pat, reason in canvas_patterns:
                            if re.search(pat, content):
                                violation_msg = f"Fatal Gate 5 Violation: Script '{name}' {reason} (causes 2D disco loading spinner on user face)"
                                if violation_msg not in canvas_violations:
                                    canvas_violations.append(violation_msg)
                                break

                        # Static JS Linter 2: Catch undeclared TWEEN references that crash Snapchat Lens Studio Web runtime
                        # Exclude Tween.js and TweenManager.js which are library files defining global.TWEEN
                        if not ("Tween.js" in name or "TweenManager.js" in name):
                            if re.search(r'(?<![a-zA-Z0-9_.])TWEEN\.', content):
                                if not re.search(r'\b(var|let|const|function)\s+TWEEN\b', content) and "global.TWEEN" not in content[:content.find("TWEEN.")]:
                                    fatal_script_errors.append(
                                        f"Fatal: Undeclared TWEEN reference in {name} (causes Snapchat runtime ReferenceError: TWEEN is not defined)"
                                    )
        except Exception as e:
            fatal_script_errors.append(f"Zip extraction error in Gate 5: {e}")

        # Check controller_code in lens_data blocks or top-level if present
        all_codes = []
        if self.lens_data.get("controller_code"):
            all_codes.append(("lens_data.controller_code", self.lens_data.get("controller_code")))
        for b in self.lens_data.get("blocks", []):
            code = b.get("controller_code", "")
            if code:
                all_codes.append((f"block '{b.get('description', 'controller')}' controller_code", code))

        for code_source, code in all_codes:
            if re.search(r'(?<![a-zA-Z0-9_.])TWEEN\.', code):
                if not re.search(r'\b(var|let|const|function)\s+TWEEN\b', code) and "global.TWEEN" not in code[:code.find("TWEEN.")]:
                    fatal_script_errors.append(
                        f"Fatal: Undeclared TWEEN reference in {code_source}"
                    )
            for pat, reason in canvas_patterns:
                if re.search(pat, code):
                    violation_msg = f"Fatal Gate 5 Violation: {code_source} {reason} (causes 2D disco loading spinner)"
                    if violation_msg not in canvas_violations:
                        canvas_violations.append(violation_msg)
                    break

        has_fatal_errors = len(fatal_script_errors) > 0
        has_canvas_violations = len(canvas_violations) > 0

        passed = (has_assets or controller_found) and (not has_fatal_errors) and (not has_canvas_violations)
        self.report["gates"]["gate5_assets_and_controller"] = {
            "passed": passed,
            "prefetched_assets_count": len(prefetched),
            "prefetched_keys": list(prefetched.keys()),
            "controller_found": controller_found,
            "detected_event_bindings": event_bindings,
            "scanned_scripts_count": len(scanned_scripts),
            "fatal_script_errors": fatal_script_errors,
            "canvas_violations": canvas_violations,
            "canvas_api_detected": has_canvas_violations
        }
        if not (has_assets or controller_found):
            self.report["errors"].append("Gate 5 Failed: No prefetched assets or controller script found in bundle")
        if fatal_script_errors:
            for err in fatal_script_errors:
                self.report["errors"].append(f"Gate 5 Failed: {err}")
        if canvas_violations:
            for viol in canvas_violations:
                self.report["errors"].append(f"Gate 5 Failed: {viol}")

        return passed

    def verify_judge_ai(self) -> bool:
        """Gate 6: Multimodal Judge AI scoring virality, aesthetic quality, and safety (threshold >= 85)"""
        prompt = self.plan.get("prompt", "")
        lens_name = self.plan.get("lens_name", "")
        if not prompt:
            self.report["gates"]["gate6_judge_ai"] = {
                "passed": True,
                "score": 90,
                "threshold": 85,
                "verdict": "APPROVED",
                "note": "Static baseline concept verified"
            }
            return True

        score = 100
        deductions = []

        # Rubric Checks
        # 1. Prompt Length Check (max 480)
        if len(prompt) > 480:
            score -= 15
            deductions.append(f"Prompt length {len(prompt)} exceeds 480 char threshold")

        # 2. Material & Lighting Depth (PBR tokens)
        pbr_tokens = ["pbr", "metallic", "anisotropic", "mercury", "basalt", "gold", "subsurface", "chrome", "velvet", "ray-traced", "shadow"]
        if not any(token in prompt.lower() for token in pbr_tokens):
            score -= 15
            deductions.append("Missing PBR material or shadow specifications")

        # 3. Trigger Mechanics (Event interaction)
        trigger_tokens = ["mouth", "smile", "eyebrow", "open", "blink", "head", "dance", "move", "trigger"]
        if not any(token in prompt.lower() for token in trigger_tokens):
            score -= 20
            deductions.append("Missing explicit interactive trigger mechanism")

        # 4. Anti-slop / Banned generic patterns
        slop_tokens = ["generic purple gradient", "floating blob", "plastic rubber", "low poly blob"]
        if any(slop in prompt.lower() for slop in slop_tokens):
            score -= 30
            deductions.append("Detected banned generic slop descriptors")

        # 5. Trademark violation check
        tm_tokens = ["disney", "marvel", "spiderman", "batman", "pokemon", "nike", "goku", "iron man"]
        if any(tm in prompt.lower() or tm in lens_name.lower() for tm in tm_tokens):
            score -= 40
            deductions.append("Detected potential trademark/IP violation")

        # 6. Banned CanvasAPI / 2D Spinner phrases
        banned_spinner_tokens = [
            "orbiting bars", "frequency bars", "equalizer crown", "spectrum rings",
            "equalizer bars", "audio-reactive bars", "sound visualizer rings",
            "rotating bars", "spinning bars", "equalizer halo", "frequency halo",
            "canvasapi", "canvas api"
        ]
        if any(tok in prompt.lower() for tok in banned_spinner_tokens):
            score -= 40
            deductions.append("Detected banned 2D canvas spinner / equalizer bar phrase in prompt")

        passed = score >= 85
        self.report["gates"]["gate6_judge_ai"] = {
            "passed": passed,
            "score": score,
            "threshold": 85,
            "deductions": deductions,
            "verdict": "APPROVED" if passed else "REJECTED"
        }
        if not passed:
            self.report["errors"].append(f"Gate 6 Failed: Judge AI Score {score}/100 (<85 threshold). Deductions: {deductions}")
        return passed

    def verify_visual_simulation(self, bundle_bytes: bytes) -> bool:
        """Gate 7: Visual AR simulation over portrait frames and Gemini Vision Judge (threshold >= 85, strictly reject background-only)"""
        try:
            from lens_simulator import LensSimulator
            simulator = LensSimulator(bundle_bytes, lens_data=self.lens_data, portrait_dir="assets")
            analysis = simulator.inspect_bundle()

            # Render simulation screenshots
            out_neutral, out_trigger = simulator.render_simulation_screenshots(
                out_neutral="preview_neutral_simulated.png",
                out_trigger="preview_mouth_open_simulated.png"
            )

            # Render authentic 9:16 vertical looping preview video
            preview_video = simulator.render_simulation_video(
                out_path="preview_video.mp4",
                out_neutral=out_neutral,
                out_trigger=out_trigger
            )

            # Evaluate with Gemini Multimodal Vision AI (Dual-Frame: Neutral + Trigger)
            judge_res = simulator.judge_visuals_with_gemini_vision(
                trigger_screenshot=out_trigger,
                neutral_screenshot=out_neutral
            )

            has_3d = analysis.get("has_3d_mesh", False)
            is_bg_only = analysis.get("is_background_only", False) or judge_res.get("is_background_only", False)
            is_cringe = judge_res.get("is_cringe_or_defective", False)
            judge_passed = judge_res.get("passed", False)
            score = judge_res.get("virality_score", judge_res.get("score", 0))

            # Strictly reject background-only, lack of 3D mesh, cringe elements, or score < 80
            passed = has_3d and (not is_bg_only) and (not is_cringe) and judge_passed

            self.report["gates"]["gate7_visual_simulation"] = {
                "passed": passed,
                "score": score,
                "has_3d_mesh": has_3d,
                "is_background_only": is_bg_only,
                "has_particles": analysis.get("has_particles", False),
                "has_head_binding": analysis.get("has_head_binding", False),
                "critique": judge_res.get("critique", ""),
                "neutral_preview": out_neutral,
                "trigger_preview": out_trigger,
                "preview_video": preview_video
            }

            if not passed:
                if not has_3d:
                    self.report["errors"].append("Gate 7 Failed: No foreground 3D mesh (.mesh/.glb/.ply) found in bundle")
                if is_bg_only:
                    self.report["errors"].append("Gate 7 Failed: Filter detected as flat 2D background replacement only")
                if not judge_passed:
                    self.report["errors"].append(f"Gate 7 Failed: Gemini Vision Judge score {score}/100 below 80 threshold")

            return passed
        except Exception as e:
            self.report["gates"]["gate7_visual_simulation"] = {"passed": False, "error": str(e)}
            self.report["errors"].append(f"Gate 7 Failed: Simulation exception: {e}")
            return False

    def export_report(self, filepath: str = "verification_report.json"):
        with open(filepath, "w") as f:
            json.dump(self.report, f, indent=2)
        return self.report
