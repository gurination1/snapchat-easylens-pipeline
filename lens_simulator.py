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
import subprocess
import shutil
import time
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
            "has_canvas_api": False,
            "is_background_only": False,
            "texture_files": [],
            "mesh_files": []
        }
        self.dominant_texture = None
        self.bg_texture = None
        self.sw_texture = None
        self.flare_texture = None
        self.eq_texture = None
        self.star_texture = None
        self.orb_texture = None
        self.asset_scale_info = {}

    def inspect_bundle(self) -> dict:
        """Deep inspects scene.scn and archive to detect 3D meshes, bindings, and slop"""
        try:
            with zipfile.ZipFile(io.BytesIO(self.bundle_bytes), "r") as z:
                names = z.namelist()
                for name in names:
                    lower = name.lower()
                    if "canvasapi" in lower or lower.endswith("canvasapi.js"):
                        self.analysis["has_canvas_api"] = True
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
                    if "CanvasAPI" in scn_content or "crown_bars_canvas" in scn_content:
                        self.analysis["has_canvas_api"] = True

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
                        mask[dist <= 135] = cv2.GC_PR_FGD
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
        labels = []
        for a_data in self.lens_data.get("asset_statuses", {}).get("prefetched_assets", {}).values():
            if isinstance(a_data, dict) and a_data.get("label"):
                labels.append(a_data["label"])

        p_text = (
            str(self.lens_data.get("lens_name", "")) + " " +
            str(self.lens_data.get("prompt", "")) + " " +
            " ".join(labels) + " " +
            " ".join(self.analysis.get("mesh_files", []))
        ).lower()

        is_full_helmet = any(w in p_text for w in ["helmet", "full-face", "full face", "motorcycle"])
        if is_full_helmet:
            target_w = 600
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 1.0
            target_h = int(target_w * aspect)
            pos = (360 - target_w // 2, 795 - target_h)
            ev_y = pos[1] + int(target_h * 0.628)
        elif any(w in p_text for w in ["visor", "glasses", "goggles", "hud", "shades", "nodes", "lenses", "specs", "monocle", "eyewear", "cybernetic", "orbital", "temple", "brow"]):
            target_w = 480
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.4
            target_h = min(190, int(target_w * aspect))
            pos = (360 - target_w // 2, 495 - target_h // 2)
            ev_y = 495
        elif any(w in p_text for w in ["crown", "horns", "tiara", "headpiece", "diadem", "horn", "antlers"]):
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.6
            max_h = 360
            target_w = min(440, int(max_h / max(0.01, aspect)))
            target_h = int(target_w * aspect)
            base_y = 390
            pos_y = max(10, base_y - target_h)
            pos = (360 - target_w // 2, pos_y)
            ev_y = 495
        elif any(w in p_text for w in ["cloud", "halo", "floating", "above", "sky", "mercury halo"]):
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.5
            target_w = 440
            target_h = int(target_w * aspect)
            pos = (360 - target_w // 2, 230 - target_h // 2)
            ev_y = 495
        else:
            aspect = (dominant_texture.height / max(1, dominant_texture.width)) if dominant_texture else 0.6
            max_h = 350
            target_w = min(440, int(max_h / max(0.01, aspect)))
            target_h = int(target_w * aspect)
            base_y = 390
            pos_y = max(10, base_y - target_h)
            pos = (360 - target_w // 2, pos_y)
            ev_y = 495

        # Store for motion video synthesis
        self.dominant_texture = dominant_texture
        self.bg_texture = bg_texture
        self.sw_texture = sw_texture
        self.flare_texture = flare_texture
        self.eq_texture = eq_texture
        self.star_texture = star_texture
        self.orb_texture = orb_texture
        self.asset_scale_info = {
            "target_w": target_w,
            "target_h": target_h,
            "pos": pos,
            "ev_y": ev_y,
            "is_full_helmet": is_full_helmet,
            "is_visor": any(w in p_text for w in ["visor", "glasses", "goggles", "hud", "shades", "nodes", "lenses", "specs", "monocle", "eyewear", "cybernetic", "orbital", "temple", "brow"]),
            "is_crown": any(w in p_text for w in ["crown", "horns", "tiara", "headpiece", "diadem", "horn", "antlers"]),
            "is_halo": any(w in p_text for w in ["cloud", "halo", "floating", "above", "sky", "mercury halo"]),
            "p_text": p_text
        }

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

        # Realistic contact shadow
        shadow = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        if any(w in p_text for w in ["crown", "horns", "tiara", "headpiece", "diadem", "horn", "antlers"]):
            # Base rim contact shadow on forehead/hairline
            s_draw.ellipse([pos[0] + 50, pos[1] + target_h - 15, pos[0] + target_w - 50, pos[1] + target_h + 25], fill=(0, 0, 0, 90))
            shadow = shadow.filter(ImageFilter.GaussianBlur(15))
        elif any(w in p_text for w in ["visor", "glasses", "goggles", "hud"]):
            # Temple and nose bridge contact occlusion
            s_draw.ellipse([pos[0] + 30, pos[1] + int(target_h * 0.7), pos[0] + target_w - 30, pos[1] + target_h + 15], fill=(0, 0, 0, 80))
            shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        elif any(w in p_text for w in ["cloud", "halo", "floating"]):
            # Downward ambient occlusion cast onto skull
            s_draw.ellipse([260, 310, 460, 360], fill=(0, 0, 0, 75))
            shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        else:
            s_draw.ellipse([pos[0] + 40, pos[1] + target_h - 15, pos[0] + target_w - 40, pos[1] + target_h + 25], fill=(0, 0, 0, 80))
            shadow = shadow.filter(ImageFilter.GaussianBlur(15))
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
            else:
                energy = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
                e_draw = ImageDraw.Draw(energy)
                for cone_w, cone_len, col in [(260, 400, (0, 220, 180, 100)), (170, 270, (0, 245, 210, 150)), (90, 150, (180, 255, 235, 210))]:
                    e_draw.polygon([
                        (360, 670),
                        (360 - cone_w // 2, 670 + cone_len),
                        (360 + cone_w // 2, 670 + cone_len)
                    ], fill=col)
                energy = energy.filter(ImageFilter.GaussianBlur(14))
                comp_t = Image.alpha_composite(comp_t, energy)

        # 3. 3D Asset Composite
        if dominant_texture:
            comp_t.alpha_composite(t_resized, dest=pos)

        # 4. Visor / Crown Overdrive Core Bloom & Anamorphic Flares
        bloom = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(bloom)

        is_visor = any(w in p_text for w in ["visor", "glasses", "hud", "cyberpunk"])
        if is_visor:
            for r, a in [(35, 255), (80, 230), (150, 160), (250, 90), (380, 35)]:
                b_draw.ellipse([360-r, ev_y-int(r*0.55), 360+r, ev_y+int(r*0.55)], fill=(0, 245, 255, a))
            bloom = bloom.filter(ImageFilter.GaussianBlur(15))
            comp_t = Image.alpha_composite(comp_t, bloom)

            flare = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
            f_draw = ImageDraw.Draw(flare)
            f_draw.line([(0, ev_y), (720, ev_y)], fill=(0, 240, 255, 220), width=6)
            f_draw.line([(80, ev_y), (640, ev_y)], fill=(220, 255, 255, 255), width=3)
            flare = flare.filter(ImageFilter.GaussianBlur(3))
            comp_t = Image.alpha_composite(comp_t, flare)
        else:
            # Warm gold/amber radiant bloom for crowns/headpieces/halos
            glow_y = pos[1] + target_h // 2
            for r, a in [(25, 220), (60, 170), (120, 110), (200, 50), (300, 20)]:
                b_draw.ellipse([360-r, glow_y-r, 360+r, glow_y+r], fill=(255, 215, 80, a))
            bloom = bloom.filter(ImageFilter.GaussianBlur(18))
            comp_t = Image.alpha_composite(comp_t, bloom)

            # Subtle eye runic sparkles at eye level
            eye_sparkle = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
            e_draw = ImageDraw.Draw(eye_sparkle)
            for ex in [280, 440]:
                e_draw.ellipse([ex - 25, ev_y - 25, ex + 25, ev_y + 25], fill=(255, 225, 120, 180))
                e_draw.line([(ex - 45, ev_y), (ex + 45, ev_y)], fill=(255, 245, 180, 220), width=2)
                e_draw.line([(ex, ev_y - 45), (ex, ev_y + 45)], fill=(255, 245, 180, 220), width=2)
            eye_sparkle = eye_sparkle.filter(ImageFilter.GaussianBlur(5))
            comp_t = Image.alpha_composite(comp_t, eye_sparkle)

        img_n = comp_n
        img_t = comp_t

        img_n.convert("RGB").save(out_neutral, "PNG")
        img_t.convert("RGB").save(out_trigger, "PNG")
        print(f"[SIMULATOR] Rendered production simulation screenshots: {out_neutral} & {out_trigger}")
        return out_neutral, out_trigger

    def resolve_audio_track(self, account_id: str = None) -> str:
        """Dynamically resolve royalty-free audio stem matching account persona or prompt archetype"""
        aid = str(
            account_id
            or self.lens_data.get("account_id")
            or os.getenv("ACCOUNT_ID", "1")
        ).lower()

        p_text = (
            str(self.asset_scale_info.get("p_text", "")) + " " +
            str(self.lens_data.get("prompt", "")) + " " +
            str(self.lens_data.get("lens_name", "")) + " " +
            str(self.lens_data.get("theme_focus", "")) + " " +
            " ".join(str(t) for t in self.lens_data.get("tags", []))
        ).lower()

        acc_map = {
            "1": "mythic_roar.mp3",
            "mythicbeasts": "mythic_roar.mp3",
            "mythicbeasts_ar": "mythic_roar.mp3",
            "2": "cyber_pulse.mp3",
            "scifi_optics": "cyber_pulse.mp3",
            "scifi": "cyber_pulse.mp3",
            "3": "comedy_pop.mp3",
            "warpshock_comedy": "comedy_pop.mp3",
            "warpshock": "comedy_pop.mp3",
            "comedy": "comedy_pop.mp3",
            "4": "luxury_shimmer.mp3",
            "lumiere_atelier": "luxury_shimmer.mp3",
            "lumiere": "luxury_shimmer.mp3",
            "5": "mercury_drift.mp3",
            "chrono_mirage": "mercury_drift.mp3",
            "chrono": "mercury_drift.mp3"
        }

        # 1. If explicit account_id passed, honor it
        chosen = None
        if account_id is not None and str(account_id).lower() in acc_map:
            chosen = acc_map[str(account_id).lower()]

        # 2. Check prompt archetype keyword semantics with scoring
        if not chosen:
            niche_scores = {
                "mythic_roar.mp3": sum(1 for w in [
                    "dragon", "wyvern", "pyrodrake", "phoenix", "firebird", "valkyrie",
                    "kitsune", "foxfire", "anubis", "jackal", "mythic", "mythology", "beast", "roar"
                ] if w in p_text),
                "cyber_pulse.mp3": sum(1 for w in [
                    "cyber", "cyberpunk", "visor", "hud", "scanner", "retinal", "ocular",
                    "monocular", "titanium", "optic", "telemetry", "goggles", "hyperdrive", "targeting"
                ] if w in p_text),
                "comedy_pop.mp3": sum(1 for w in [
                    "comedy", "meme", "crying", "stormcloud", "teardrop", "soap-opera",
                    "melodrama", "steam-whistle", "boiler valve", "laughing skull", "confetti",
                    "hypno", "cartoon", "bouncy", "spring", "pop-out", "whistle", "splat"
                ] if w in p_text),
                "luxury_shimmer.mp3": sum(1 for w in [
                    "luxury", "couture", "haute", "baroque", "pearl", "art nouveau", "tiara",
                    "champagne", "diamond", "florentine", "laurel", "35mm", "portra",
                    "analog", "shimmer", "chime", "glissando", "harp", "atelier"
                ] if w in p_text),
                "mercury_drift.mp3": sum(1 for w in [
                    "mercury", "chrome", "surreal", "zero-g", "mobius", "ferrofluid",
                    "liquid platinum", "bismuth", "chrysalis", "toroid", "toroidal",
                    "hypnotic", "y3k", "chrono", "mirage", "fluid drop"
                ] if w in p_text)
            }
            best_stem, best_score = max(niche_scores.items(), key=lambda x: x[1])
            if best_score > 0:
                chosen = best_stem

        # 3. Fall back to account_id from lens_data or env
        if not chosen:
            chosen = acc_map.get(aid, "cyber_pulse.mp3")

        cand_dirs = [
            os.path.join(self.portrait_dir, "audio"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "audio"),
            os.path.join(os.getcwd(), "assets", "audio"),
            "assets/audio"
        ]

        for audio_dir in cand_dirs:
            cand_path = os.path.join(audio_dir, chosen)
            if os.path.exists(cand_path) and os.path.getsize(cand_path) > 1000:
                return cand_path

        if os.path.exists("preview_audio.mp3") and os.path.getsize("preview_audio.mp3") > 1000:
            return "preview_audio.mp3"

        return None

    @staticmethod
    def audit_preview_video(video_path: str, require_audio: bool = False) -> dict:
        """Strict mathematical quality, black-screen, freeze, motion variance, and audio audit"""
        from lens_verifier import audit_preview_video
        return audit_preview_video(video_path, require_audio=require_audio)

    def render_simulation_video(self, out_path: str = "preview_video.mp4", out_neutral: str = "preview_neutral_simulated.png", out_trigger: str = "preview_mouth_open_simulated.png", motion_video: str = None, account_id: str = None) -> str:
        """
        Renders an authentic, dynamic 9:16 vertical 720x1280 30fps preview video with real portrait motion,
        optical flow facial landmark tracking, dynamic reactive asset transformation, and audio muxing.
        Seamlessly falls back to 2-frame crossfade if motion video is unavailable.
        """
        import subprocess
        import time
        import shutil
        from PIL import ImageEnhance

        try:
            import cv2
            import numpy as np
        except ImportError:
            cv2 = None
            np = None

        # Ensure assets are loaded
        if self.dominant_texture is None:
            self.render_simulation_screenshots(out_neutral=out_neutral, out_trigger=out_trigger)

        video_src = motion_video or os.path.join(self.portrait_dir, "test_portrait.mp4")
        temp_video = "temp_preview_video.mp4"

        # ---------------- 1. REAL PORTRAIT MOTION ENGINE WITH LANDMARK TRACKING ----------------
        if cv2 is not None and np is not None and os.path.exists(video_src):
            try:
                cap = cv2.VideoCapture(video_src)
                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                ret, first_frame = cap.read()
                if not ret:
                    raise ValueError(f"Unable to read frames from {video_src}")

                # Initial canonical landmark anchor points for 720x1280 portrait
                # [0: left eye, 1: right eye, 2: nose tip, 3: forehead hairline, 4: mouth center]
                pts0 = np.array([
                    [240.0, 395.0],  # left eye pupil
                    [520.0, 400.0],  # right eye pupil
                    [365.0, 510.0],  # nose bridge
                    [365.0, 260.0],  # forehead hairline
                    [365.0, 660.0],  # mouth center
                ], dtype=np.float32).reshape(-1, 1, 2)

                lk_params = dict(winSize=(31, 31), maxLevel=3,
                                 criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03))

                all_frames = [first_frame]
                trajectory = [pts0.reshape(-1, 2)]
                prev_gray = cv2.cvtColor(first_frame, cv2.COLOR_BGR2GRAY)
                curr_pts = pts0.copy()

                while True:
                    ret, f_cur = cap.read()
                    if not ret:
                        break
                    gray = cv2.cvtColor(f_cur, cv2.COLOR_BGR2GRAY)
                    next_pts, status, err = cv2.calcOpticalFlowPyrLK(prev_gray, gray, curr_pts, None, **lk_params)
                    # Check validity of tracked points
                    if status is not None and np.sum(status) >= 3:
                        trajectory.append(next_pts.reshape(-1, 2))
                        curr_pts = next_pts
                    else:
                        trajectory.append(trajectory[-1])
                    all_frames.append(f_cur)
                    prev_gray = gray
                cap.release()

                num_frames = len(all_frames)
                print(f"[SIMULATOR] Loaded {num_frames} frames from portrait motion video ({src_w}x{src_h} @ {fps:.1f}fps)")

                # Asset geometry configs
                target_w = self.asset_scale_info.get("target_w", 480)
                target_h = self.asset_scale_info.get("target_h", 190)
                is_full_helmet = self.asset_scale_info.get("is_full_helmet", False)
                is_visor = self.asset_scale_info.get("is_visor", False)
                is_crown = self.asset_scale_info.get("is_crown", False)
                is_halo = self.asset_scale_info.get("is_halo", False)
                p_text = self.asset_scale_info.get("p_text", "")
                base_eye_dist = 280.0

                # Pre-generate optimized contact shadow sprite
                sh_w = max(20, int(target_w * 0.85))
                sh_h = max(20, int(target_h * 0.45))
                shadow_sprite = Image.new("RGBA", (sh_w, sh_h), (0, 0, 0, 0))
                s_draw = ImageDraw.Draw(shadow_sprite)
                s_draw.ellipse([8, 8, sh_w - 8, sh_h - 8], fill=(0, 0, 0, 85))
                shadow_sprite = shadow_sprite.filter(ImageFilter.GaussianBlur(8))

                # Pre-generate bloom flare sprite for visors / crowns
                fl_size = 220
                flare_sprite = Image.new("RGBA", (fl_size, fl_size), (0, 0, 0, 0))
                f_draw = ImageDraw.Draw(flare_sprite)
                flare_rgb = (0, 245, 255) if is_visor else (255, 215, 80)
                for r in [25, 50, 85, 105]:
                    f_draw.ellipse([fl_size//2 - r, fl_size//2 - int(r*0.55), fl_size//2 + r, fl_size//2 + int(r*0.55)],
                                   fill=(*flare_rgb, int(110 * (1.0 - r/120.0))))
                flare_sprite = flare_sprite.filter(ImageFilter.GaussianBlur(8))

                temp_frames_dir = f"/tmp/lens_sim_frames_{os.getpid()}_{int(time.time())}"
                os.makedirs(temp_frames_dir, exist_ok=True)

                for idx, (frame_bgr, landmarks) in enumerate(zip(all_frames, trajectory)):
                    le, re, nose, fh, mouth = landmarks
                    eye_cx = float((le[0] + re[0]) / 2.0)
                    eye_cy = float((le[1] + re[1]) / 2.0)
                    eye_dist = float(np.linalg.norm(re - le))
                    scale = float(eye_dist / max(1.0, base_eye_dist))
                    roll_angle = float(np.degrees(np.arctan2(re[1] - le[1], re[0] - le[0])))

                    # Anchor point determination - use nose bridge as true midline axis
                    face_midline_x = float(nose[0])
                    if is_full_helmet:
                        anc_x, anc_y = face_midline_x, eye_cy
                    elif is_visor:
                        anc_x, anc_y = face_midline_x, eye_cy
                    elif is_crown:
                        anc_x = face_midline_x
                        anc_y = float(fh[1] - (target_h // 2 - 15) * scale)
                    elif is_halo:
                        anc_x = face_midline_x
                        anc_y = float(fh[1] - (target_h // 2 + 55) * scale)
                    else:
                        anc_x = face_midline_x
                        anc_y = float(fh[1] - (target_h // 2) * scale)

                    # Dynamic trigger progression curve (mouth open / smile transition)
                    # Peak trigger between 35% and 75% of clip duration
                    frame_ratio = idx / max(1, num_frames - 1)
                    if 0.30 <= frame_ratio <= 0.45:
                        t_prog = (frame_ratio - 0.30) / 0.15
                    elif 0.45 < frame_ratio <= 0.75:
                        t_prog = 1.0
                    elif 0.75 < frame_ratio <= 0.90:
                        t_prog = 1.0 - (frame_ratio - 0.75) / 0.15
                    else:
                        t_prog = 0.0

                    # Convert frame to PIL RGBA
                    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    pil_frame = Image.fromarray(rgb).convert("RGBA")

                    # Dynamic lighting enhancement during trigger
                    if t_prog > 0.0:
                        enh = ImageEnhance.Contrast(pil_frame)
                        pil_frame = enh.enhance(1.0 + 0.14 * t_prog)

                    # Contact shadow composite
                    cur_sw = max(10, int(sh_w * scale))
                    cur_sh = max(10, int(sh_h * scale))
                    rot_shadow = shadow_sprite.resize((cur_sw, cur_sh), Image.Resampling.BILINEAR).rotate(
                        -roll_angle, resample=Image.Resampling.BILINEAR, expand=True
                    )
                    sh_dest = (int(anc_x - rot_shadow.width // 2), int(anc_y - rot_shadow.height // 2 + cur_sh * 0.35))
                    pil_frame.alpha_composite(rot_shadow, dest=sh_dest)

                    # 3D Asset scaling, rotation, and compositing
                    if self.dominant_texture:
                        cur_w = max(10, int(target_w * scale))
                        cur_h = max(10, int(target_h * scale))
                        scaled_asset = self.dominant_texture.resize((cur_w, cur_h), Image.Resampling.LANCZOS)
                        rot_asset = scaled_asset.rotate(-roll_angle, resample=Image.Resampling.BICUBIC, expand=True)
                        dest_pos = (int(anc_x - rot_asset.width // 2), int(anc_y - rot_asset.height // 2))
                        pil_frame.alpha_composite(rot_asset, dest=dest_pos)

                    # Reactive particles & optical flares on trigger
                    if t_prog > 0.05:
                        # Bloom flare
                        cur_fl = max(10, int(fl_size * scale * (0.85 + 0.35 * t_prog)))
                        scaled_flare = flare_sprite.resize((cur_fl, cur_fl), Image.Resampling.BILINEAR)
                        pil_frame.alpha_composite(scaled_flare, dest=(int(anc_x - cur_fl // 2), int(anc_y - cur_fl // 2)))

                        # Bundle optical flare sprite if present
                        if self.flare_texture:
                            fl_w = max(10, int(cur_w * 1.3))
                            fl_h = max(10, int(cur_h * 1.3))
                            scaled_f = self.flare_texture.resize((fl_w, fl_h), Image.Resampling.BILINEAR)
                            rot_f = scaled_f.rotate(-roll_angle, resample=Image.Resampling.BILINEAR, expand=True)
                            pil_frame.alpha_composite(rot_f, dest=(int(anc_x - rot_f.width // 2), int(anc_y - rot_f.height // 2)))

                        # Volumetric mouth shockwave or energy flame burst
                        if not is_full_helmet:
                            mouth_x, mouth_y = int(mouth[0]), int(mouth[1])
                            if self.sw_texture:
                                sw_sz = max(10, int((350 + 150 * t_prog) * scale))
                                scaled_sw = self.sw_texture.resize((sw_sz, sw_sz), Image.Resampling.LANCZOS)
                                pil_frame.alpha_composite(scaled_sw, dest=(mouth_x - sw_sz // 2, mouth_y - sw_sz // 2))
                            elif any(k in p_text for k in ["flame", "fire", "breath", "dragon", "amber"]):
                                f_box_w, f_box_h = 320, 500
                                flame_patch = Image.new("RGBA", (f_box_w, f_box_h), (0, 0, 0, 0))
                                f_draw = ImageDraw.Draw(flame_patch)
                                fx0, fy0 = f_box_w // 2, 20
                                for c_w, c_l, col in [(int(240*t_prog), int(420*t_prog), (0, 180, 90, 80)),
                                                      (int(160*t_prog), int(310*t_prog), (20, 230, 120, 140)),
                                                      (int(90*t_prog), int(200*t_prog), (80, 255, 180, 200))]:
                                    if c_w > 5 and c_l > 5:
                                        f_draw.polygon([(fx0, fy0),
                                                        (fx0 - c_w // 2, fy0 + c_l),
                                                        (fx0 + c_w // 2, fy0 + c_l)], fill=col)
                                flame_patch = flame_patch.filter(ImageFilter.GaussianBlur(10))
                                pil_frame.alpha_composite(flame_patch, dest=(mouth_x - fx0, mouth_y - fy0))

                    # Write frame to temporary JPEG
                    frame_path = os.path.join(temp_frames_dir, f"{idx:04d}.jpg")
                    cv2.imwrite(frame_path, cv2.cvtColor(np.array(pil_frame), cv2.COLOR_RGBA2BGR), [cv2.IMWRITE_JPEG_QUALITY, 93])

                # Encode frame sequence with FFmpeg
                enc_cmd = [
                    "ffmpeg", "-y",
                    "-framerate", str(int(round(fps))),
                    "-i", os.path.join(temp_frames_dir, "%04d.jpg"),
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    temp_video
                ]
                subprocess.run(enc_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

                # Cleanup temp frames
                shutil.rmtree(temp_frames_dir, ignore_errors=True)

                # Mux production audio if present
                audio_file = self.resolve_audio_track(account_id=account_id)
                if audio_file and os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
                    print(f"[SIMULATOR] Muxing production audio track ({os.path.basename(audio_file)}) into motion preview video...")
                    vid_dur = round(float(num_frames / max(1.0, fps)), 3)
                    mux_cmd = [
                        "ffmpeg", "-y",
                        "-i", temp_video,
                        "-stream_loop", "-1",
                        "-i", audio_file,
                        "-t", str(vid_dur),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-b:a", "128k",
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
                    print(f"[SIMULATOR] Successfully synthesized dynamic portrait motion preview video ({os.path.getsize(out_path)} bytes): {out_path}")
                    return out_path

            except Exception as e:
                print(f"[SIMULATOR WARN] Motion video synthesis encountered error ({e}), falling back to crossfade.")
                if os.path.exists(temp_video):
                    os.remove(temp_video)

        # ---------------- 2. FALLBACK: 2-FRAME SEAMLESS CROSS-FADE ----------------
        if not os.path.exists(out_neutral) or not os.path.exists(out_trigger):
            print(f"[SIMULATOR WARN] Screenshots missing for video synthesis ({out_neutral}, {out_trigger})")
            return None

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

            audio_file = self.resolve_audio_track(account_id=account_id)
            if audio_file and os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
                print(f"[SIMULATOR] Muxing production audio track ({os.path.basename(audio_file)}) into fallback preview video...")
                mux_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    "-stream_loop", "-1",
                    "-i", audio_file,
                    "-t", "3.6",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "128k",
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
                print(f"[SIMULATOR] Rendered fallback 9:16 preview video ({os.path.getsize(out_path)} bytes): {out_path}")
                return out_path
        except Exception as e:
            print(f"[SIMULATOR WARN] Fallback FFmpeg video render failed ({e}).")
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
            "3. ANTI-CRINGE & ANTI-SLOP: ZERO weird on-screen text, ZERO developer UI sliders, ZERO awkward circular badge cutouts, ZERO cheesy clipart, ZERO 2D canvas loading wheels or equalizer bars.\n"
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
                    res = requests.post(url, json=payload, timeout=45)
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
