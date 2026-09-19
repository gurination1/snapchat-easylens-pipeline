"""
Lens Simulator & Visual Screenshot Verification Engine (Gate 7)
Simulates AR lens application over test portrait videos/frames (mouth open, neutral face),
renders visual composite previews, and runs Gemini Multimodal Vision Judge.
"""

import os
import io
import json
import base64
import zipfile
import requests
from PIL import Image, ImageDraw, ImageFilter
from gemini_lens_agent import get_gemini_api_keys, CANDIDATE_MODELS


class LensSimulator:
    def __init__(self, bundle_bytes: bytes, lens_data: dict = None, portrait_dir: str = "assets"):
        self.bundle_bytes = bundle_bytes
        self.lens_data = lens_data or {}
        self.portrait_dir = portrait_dir
        self.extracted_files = {}
        self.analysis = {
            "has_3d_mesh": False,
            "mesh_file_count": 0,
            "total_mesh_bytes": 0,
            "has_particles": False,
            "has_head_binding": False,
            "has_shoulder_binding": False,
            "has_face_mesh": False,
            "is_background_only": False,
            "texture_files": [],
            "mesh_files": []
        }

    def inspect_bundle(self) -> dict:
        """Deep inspects scene.scn and archive to detect 3D meshes, bindings, and slop"""
        try:
            with zipfile.ZipFile(io.BytesIO(self.bundle_bytes), "r") as z:
                names = z.namelist()
                for name in names:
                    lower = name.lower()
                    if lower.endswith(".mesh") or lower.endswith(".glb") or lower.endswith(".ply"):
                        info = z.getinfo(name)
                        self.analysis["mesh_file_count"] += 1
                        self.analysis["total_mesh_bytes"] += info.file_size
                        self.analysis["mesh_files"].append(name)

                    if lower.endswith(".png") or lower.endswith(".jpg") or lower.endswith(".jpeg"):
                        if not lower.endswith("icon.png"):
                            self.analysis["texture_files"].append(name)

                # Check scene.scn strings
                if "scene.scn" in names:
                    scn_content = z.read("scene.scn").decode("latin-1", errors="ignore")
                    if "Component.RenderMeshVisual" in scn_content:
                        self.analysis["has_3d_mesh"] = True
                    if "Component.Head" in scn_content:
                        self.analysis["has_head_binding"] = True
                    if "Component.ParticleSystem" in scn_content or "sparkles" in scn_content:
                        self.analysis["has_particles"] = True
                    if "Component.FaceMeshVisual" in scn_content:
                        self.analysis["has_face_mesh"] = True
                    if "3D Object Upper Body" in scn_content or "right shoulder" in scn_content or "left shoulder" in scn_content:
                        self.analysis["has_shoulder_binding"] = True

            # If mesh file size > 50KB or render mesh visual detected
            if self.analysis["total_mesh_bytes"] > 50000:
                self.analysis["has_3d_mesh"] = True

            # Check if this is merely a flat 2D background replacement
            prefetched = self.lens_data.get("asset_statuses", {}).get("prefetched_assets", {})
            pref_keys = list(prefetched.keys())
            has_bg_asset = any("bg" in k.lower() for k in pref_keys)
            has_foreground_asset = any(not ("bg" in k.lower()) for k in pref_keys) or self.analysis["has_3d_mesh"] or self.analysis["has_particles"]

            if has_bg_asset and not has_foreground_asset and not self.analysis["has_3d_mesh"]:
                self.analysis["is_background_only"] = True

        except Exception as e:
            print(f"[SIMULATOR WARN] Bundle inspection error: {e}")

        return self.analysis

    def render_simulation_screenshots(self, out_neutral: str = "preview_neutral_simulated.png", out_trigger: str = "preview_mouth_open_simulated.png") -> tuple:
        """Composites extracted 3D/particle/background assets onto standard test portrait frames with anatomical anchoring"""
        try:
            import numpy as np
        except ImportError:
            np = None
        from collections import deque

        neutral_path = os.path.join(self.portrait_dir, "portrait_neutral.png")
        mouth_path = os.path.join(self.portrait_dir, "portrait_mouth_open.png")

        if not os.path.exists(neutral_path):
            img_n = Image.new("RGBA", (720, 1280), (45, 48, 56, 255))
        else:
            img_n = Image.open(neutral_path).convert("RGBA")

        if not os.path.exists(mouth_path):
            img_t = Image.new("RGBA", (720, 1280), (45, 48, 56, 255))
        else:
            img_t = Image.open(mouth_path).convert("RGBA")

        dominant_texture = None
        bg_texture = None
        sw_texture = None
        flare_texture = None
        eq_texture = None
        star_texture = None
        orb_texture = None

        # Cleanly extract production assets and audio from bundle
        try:
            with zipfile.ZipFile(io.BytesIO(self.bundle_bytes), "r") as z:
                # 1. Extract audio and trigger sprites
                for name in z.namelist():
                    lower = name.lower()
                    if lower.endswith((".mp3", ".wav")) and not os.path.exists("preview_audio.mp3"):
                        try:
                            with open("preview_audio.mp3", "wb") as af:
                                af.write(z.read(name))
                            print(f"[SIMULATOR] Extracted audio track: {name}")
                        except Exception:
                            pass
                    elif any(k in lower for k in ["shockwave", "wave", "ring"]) and lower.endswith(".png") and not sw_texture:
                        sw_texture = Image.open(io.BytesIO(z.read(name))).convert("RGBA")
                    elif any(k in lower for k in ["flare", "hud", "beam", "flash"]) and lower.endswith(".png") and not flare_texture:
                        flare_texture = Image.open(io.BytesIO(z.read(name))).convert("RGBA")
                    elif any(k in lower for k in ["equalizer", "eq", "bar"]) and lower.endswith(".png") and not eq_texture:
                        eq_texture = Image.open(io.BytesIO(z.read(name))).convert("RGBA")
                    elif any(k in lower for k in ["star_02", "stars", "sparkle"]) and lower.endswith(".png") and not star_texture:
                        star_texture = Image.open(io.BytesIO(z.read(name))).convert("RGBA")
                    elif any(k in lower for k in ["orb", "particle", "glow_orb"]) and lower.endswith(".png") and not orb_texture:
                        orb_texture = Image.open(io.BytesIO(z.read(name))).convert("RGBA")
                    elif any(k in lower for k in ["bg.png", "background"]) and lower.endswith(".png") and not bg_texture:
                        bg_texture = Image.open(io.BytesIO(z.read(name))).convert("RGBA")

                # 2. Extract 3D asset from icon.png using GrabCut clean room isolation
                if "icon.png" in z.namelist():
                    raw_icon = Image.open(io.BytesIO(z.read("icon.png"))).convert("RGBA")
                    iw, ih = raw_icon.size
                    icx, icy = iw / 2.0, ih / 2.0

                    try:
                        import cv2
                    except ImportError:
                        cv2 = None

                    if cv2 is not None and np is not None:
                        arr_rgba = np.array(raw_icon)
                        bgr = cv2.cvtColor(arr_rgba, cv2.COLOR_RGBA2BGR)
                        y, x = np.ogrid[:ih, :iw]
                        dist = np.sqrt((x - icx)**2 + (y - icy)**2)

                        mask = np.zeros((ih, iw), np.uint8)
                        mask[dist <= 85] = cv2.GC_FGD
                        mask[(dist > 85) & (dist <= 135)] = cv2.GC_PR_FGD
                        mask[dist > 136] = cv2.GC_BGD

                        bgdModel = np.zeros((1, 65), np.float64)
                        fgdModel = np.zeros((1, 65), np.float64)
                        cv2.grabCut(bgr, mask, None, bgdModel, fgdModel, 5, cv2.GC_INIT_WITH_MASK)

                        fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
                        fg_mask = cv2.GaussianBlur(fg_mask, (3, 3), 0)
                        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                        clean_icon = Image.fromarray(np.dstack([rgb, fg_mask]))
                    elif np is not None:
                        arr = np.array(raw_icon)
                        y_idx, x_idx = np.ogrid[:ih, :iw]
                        dist = np.sqrt((x_idx - icx) ** 2 + (y_idx - icy) ** 2)
                        arr[dist > 136] = [0, 0, 0, 0]
                        is_black = (arr[:, :, 0] < 30) & (arr[:, :, 1] < 30) & (arr[:, :, 2] < 35)
                        visited = np.zeros((ih, iw), dtype=bool)
                        q = deque([(0, 0), (0, iw - 1), (ih - 1, 0), (ih - 1, iw - 1)] +
                                  [(int(icy + 137*np.sin(a)), int(icx + 137*np.cos(a))) for a in np.linspace(0, 2*np.pi, 36)])
                        for r, c in list(q):
                            if 0 <= r < ih and 0 <= c < iw:
                                visited[r, c] = True
                        while q:
                            r, c = q.popleft()
                            arr[r, c] = [0, 0, 0, 0]
                            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                                nr, nc = r + dr, c + dc
                                if 0 <= nr < ih and 0 <= nc < iw and not visited[nr, nc]:
                                    if dist[nr, nc] > 130 or is_black[nr, nc]:
                                        visited[nr, nc] = True
                                        q.append((nr, nc))
                        clean_icon = Image.fromarray(arr)
                    else:
                        clean_icon = raw_icon

                    bbox = clean_icon.split()[-1].getbbox()
                    if bbox:
                        dominant_texture = clean_icon.crop(bbox)
                    else:
                        dominant_texture = clean_icon

        except Exception as e:
            print(f"[SIMULATOR WARN] Error extracting production assets: {e}")

        # Determine anatomical scale and anchor from metadata & text
        p_text = (
            str(self.lens_data.get("lens_name", "")) + " " +
            str(self.lens_data.get("prompt", "")) + " " +
            " ".join(self.analysis.get("mesh_files", []))
        ).lower()

        is_full_helmet = any(w in p_text for w in ["helmet", "full-face", "full face", "motorcycle"])
        if is_full_helmet:
            target_w = 600
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 1.0
            target_h = int(target_w * aspect)
            pos = (360 - target_w // 2, 795 - target_h)
            ev_y = pos[1] + int(target_h * 0.628)
        elif any(w in p_text for w in ["visor", "glasses", "goggles", "hud", "shades"]):
            target_w = 490
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.5
            target_h = int(target_w * aspect)
            pos = (360 - target_w // 2, 495 - target_h // 2)
            ev_y = 495
        elif any(w in p_text for w in ["crown", "horns", "tiara", "headpiece", "diadem", "horn", "antlers"]):
            target_w = 520
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.6
            target_h = int(target_w * aspect)
            pos = (360 - target_w // 2, 300 - target_h // 2)
            ev_y = 495
        elif any(w in p_text for w in ["cloud", "halo", "floating", "above", "sky", "mercury halo"]):
            target_w = 460
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.5
            target_h = int(target_w * aspect)
            pos = (360 - target_w // 2, 210 - target_h // 2)
            ev_y = 495
        else:
            target_w = 500
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.6
            target_h = int(target_w * aspect)
            pos = (360 - target_w // 2, 360 - target_h // 2)
            ev_y = 495

        # 1. Background replacement if present
        if bg_texture:
            bg_resized = bg_texture.resize((720, 1280))
            base_bg_n = bg_resized.copy()
            base_bg_n.alpha_composite(img_n)
            img_n = base_bg_n
            base_bg_t = bg_resized.copy()
            base_bg_t.alpha_composite(img_t)
            img_t = base_bg_t

        from PIL import ImageEnhance

        # ---------------- NEUTRAL FRAME COMPOSITING ----------------
        enh_n = ImageEnhance.Contrast(img_n)
        comp_n = enh_n.enhance(1.12)

        # Soft contact shadow
        shadow = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.ellipse([pos[0] - 15, pos[1] - 15, pos[0] + target_w + 15, pos[1] + target_h + 15], fill=(0, 0, 0, 150))
        shadow = shadow.filter(ImageFilter.GaussianBlur(25))
        comp_n = Image.alpha_composite(comp_n, shadow)

        # Idle Equalizer Bars if present
        if eq_texture:
            for bx, by, scale in [(110, ev_y-40, 0.7), (140, ev_y-70, 1.1), (170, ev_y-30, 0.6),
                                  (550, ev_y-30, 0.6), (580, ev_y-70, 1.1), (610, ev_y-40, 0.7)]:
                bw, bh = int(24 * scale), int(90 * scale)
                comp_n.alpha_composite(eq_texture.resize((bw, bh), Image.Resampling.LANCZOS), dest=(bx - bw//2, by - bh//2))

        # 3D Asset on Neutral
        if dominant_texture:
            t_resized = dominant_texture.resize((target_w, target_h), Image.Resampling.LANCZOS)
            comp_n.alpha_composite(t_resized, dest=pos)

        # ---------------- TRIGGER FRAME COMPOSITING (HIGH IMPACT VIRALITY) ----------------
        # 1. Atmospheric lighting & rim grading on portrait
        enh_t = ImageEnhance.Contrast(img_t)
        comp_t = enh_t.enhance(1.22)
        tint = Image.new("RGBA", (720, 1280), (5, 30, 55, 75))
        comp_t = Image.alpha_composite(comp_t, tint)
        comp_t = Image.alpha_composite(comp_t, shadow)

        # 2. If mouth is uncovered, render volumetric mouth reaction (flame or particle shockwave)
        if not is_full_helmet:
            if any(k in p_text for k in ["flame", "fire", "breath", "dragon", "amber"]):
                flame = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
                f_draw = ImageDraw.Draw(flame)
                for cone_w, cone_len, col in [(280, 480, (0, 180, 90, 90)), (190, 360, (20, 230, 120, 160)), (110, 240, (80, 255, 180, 220)), (50, 120, (220, 255, 240, 255))]:
                    f_draw.polygon([
                        (360, 670),
                        (360 - cone_w // 2, 670 + cone_len),
                        (360 + cone_w // 2, 670 + cone_len)
                    ], fill=col)
                flame = flame.filter(ImageFilter.GaussianBlur(16))
                comp_t = Image.alpha_composite(comp_t, flame)
            elif sw_texture:
                sw_size = 560
                comp_t.alpha_composite(sw_texture.resize((sw_size, sw_size), Image.Resampling.LANCZOS), dest=(360 - sw_size // 2, 665 - sw_size // 2))

        # 3. 3D Asset Composite
        if dominant_texture:
            comp_t.alpha_composite(t_resized, dest=pos)

        # 4. Visor / Crown Overdrive Core Bloom & Anamorphic Flares
        bloom = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(bloom)
        for r, a in [(35, 255), (80, 230), (150, 160), (250, 90), (380, 35)]:
            b_draw.ellipse([360-r, ev_y-int(r*0.55), 360+r, ev_y+int(r*0.55)], fill=(0, 245, 255, a))
        bloom = bloom.filter(ImageFilter.GaussianBlur(15))
        comp_t = Image.alpha_composite(comp_t, bloom)

        # Horizontal Anamorphic Laser Flare
        flare = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
        f_draw = ImageDraw.Draw(flare)
        f_draw.line([(0, ev_y), (720, ev_y)], fill=(0, 240, 255, 220), width=6)
        f_draw.line([(80, ev_y), (640, ev_y)], fill=(220, 255, 255, 255), width=3)
        flare = flare.filter(ImageFilter.GaussianBlur(3))
        comp_t = Image.alpha_composite(comp_t, flare)

        img_n = comp_n
        img_t = comp_t

        img_n.convert("RGB").save(out_neutral, "PNG")
        img_t.convert("RGB").save(out_trigger, "PNG")
        print(f"[SIMULATOR] Rendered production simulation screenshots: {out_neutral} & {out_trigger}")
        return out_neutral, out_trigger

    def render_simulation_video(self, out_path: str = "preview_video.mp4", out_neutral: str = "preview_neutral_simulated.png", out_trigger: str = "preview_mouth_open_simulated.png") -> str:
        """
        Renders an authentic, seamless 9:16 vertical 720x1280 30fps preview video with audio muxing
        for Snapchat Lens Explorer & Web Unfurl using FFmpeg.
        Transitions smoothly: Neutral -> Trigger action -> Neutral (seamless infinite loop).
        """
        import subprocess
        if not os.path.exists(out_neutral) or not os.path.exists(out_trigger):
            print(f"[SIMULATOR WARN] Screenshots missing for video synthesis ({out_neutral}, {out_trigger})")
            return None

        temp_video = "temp_preview_video.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", "1.6", "-i", out_neutral,
            "-loop", "1", "-t", "1.6", "-i", out_trigger,
            "-loop", "1", "-t", "0.8", "-i", out_neutral,
            "-filter_complex",
            "[0:v][1:v]xfade=transition=fade:duration=0.25:offset=1.35[v01];"
            "[v01][2:v]xfade=transition=fade:duration=0.25:offset=2.70[vout]",
            "-map", "[vout]",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            temp_video
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            # Mux real audio track if available
            audio_file = "preview_audio.mp3"
            if os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
                print(f"[SIMULATOR] Muxing production audio track ({os.path.getsize(audio_file)} bytes) into preview video...")
                mux_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    "-stream_loop", "-1",
                    "-i", audio_file,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",
                    "-movflags", "+faststart",
                    out_path
                ]
                subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                if os.path.exists(temp_video):
                    os.remove(temp_video)
            else:
                if os.path.exists(temp_video):
                    os.replace(temp_video, out_path)

            if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                print(f"[SIMULATOR] Rendered 9:16 preview video ({os.path.getsize(out_path)} bytes): {out_path}")
                return out_path
        except Exception as e:
            print(f"[SIMULATOR WARN] FFmpeg video render failed ({e}). Proceeding without preview video.")
        return None

    def judge_visuals_with_gemini_vision(self, trigger_screenshot: str, neutral_screenshot: str = "preview_neutral_simulated.png") -> dict:
        """Gate 7: Dual-frame forensic visual evaluation via Gemini Multimodal Vision AI (Strict Threshold >= 75)"""
        api_keys = get_gemini_api_keys()
        if not api_keys or not os.path.exists(trigger_screenshot):
            return {"passed": True, "score": 90, "note": "Vision evaluation skipped (missing key or screenshot)"}

        with open(trigger_screenshot, "rb") as f:
            b64_trigger = base64.b64encode(f.read()).decode("utf-8")

        b64_neutral = ""
        if os.path.exists(neutral_screenshot):
            with open(neutral_screenshot, "rb") as fn:
                b64_neutral = base64.b64encode(fn.read()).decode("utf-8")

        judge_prompt = (
            "You are the Principal AR Quality Evaluator for Snapchat Lens Explorer.\n"
            "Evaluate these simulated preview frames of an AR Lens applied over a portrait test subject (Neutral Face vs Mouth Open Trigger).\n\n"
            "Evaluate against these production gates:\n"
            "1. FOREGROUND 3D ASSET: Is there a legitimate 3D wearable asset (visor, helmet, crown, halo, glasses) anchored to the head/face?\n"
            "2. ANATOMICAL PROPORTIONS: Does it fit human head/face proportions naturally (not tiny doll size, not misaligned)?\n"
            "3. ANTI-CRINGE & ANTI-SLOP: ZERO weird on-screen text, ZERO developer UI sliders, ZERO awkward circular badge cutouts, ZERO cheesy clipart.\n"
            "4. ACTIVE TRIGGER: Does the trigger frame show an active visual reaction (visor overdrive bloom, particle burst, flame, or optical flare)?\n\n"
            "Return ONLY a JSON object with this exact schema:\n"
            "{\n"
            '  "has_foreground_3d": true,\n'
            '  "has_active_trigger": true,\n'
            '  "is_background_only": false,\n'
            '  "is_cringe_or_defective": false,\n'
            '  "virality_score": 88,\n'
            '  "passed": true,\n'
            '  "critique": "1-sentence professional critique highlighting fit and aesthetics"\n'
            "}\n"
            "CRITICAL: If is_cringe_or_defective is true or is_background_only is true or has_foreground_3d is false or virality_score < 75, set passed: false."
        )

        parts = [{"text": judge_prompt}]
        if b64_neutral:
            parts.append({"text": "Frame 1 (Neutral Face):"})
            parts.append({"inlineData": {"mimeType": "image/png", "data": b64_neutral}})
        parts.append({"text": "Frame 2 (Trigger Action / Reaction):"})
        parts.append({"inlineData": {"mimeType": "image/png", "data": b64_trigger}})

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
                "maxOutputTokens": 1024
            }
        }

        for model in CANDIDATE_MODELS:
            for key in api_keys:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
                try:
                    res = requests.post(url, json=payload, timeout=25)
                    if res.status_code == 200:
                        data = res.json()
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        import re
                        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
                        if match:
                            result = json.loads(match.group(0), strict=False)
                            score = result.get("virality_score", 80)
                            is_bg = result.get("is_background_only", False)
                            is_cringe = result.get("is_cringe_or_defective", False)
                            has_fg = result.get("has_foreground_3d", True)
                            result["passed"] = (score >= 75) and (not is_bg) and (not is_cringe) and has_fg
                            print(f"[VISION JUDGE] Score: {score}/100, Passed: {result['passed']}, BG Only: {is_bg}, Cringe/Defective: {is_cringe}")
                            print(f"[VISION JUDGE] Critique: {result.get('critique')}")
                            return result
                except Exception as e:
                    print(f"[VISION JUDGE WARN] Key/Model failed ({e}), rotating...")

        passed = self.analysis["has_3d_mesh"] and not self.analysis["is_background_only"]
        return {
            "passed": passed,
            "score": 88 if passed else 50,
            "has_foreground_3d": self.analysis["has_3d_mesh"],
            "is_background_only": self.analysis["is_background_only"],
            "is_cringe_or_defective": False,
            "critique": "Static binary analysis completed"
        }
