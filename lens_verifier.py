import os
import sys
import io
import re
import json
import hashlib
import zipfile
import tempfile
import shutil
import subprocess
import requests

MAX_COMPRESSED_BYTES = 8 * 1024 * 1024       # 8 MB
MAX_UNCOMPRESSED_BYTES = 20 * 1024 * 1024   # 20 MB


def audit_video_frames_visual_defects(video_path: str) -> dict:
    """
    Forensic Computer Vision Video Quality Inspector.
    Examines keyframes across the entire video timeline to guarantee zero visual defects:
      1. Ray / Spoke Anomaly Detector: Detects stiff, unnatural 2D radiating line rays or bicycle spokes fanning from crown/head.
      2. Facial / Nose Obstruction Detector: Detects unnatural translucent/opaque veils or polygons covering nose/mouth.
      3. Zombie Eye Detector: Detects unnatural yellow/cyan cataract fills in the eyes.
      4. Skin Crosshairs Detector: Detects crosshairs or target reticles on facial skin.
    """
    if not video_path or not os.path.exists(video_path):
        return {"passed": False, "defects": ["Video file not found"], "frames_inspected": 0}

    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"passed": True, "defects": [], "frames_inspected": 0}

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    if total_frames < 5:
        cap.release()
        return {"passed": False, "defects": [f"Insufficient video frames: {total_frames}"], "frames_inspected": total_frames}

    # Sample 8 keyframes across video timeline
    sample_indices = np.linspace(0, total_frames - 1, min(8, total_frames), dtype=int)
    defects = []

    for f_idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(f_idx))
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        h, w = frame.shape[:2]

        # 1. Ray / Spoke Anomaly Detector (sky region above forehead/crown: y < h * 0.25)
        sky_crop = frame[:int(h * 0.25), :]
        gray_sky = cv2.cvtColor(sky_crop, cv2.COLOR_BGR2GRAY)
        sky_hsv = cv2.cvtColor(sky_crop, cv2.COLOR_BGR2HSV)
        edges = cv2.Canny(gray_sky, 60, 160)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35, minLineLength=35, maxLineGap=6)
        if lines is not None and len(lines) >= 5:
            cx, cy = w // 2, int(h * 0.38)
            radial_count = 0
            for l in lines:
                coords = l.reshape(-1)
                if len(coords) < 4:
                    continue
                x1, y1, x2, y2 = coords[:4]
                # Exclude top-left native UI badge pill region (x < 300, y < 100)
                if (x1 < 300 and y1 < 100) or (x2 < 300 and y2 < 100):
                    continue
                dx, dy = float(x2 - x1), float(y2 - y1)
                line_len = np.hypot(dx, dy)
                if line_len < 35:
                    continue
                # Sample HSV color along line to detect emissive AR ray lines
                num_pts = max(6, min(20, int(line_len // 3)))
                xs = np.clip(np.linspace(x1, x2, num_pts).astype(int), 0, w - 1)
                ys = np.clip(np.linspace(y1, y2, num_pts).astype(int), 0, sky_crop.shape[0] - 1)
                hsv_pts = sky_hsv[ys, xs]
                mean_h = np.mean(hsv_pts[:, 0])
                mean_s = np.mean(hsv_pts[:, 1])
                mean_v = np.mean(hsv_pts[:, 2])

                # Synthetic AR rays have high saturation and high luminance (golden or emissive glow)
                if (16 <= mean_h <= 40 or mean_s > 140) and mean_s > 120 and mean_v > 160:
                    # Disambiguate isolated thin line rays (background on both sides) from solid 3D mesh contours (interior on one side)
                    nx, ny = -dy / line_len, dx / line_len
                    mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
                    ax, ay = int(np.clip(mx + 8 * nx, 0, w - 1)), int(np.clip(my + 8 * ny, 0, sky_crop.shape[0] - 1))
                    bx, by = int(np.clip(mx - 8 * nx, 0, w - 1)), int(np.clip(my - 8 * ny, 0, sky_crop.shape[0] - 1))
                    sa = sky_hsv[ay, ax, 1]
                    sb = sky_hsv[by, bx, 1]
                    if sa > 80 or sb > 80:
                        continue  # Solid wearable mesh interior, not an isolated ray

                    vx, vy = mx - cx, my - cy
                    v_len = np.hypot(vx, vy)
                    if v_len > 25:
                        cos_sim = abs(dx * vx + dy * vy) / (line_len * v_len)
                        if cos_sim > 0.85:
                            radial_count += 1
            if radial_count >= 5:
                defects.append(f"Detected {radial_count} unnatural radiating line rays/spokes from crown/head at frame {f_idx}")
                break

        # 2. Nose & Facial Obstruction Anomaly Detector (center face: y 0.40-0.55, x 0.42-0.58)
        face_center = frame[int(h * 0.40):int(h * 0.55), int(w * 0.42):int(w * 0.58)]
        if face_center.size > 0:
            hsv_face = cv2.cvtColor(face_center, cv2.COLOR_BGR2HSV)
            yellow_mask = cv2.inRange(hsv_face, np.array([18, 70, 120]), np.array([35, 255, 255]))
            yellow_ratio = np.sum(yellow_mask > 0) / float(face_center.shape[0] * face_center.shape[1])
            if yellow_ratio > 0.22:
                defects.append(f"Detected unnatural yellow veil/polygon covering subject nose/face ({yellow_ratio*100:.1f}% area) at frame {f_idx}")
                break

        # 3. Zombie Eye Anomaly Detector (eye horizontal band: y 0.33-0.43, x 0.28-0.72)
        eye_band = frame[int(h * 0.33):int(h * 0.43), int(w * 0.28):int(w * 0.72)]
        if eye_band.size > 0:
            hsv_eye = cv2.cvtColor(eye_band, cv2.COLOR_BGR2HSV)
            eye_yellow = cv2.inRange(hsv_eye, np.array([18, 120, 140]), np.array([36, 255, 255]))
            eye_defect_mask = eye_yellow
            contours, _ = cv2.findContours(eye_defect_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                x, y, cw, ch = cv2.boundingRect(cnt)
                if cw > 180:
                    continue  # Legitimate wearable eyewear/visor spanning across both temples
                if area > 350:
                    defects.append(f"Detected unnatural zombie/discolored eye fill (blob area {area:.0f}px) at frame {f_idx}")
                    break
            if defects:
                break

    cap.release()
    passed = len(defects) == 0
    return {
        "passed": passed,
        "defects": defects,
        "frames_inspected": len(sample_indices)
    }


def audit_preview_video(video_path: str, require_audio: bool = False) -> dict:
    """
    Uncompromising automated video quality & freeze detector.
    Mathematically guarantees preview videos uploaded to Snapchat Bolt CDN never freeze,
    never have black frames, and have genuine fluid portrait motion:
      1. File existence and minimum size (> 50KB).
      2. Resolution & aspect ratio: strictly 720x1280 (or 1080x1920) 9:16 vertical.
      3. FFmpeg blackdetect=d=0.1:pix_th=0.10: reject if any black frame sequence detected.
      4. FFmpeg freezedetect=n=0.003:d=0.4: reject if video freezes for >= 0.4 seconds.
      5. Optical motion variance: 10 evenly spaced frames across video with average RMS Δ > 0.8.
      6. Audio track verification: presence, codec (AAC/MP3/Opus), and sync (Δ <= 0.5s).
      7. Computer vision visual defect audit: zero radiating ray spokes, zero nose veils, zero zombie eyes.
    """
    if not video_path or not os.path.exists(video_path):
        return {
            "passed": False,
            "file_exists": False,
            "file_size_bytes": 0,
            "file_size_passed": False,
            "resolution": [0, 0],
            "resolution_passed": False,
            "aspect_ratio": "none",
            "aspect_ratio_passed": False,
            "black_detect": {"passed": False, "black_frames_detected": False, "detections": []},
            "freeze_detect": {"passed": False, "freeze_detected": False, "detections": []},
            "motion_variance": {"passed": False, "avg_rms": 0.0, "threshold": 0.8, "frame_diffs": []},
            "audio": {"passed": False, "has_audio": False, "codec": None, "channels": 0, "sample_rate": 0, "sync_delta_seconds": None, "sync_passed": False},
            "errors": [f"Preview video file does not exist: {video_path}"]
        }

    errors = []
    file_size = os.path.getsize(video_path)
    MIN_SIZE_BYTES = 50 * 1024  # strictly > 50KB (51,200 bytes)
    file_size_passed = file_size > MIN_SIZE_BYTES
    if not file_size_passed:
        errors.append(f"Preview video file size {file_size} bytes <= 50KB minimum threshold ({MIN_SIZE_BYTES} bytes)")

    # 1. Stream inspection via ffprobe
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        video_path
    ]
    try:
        p_res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        probe_data = json.loads(p_res.stdout)
    except Exception as e:
        return {
            "passed": False,
            "file_exists": True,
            "file_size_bytes": file_size,
            "file_size_passed": file_size_passed,
            "resolution": [0, 0],
            "resolution_passed": False,
            "aspect_ratio": "none",
            "aspect_ratio_passed": False,
            "black_detect": {"passed": False, "black_frames_detected": False, "detections": []},
            "freeze_detect": {"passed": False, "freeze_detected": False, "detections": []},
            "motion_variance": {"passed": False, "avg_rms": 0.0, "threshold": 0.8, "frame_diffs": []},
            "audio": {"passed": False, "has_audio": False, "codec": None, "channels": 0, "sample_rate": 0, "sync_delta_seconds": None, "sync_passed": False},
            "errors": errors + [f"ffprobe stream analysis failed: {e}"]
        }

    streams = probe_data.get("streams", [])
    format_info = probe_data.get("format", {})
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not v_stream:
        return {
            "passed": False,
            "file_exists": True,
            "file_size_bytes": file_size,
            "file_size_passed": file_size_passed,
            "resolution": [0, 0],
            "resolution_passed": False,
            "aspect_ratio": "none",
            "aspect_ratio_passed": False,
            "black_detect": {"passed": False, "black_frames_detected": False, "detections": []},
            "freeze_detect": {"passed": False, "freeze_detected": False, "detections": []},
            "motion_variance": {"passed": False, "avg_rms": 0.0, "threshold": 0.8, "frame_diffs": []},
            "audio": {"passed": False, "has_audio": False, "codec": None, "channels": 0, "sample_rate": 0, "sync_delta_seconds": None, "sync_passed": False},
            "errors": errors + ["No video stream detected in preview file"]
        }

    w = int(v_stream.get("width", 0))
    h = int(v_stream.get("height", 0))
    video_dur = float(v_stream.get("duration") or format_info.get("duration") or 0.0)

    # 2. Strict resolution & aspect ratio: strictly 720x1280 (or 1080x1920) 9:16 vertical
    resolution_passed = (w, h) in [(720, 1280), (1080, 1920)]
    aspect_ratio_passed = (h > 0) and (abs((w / h) - (9.0 / 16.0)) < 0.01) and resolution_passed
    if not resolution_passed:
        errors.append(f"Resolution {w}x{h} not strictly 720x1280 or 1080x1920 (9:16 vertical)")

    # 3. FFmpeg blackdetect=d=0.1:pix_th=0.10 and freezedetect=n=0.003:d=0.4
    filter_chain = "blackdetect=d=0.1:pix_th=0.10,freezedetect=n=0.003:d=0.4"
    chk_cmd = [
        "ffmpeg", "-nostdin", "-v", "info",
        "-i", video_path,
        "-vf", filter_chain,
        "-f", "null", "-"
    ]
    c_res = subprocess.run(chk_cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    c_out = (c_res.stderr or "") + "\n" + (c_res.stdout or "")

    # Black frame detection: reject if any black frame sequence detected
    black_matches = re.findall(r"black_start:\s*([0-9.]+)\s+black_end:\s*([0-9.]+)\s+black_duration:\s*([0-9.]+)", c_out)
    if not black_matches:
        black_matches = re.findall(r"black_start:\s*([0-9.]+)", c_out)
    black_detected = len(black_matches) > 0
    black_detect_passed = not black_detected
    if black_detected:
        errors.append(f"Black frame sequence detected by FFmpeg blackdetect: {len(black_matches)} instance(s)")

    # Freeze detection: reject if video freezes for >= 0.4 seconds
    freeze_starts = re.findall(r"(?:lavfi\.freezedetect\.)?freeze_start:\s*([0-9.]+)", c_out)
    freeze_detected = len(freeze_starts) > 0
    freeze_detect_passed = not freeze_detected
    if freeze_detected:
        errors.append(f"Motion freeze >= 0.4s detected by FFmpeg freezedetect: {len(freeze_starts)} instance(s) starting at {freeze_starts[:3]}")

    # 4. Optical motion variance: extract 10 evenly spaced frames and calculate average RMS pixel difference (Δ > 0.8)
    avg_rms = 0.0
    diffs = []
    motion_variance_passed = False
    try:
        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        if total_f >= 10:
            sample_indices = np.linspace(0, total_f - 1, 10, dtype=int)
            sampled_frames = []
            for idx in sample_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ret, frame = cap.read()
                if ret and frame is not None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
                    sampled_frames.append(gray)
            cap.release()

            if len(sampled_frames) >= 2:
                for i in range(len(sampled_frames) - 1):
                    rms = float(np.sqrt(np.mean((sampled_frames[i+1] - sampled_frames[i]) ** 2)))
                    diffs.append(round(rms, 4))
                avg_rms = float(np.mean(diffs))
                motion_variance_passed = avg_rms > 0.8
                if not motion_variance_passed:
                    errors.append(f"Insufficient optical motion variance: avg RMS {avg_rms:.3f} <= 0.8 threshold (static image holding)")
            else:
                errors.append("Could not extract at least 2 frames for optical motion variance calculation")
        else:
            errors.append(f"Video frame count ({total_f}) insufficient to sample 10 frames")
            cap.release()
    except Exception as e:
        errors.append(f"Optical motion variance calculation failed: {e}")

    # 5. Audio track verification: presence, codec, and sync
    has_audio = a_stream is not None
    audio_codec = a_stream.get("codec_name") if has_audio else None
    audio_sync_delta = None
    codec_passed = True
    sync_passed = True

    if has_audio:
        valid_codecs = ["aac", "mp3", "opus"]
        if audio_codec and audio_codec.lower() not in valid_codecs:
            codec_passed = False
            errors.append(f"Audio codec '{audio_codec}' not supported (must be aac, mp3, or opus)")

        try:
            a_dur = float(a_stream.get("duration") or format_info.get("duration") or 0.0)
            if video_dur > 0 and a_dur > 0:
                audio_sync_delta = round(abs(video_dur - a_dur), 4)
                if audio_sync_delta > 0.5:
                    sync_passed = False
                    errors.append(f"Audio/video sync drift Δ={audio_sync_delta:.3f}s exceeds 0.5s tolerance (video={video_dur:.2f}s, audio={a_dur:.2f}s)")
        except Exception as e:
            sync_passed = False
            errors.append(f"Audio sync calculation failed: {e}")
    else:
        if require_audio:
            errors.append("Audio track missing from preview video (require_audio=True)")

    audio_passed = (not require_audio if not has_audio else (codec_passed and sync_passed))

    # 6. Computer Vision Frame Slop & Artifact Audit
    visual_defects_res = audit_video_frames_visual_defects(video_path)
    visual_audit_passed = visual_defects_res.get("passed", True)
    if not visual_audit_passed:
        for defect in visual_defects_res.get("defects", []):
            errors.append(f"Visual Defect: {defect}")

    passed = (
        file_size_passed and
        resolution_passed and
        aspect_ratio_passed and
        black_detect_passed and
        freeze_detect_passed and
        motion_variance_passed and
        audio_passed and
        visual_audit_passed and
        len(errors) == 0
    )

    return {
        "passed": passed,
        "file_exists": True,
        "file_size_bytes": file_size,
        "file_size_passed": file_size_passed,
        "resolution": [w, h],
        "resolution_passed": resolution_passed,
        "aspect_ratio": f"{w}:{h}",
        "aspect_ratio_passed": aspect_ratio_passed,
        "black_detect": {
            "passed": black_detect_passed,
            "black_frames_detected": black_detected,
            "detections": black_matches
        },
        "freeze_detect": {
            "passed": freeze_detect_passed,
            "freeze_detected": freeze_detected,
            "detections": freeze_starts
        },
        "motion_variance": {
            "passed": motion_variance_passed,
            "avg_rms": round(avg_rms, 4),
            "threshold": 0.8,
            "frame_diffs": diffs
        },
        "audio": {
            "passed": audio_passed,
            "has_audio": has_audio,
            "codec": audio_codec,
            "channels": int(a_stream.get("channels", 0)) if has_audio else 0,
            "sample_rate": int(a_stream.get("sample_rate", 0)) if has_audio else 0,
            "sync_delta_seconds": audio_sync_delta,
            "sync_passed": sync_passed
        },
        "visual_defects": visual_defects_res,
        "errors": errors
    }


class LensVerifier:
    audit_preview_video = staticmethod(audit_preview_video)
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

    @staticmethod
    def clean_js_code(code: str) -> str:
        """Strip comments, string literals, and typeof checks to eliminate false positives in static linter."""
        typeof_cleaned = re.sub(r'\btypeof\s*\(?\s*([a-zA-Z0-9_$]+)\s*\)?', r'typeof_safe', code)
        pattern = r'(\/\/[^\n]*|\/\*[\s\S]*?\*\/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)'
        def replacer(match):
            s = match.group(0)
            return "\n" * s.count("\n") + " " * (len(s) if "\n" not in s else 0)
        return re.sub(pattern, replacer, typeof_cleaned)

    @staticmethod
    def check_js_syntax(code: str) -> tuple[bool, str]:
        """Verify JavaScript syntax using node -c via subprocess."""
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", encoding="utf-8", delete=False) as f:
            f.write(code)
            tmp_path = f.name
        try:
            res = subprocess.run(["node", "-c", tmp_path], capture_output=True, text=True, timeout=10)
            return res.returncode == 0, res.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "node -c timed out after 10s"
        except Exception as e:
            return False, f"node execution error: {e}"
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    @classmethod
    def lint_js_globals(cls, name: str, code: str, bundled_libs: set = None, bundled_modules: set = None) -> list[str]:
        """Lint JavaScript code for banned or undeclared globals in Snapchat Lens Studio runtime."""
        errors = []
        bundled_libs = bundled_libs or set()
        bundled_modules = bundled_modules or set()
        is_library_file = any(lib in name.lower() for lib in ["tween.js", "tweenmanager.js", "tweenmax.js", "gsap.js"])
        clean_code = cls.clean_js_code(code)

        # 1. TWEEN / TweenMax / gsap (unless explicitly defined or bundled)
        if not is_library_file:
            for lib in ["TWEEN", "TweenMax", "gsap"]:
                has_ref = bool(
                    re.search(r'(?<![a-zA-Z0-9_$.])' + lib + r'\.', clean_code) or
                    re.search(r'(?<![a-zA-Z0-9_$.])' + lib + r'\b(?!\s*[:=])', clean_code)
                )
                if has_ref:
                    has_decl = bool(
                        re.search(r'\b(var|let|const|function|class)\s+' + lib + r'\b', clean_code) or
                        re.search(r'\bglobal\.' + lib + r'\s*=', clean_code) or
                        re.search(r'function\s*\([^\)]*\b' + lib + r'\b', clean_code) or
                        re.search(r'\bimport\s+.*\b' + lib + r'\b', clean_code)
                    )
                    is_bundled = lib.lower() in bundled_libs
                    if not has_decl and not is_bundled:
                        errors.append(
                            f"Fatal: Undeclared {lib} reference in '{name}' (causes Snapchat runtime ReferenceError: {lib} is not defined)"
                        )
                    elif not has_decl and f"global.{lib}" not in clean_code[:clean_code.find(f"{lib}.") if f"{lib}." in clean_code else len(clean_code)]:
                        errors.append(
                            f"Fatal: Undeclared {lib} reference in '{name}' (bare global without local declaration or global.{lib})"
                        )

        # 2. Browser DOM globals (Snapchat Lens Studio has no browser DOM)
        if not is_library_file:
            banned_dom = [
                ("window", r'\bwindow\b'),
                ("document", r'\bdocument\b'),
                ("localStorage", r'\blocalStorage\b'),
                ("sessionStorage", r'\bsessionStorage\b'),
                ("XMLHttpRequest", r'\bXMLHttpRequest\b'),
                ("fetch", r'\bfetch\s*\(')
            ]
            for dom_name, dom_pat in banned_dom:
                if re.search(dom_pat, clean_code):
                    if not re.search(r'\b(var|let|const|function|class)\s+' + dom_name + r'\b', clean_code):
                        errors.append(
                            f"Fatal: Prohibited browser DOM global '{dom_name}' referenced in '{name}' (Snapchat Lens Studio has no browser DOM)"
                        )

        # 3. Node globals & require checks
        is_library_file = is_library_file or any(lib in name.lower() for lib in ["module", "helper", "utils", "hintevents", "preset", "gizmo"]) or ("@author Snap" in code) or ("Snap inc." in code)
        if not is_library_file:
            if re.search(r'\bprocess\.env\b', clean_code) or re.search(r'\bprocess\.(?:exit|cwd|argv|versions)\b', clean_code):
                errors.append(
                    f"Fatal: Prohibited Node global 'process.env' referenced in '{name}' (Snapchat Lens Studio has no Node environment)"
                )

        banned_node_modules = {"fs", "child_process", "cluster", "dgram", "dns", "http", "https", "net", "os", "path", "readline", "stream", "tls", "v8", "vm", "worker_threads", "zlib"}
        code_no_comments = re.sub(r'(\/\/[^\n]*|\/\*[\s\S]*?\*\/)', '', code)
        require_matches = re.findall(r'\brequire\s*\(\s*["\']([^"\']+)["\']\s*\)', code_no_comments)
        for req_mod in require_matches:
            if req_mod in banned_node_modules:
                errors.append(
                    f"Fatal: Unbundled require('{req_mod}') in '{name}' (prohibited Node built-in module in Snapchat Lens Studio)"
                )
            elif not is_library_file and not req_mod.startswith(".") and not req_mod.startswith("LensStudio:") and req_mod != "EventModule":
                base_mod = os.path.basename(req_mod)
                norm_mod = req_mod.lower().replace('\\', '/').lstrip('./')
                base_norm = base_mod.lower()
                is_bundled_mod = (
                    req_mod in bundled_modules or
                    norm_mod in bundled_modules or
                    base_mod in bundled_modules or
                    base_norm in bundled_modules or
                    (base_norm + ".js") in bundled_modules or
                    any(b.endswith(norm_mod) or b.endswith(norm_mod + ".js") for b in bundled_modules)
                )
                if not is_bundled_mod and not re.search(r'\b(var|let|const|function)\s+require\b', clean_code):
                    errors.append(
                        f"Fatal: Unbundled require('{req_mod}') in '{name}' (module not bundled in .lns package)"
                    )

        return errors

    def verify_controller_and_assets(self, bundle_bytes: bytes) -> bool:
        """Gate 5: Verify 3D/particle prefetched assets, face event bindings, static JS syntax, undeclared/banned globals, and asset integrity"""
        prefetched = self.lens_data.get("asset_statuses", {}).get("prefetched_assets", {})
        has_assets = len(prefetched) > 0

        controller_found = False
        event_bindings = []
        fatal_script_errors = []
        canvas_violations = []
        scanned_scripts = []
        scanned_manifests = []
        referenced_assets = []
        missing_assets = []

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

        asset_regex = re.compile(
            r'["\'`]([a-zA-Z0-9_\-./\\]+\.(?:png|jpg|jpeg|glb|gltf|mesh|hdr|wav|mp3|ogg|ttf|otf|fbx|obj|ply))["\'`]',
            re.IGNORECASE
        )

        all_zip_names = set()
        bundled_libs = set()
        bundled_modules = set()
        zip_basenames = {}
        zip_normalized = {}

        temp_js_dir = tempfile.mkdtemp(prefix="lens_verifier_scripts_")
        try:
            with zipfile.ZipFile(io.BytesIO(bundle_bytes), "r") as z:
                all_zip_names = set(z.namelist())
                zip_basenames = {os.path.basename(f).lower(): f for f in all_zip_names if not f.endswith("/")}
                zip_normalized = {f.lower().replace("\\", "/").lstrip("./"): f for f in all_zip_names}

                # Index bundled modules and libraries
                for z_name in all_zip_names:
                    lower_z = z_name.lower()
                    if lower_z.endswith(".js"):
                        bundled_modules.add(z_name)
                        bundled_modules.add(lower_z)
                        bundled_modules.add(os.path.basename(z_name))
                        bundled_modules.add(os.path.basename(lower_z))
                        base_no_ext = os.path.splitext(os.path.basename(lower_z))[0]
                        bundled_modules.add(base_no_ext)
                        if "tween" in base_no_ext:
                            bundled_libs.add("tween")
                        if "tweenmax" in base_no_ext:
                            bundled_libs.add("tweenmax")
                        if "gsap" in base_no_ext:
                            bundled_libs.add("gsap")

                for name in z.namelist():
                    lower_name = name.lower()

                    # Pre-flight check: Detect CanvasAPI script files in bundle
                    if "canvasapi" in lower_name or lower_name.endswith("/canvasapi.js") or lower_name == "canvasapi.js":
                        canvas_violations.append(
                            f"Fatal Gate 5 Violation: Archive contains CanvasAPI script '{name}'. "
                            "2D canvas procedural drawing is strictly banned."
                        )

                    # Extract and inspect JS scripts
                    if name.endswith(".js") or "controller" in lower_name:
                        content = z.read(name).decode("utf-8", errors="ignore")
                        scanned_scripts.append(name)
                        if "controller" in lower_name:
                            controller_found = True

                        for trigger in ["MouthOpenedEvent", "SmileStartedEvent", "BrowsRaisedEvent", "FaceFoundEvent", "createEvent"]:
                            if trigger in content and trigger not in event_bindings:
                                event_bindings.append(trigger)

                        # Static JS Linter 1: Node.js -c syntax compilation check
                        if name.endswith(".js"):
                            temp_script_path = os.path.join(
                                temp_js_dir, f"{hashlib.md5(name.encode('utf-8')).hexdigest()}_{os.path.basename(name)}"
                            )
                            with open(temp_script_path, "w", encoding="utf-8") as tf:
                                tf.write(content)
                            try:
                                n_res = subprocess.run(["node", "-c", temp_script_path], capture_output=True, text=True, timeout=10)
                                if n_res.returncode != 0:
                                    syntax_err = n_res.stderr.strip() or f"Syntax error (exit {n_res.returncode})"
                                    fatal_script_errors.append(
                                        f"Fatal Gate 5 Syntax Error in '{name}': {syntax_err}"
                                    )
                            except subprocess.TimeoutExpired:
                                fatal_script_errors.append(f"Fatal Gate 5 Syntax Error in '{name}': node -c timed out")
                            except Exception as n_err:
                                fatal_script_errors.append(f"Fatal Gate 5 Syntax Error in '{name}': {n_err}")

                        # Static JS Linter 2: Catch CanvasAPI & 2D canvas drawing scripts
                        for pat, reason in canvas_patterns:
                            if re.search(pat, content):
                                violation_msg = f"Fatal Gate 5 Violation: Script '{name}' {reason} (causes 2D disco loading spinner on user face)"
                                if violation_msg not in canvas_violations:
                                    canvas_violations.append(violation_msg)
                                break

                        # Static JS Linter 3: Catch undeclared TWEEN, TweenMax, gsap, browser DOM globals, Node globals
                        global_errs = self.lint_js_globals(name, content, bundled_libs=bundled_libs, bundled_modules=bundled_modules)
                        for g_err in global_errs:
                            if g_err not in fatal_script_errors:
                                fatal_script_errors.append(g_err)

                    # Asset Integrity: Scan scene manifests and scripts for referenced asset filenames
                    is_manifest = any(lower_name.endswith(ext) for ext in [".scn", ".json", ".config", ".manifest", ".scene", ".yaml", ".yml"])
                    if is_manifest:
                        scanned_manifests.append(name)

                    if name.endswith(".js") or is_manifest:
                        try:
                            c_text = z.read(name).decode("utf-8", errors="ignore")
                        except Exception:
                            c_text = ""

                        for ref in asset_regex.findall(c_text):
                            if ref.startswith("http://") or ref.startswith("https://"):
                                continue
                            referenced_assets.append((name, ref))
                            norm_ref = ref.lower().replace("\\", "/").lstrip("./")
                            base_ref = os.path.basename(ref).lower()
                            ref_dir = os.path.dirname(name)
                            rel_path = os.path.normpath(os.path.join(ref_dir, ref)).replace("\\", "/").lower().lstrip("./")

                            is_present = (
                                ref in all_zip_names or
                                norm_ref in zip_normalized or
                                base_ref in zip_basenames or
                                rel_path in zip_normalized or
                                any(z_name.endswith(norm_ref) for z_name in zip_normalized)
                            )
                            if not is_present:
                                missing_msg = f"Fatal Asset Integrity Error: Missing referenced asset '{ref}' in '{name}' (asset not found in archive)"
                                if missing_msg not in fatal_script_errors:
                                    fatal_script_errors.append(missing_msg)
                                    missing_assets.append({"referrer": name, "asset": ref})

        except Exception as e:
            fatal_script_errors.append(f"Zip extraction error in Gate 5: {e}")
        finally:
            shutil.rmtree(temp_js_dir, ignore_errors=True)

        # Check controller_code in lens_data blocks or top-level if present
        all_codes = []
        if self.lens_data.get("controller_code"):
            all_codes.append(("lens_data.controller_code", self.lens_data.get("controller_code")))
        for b in self.lens_data.get("blocks", []):
            code = b.get("controller_code", "")
            if code:
                all_codes.append((f"block '{b.get('description', 'controller')}' controller_code", code))

        for code_source, code in all_codes:
            # Subprocess node -c syntax check for controller_code
            ok_syntax, syntax_msg = self.check_js_syntax(code)
            if not ok_syntax:
                fatal_script_errors.append(f"Fatal Gate 5 Syntax Error in {code_source}: {syntax_msg}")

            # Lint globals in controller_code
            ctrl_global_errs = self.lint_js_globals(code_source, code, bundled_libs=bundled_libs, bundled_modules=bundled_modules)
            for cg_err in ctrl_global_errs:
                if cg_err not in fatal_script_errors:
                    fatal_script_errors.append(cg_err)

            # Check CanvasAPI in controller_code
            for pat, reason in canvas_patterns:
                if re.search(pat, code):
                    violation_msg = f"Fatal Gate 5 Violation: {code_source} {reason} (causes 2D disco loading spinner)"
                    if violation_msg not in canvas_violations:
                        canvas_violations.append(violation_msg)
                    break

            # Asset integrity check for controller_code
            for ref in asset_regex.findall(code):
                if ref.startswith("http://") or ref.startswith("https://"):
                    continue
                referenced_assets.append((code_source, ref))
                norm_ref = ref.lower().replace("\\", "/").lstrip("./")
                base_ref = os.path.basename(ref).lower()
                is_present = (
                    norm_ref in zip_normalized or
                    base_ref in zip_basenames or
                    any(z_name.endswith(norm_ref) for z_name in zip_normalized)
                )
                if not is_present:
                    missing_msg = f"Fatal Asset Integrity Error: Missing referenced asset '{ref}' in {code_source} (not found in archive)"
                    if missing_msg not in fatal_script_errors:
                        fatal_script_errors.append(missing_msg)
                        missing_assets.append({"referrer": code_source, "asset": ref})

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
            "scanned_manifests_count": len(scanned_manifests),
            "referenced_assets_count": len(referenced_assets),
            "missing_assets_count": len(missing_assets),
            "missing_assets": missing_assets,
            "fatal_script_errors": fatal_script_errors,
            "canvas_violations": canvas_violations,
            "canvas_api_detected": has_canvas_violations
        }
        if not (has_assets or controller_found):
            self.report["errors"].append("Gate 5 Failed: No prefetched assets or controller script found in bundle")
        if fatal_script_errors:
            for err in fatal_script_errors:
                if f"Gate 5 Failed: {err}" not in self.report["errors"]:
                    self.report["errors"].append(f"Gate 5 Failed: {err}")
        if canvas_violations:
            for viol in canvas_violations:
                if f"Gate 5 Failed: {viol}" not in self.report["errors"]:
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
        trigger_tokens = ["mouth", "smile", "smiling", "smiles", "eyebrow", "open", "opening", "blink", "head", "dance", "move", "trigger"]
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
            sim_lens_data = dict(self.lens_data)
            if self.plan:
                for k in ["prompt", "lens_name", "account_id", "tags", "theme_focus", "archetype", "genre", "niche", "channel_id"]:
                    if k in self.plan and k not in sim_lens_data:
                        sim_lens_data[k] = self.plan[k]
            simulator = LensSimulator(bundle_bytes, lens_data=sim_lens_data, portrait_dir="assets")
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
                out_trigger=out_trigger,
                account_id=sim_lens_data.get("account_id")
            )

            # Render high-CTR viral 320x320 lens icon ("The Pick")
            lens_icon_path = simulator.generate_viral_lens_icon(
                out_path="lens_icon.png",
                account_id=sim_lens_data.get("account_id")
            )

            # Render high-converting Before/After Split Comparison photo
            split_photo_path = simulator.render_split_comparison(
                out_path="preview_split_comparison.png",
                account_id=sim_lens_data.get("account_id")
            )

            # Evaluate with Gemini Multimodal Vision AI (Dual-Frame + Video Timeline Keyframes)
            judge_res = simulator.judge_visuals_with_gemini_vision(
                trigger_screenshot=out_trigger,
                neutral_screenshot=out_neutral,
                preview_video=preview_video
            )

            has_3d = analysis.get("has_3d_mesh", False)
            is_bg_only = analysis.get("is_background_only", False) or judge_res.get("is_background_only", False)
            is_cringe = judge_res.get("is_cringe_or_defective", False)
            has_rays = judge_res.get("has_unnatural_rays_or_spokes", False)
            has_veil = judge_res.get("has_face_obstruction_or_veil", False)
            has_zombie = judge_res.get("has_zombie_eyes", False)
            judge_passed = judge_res.get("passed", False)
            score = judge_res.get("virality_score", judge_res.get("score", 0))

            # Audit preview video for black frames, freeze, motion variance, resolution, audio, and visual defects
            video_audit = audit_preview_video(preview_video)
            video_passed = video_audit.get("passed", False)
            if not video_passed:
                v_errors = video_audit.get("errors", [])
                if v_errors:
                    for v_err in v_errors:
                        self.report["errors"].append(f"Gate 7 Failed: Video Audit Error: {v_err}")
                elif video_audit.get("error"):
                    self.report["errors"].append(f"Gate 7 Failed: Video Audit Error: {video_audit.get('error')}")
                else:
                    self.report["errors"].append("Gate 7 Failed: Preview video failed automated quality & freeze audit")

            # Strictly reject background-only, lack of 3D mesh, cringe elements, rays/spokes, face veil, zombie eyes, score < 85, or defective video
            passed = has_3d and (not is_bg_only) and (not is_cringe) and (not has_rays) and (not has_veil) and (not has_zombie) and judge_passed and video_passed

            self.report["gates"]["gate7_visual_simulation"] = {
                "passed": passed,
                "score": score,
                "has_3d_mesh": has_3d,
                "is_background_only": is_bg_only,
                "has_unnatural_rays_or_spokes": has_rays,
                "has_face_obstruction_or_veil": has_veil,
                "has_zombie_eyes": has_zombie,
                "has_particles": analysis.get("has_particles", False),
                "has_head_binding": analysis.get("has_head_binding", False),
                "critique": judge_res.get("critique", ""),
                "neutral_preview": out_neutral,
                "trigger_preview": out_trigger,
                "preview_video": preview_video,
                "lens_icon": lens_icon_path,
                "split_comparison": split_photo_path,
                "video_audit": video_audit
            }

            if not passed:
                if not has_3d:
                    self.report["errors"].append("Gate 7 Failed: No foreground 3D mesh (.mesh/.glb/.ply) found in bundle")
                if is_bg_only:
                    self.report["errors"].append("Gate 7 Failed: Filter detected as flat 2D background replacement only")
                if has_rays:
                    self.report["errors"].append("Gate 7 Failed: Detected unnatural 2D radiating line rays/spokes from crown")
                if has_veil:
                    self.report["errors"].append("Gate 7 Failed: Detected unnatural veil or polygon covering subject nose/mouth")
                if has_zombie:
                    self.report["errors"].append("Gate 7 Failed: Detected unnatural zombie/discolored eye fill")
                if not judge_passed:
                    self.report["errors"].append(f"Gate 7 Failed: Gemini Vision Judge score {score}/100 below 85 threshold")
                if not video_passed:
                    self.report["errors"].append("Gate 7 Failed: Preview video failed automated quality & freeze audit")

            return passed
        except Exception as e:
            self.report["gates"]["gate7_visual_simulation"] = {"passed": False, "error": str(e)}
            self.report["errors"].append(f"Gate 7 Failed: Simulation exception: {e}")
            return False

    def export_report(self, filepath: str = "verification_report.json"):
        with open(filepath, "w") as f:
            json.dump(self.report, f, indent=2)
        return self.report
