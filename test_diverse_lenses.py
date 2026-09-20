#!/usr/bin/env python3
"""
Diverse Lens Multi-Suite Test Runner.
Tests distinct archetypes across Account 1 (Mythic) and Account 2 (Cyber).
Validates preview images, preview videos, split comparisons, and Gate 7 video audits.
"""
import os
import io
import json
import zipfile
import subprocess
from lens_simulator import LensSimulator
from lens_verifier import LensVerifier

TEST_LENSES = [
    {
        "id": "acc1_ghibli",
        "account_id": "1",
        "lens_name": "Ghibli Watercolor Cloud Crown",
        "prompt": "Hand-painted Ghibli watercolor cumulus cloud crown resting above hairline with floating soot spirit dust and celestial spirit serpent coils. Soft cel-shaded gouache textures with warm 2800K sunlight ray-traced highlights. Opening mouth erupts swirling sakura petal cyclone; smiling spawns cheerful soot sprites around temples; head tilt shifts floating spirit dust. Pure 3D PBR fantasy, zero strobing, zero UI.",
        "archetype": "cloud",
        "tags": ["ghibli", "watercolor", "anime", "clouds", "spirit"]
    },
    {
        "id": "acc2_vhs_camcorder",
        "account_id": "2",
        "lens_name": "90s Cyber Camcorder Visor",
        "prompt": "Retro-futuristic 90s cyber camcorder visor frame contoured across brow and temples with holographic rec timestamp and magnetic phosphor glass. PBR brushed titanium, cathode-ray scanline reflections. Opening mouth discharges magnetic tape-rip glitch shockwave and RGB chromatic particle split; smiling pulses neon REC battery flare; head tilt shifts scanlines. Zero strobing, pure 3D AR craft, zero UI.",
        "archetype": "visor",
        "tags": ["camcorder", "vhs", "glitch", "cyberpunk", "visor"]
    },
    {
        "id": "acc1_crying_meme",
        "account_id": "1",
        "lens_name": "Fluffy Crying Stormcloud",
        "prompt": "Floating expressive cartoon crying stormcloud anchored above user head with shimmering rain and soft volume lighting. Opening mouth triggers dramatic geyser of liquid mercury teardrops and bouncing 24k gold coins; smiling parts the cloud with bright rainbow sunburst rays; eyebrow raise sends comic thunderbolt flashes through cloud rim. Pure 3D mesh, zero text.",
        "archetype": "cloud",
        "tags": ["meme", "crying", "funny", "cloud", "cartoon"]
    },
    {
        "id": "acc2_haute_luxe",
        "account_id": "2",
        "lens_name": "Haute Baroque Gold & Pearls",
        "prompt": "Sculpted 24k gold leaf baroque crown fitted strictly to hairline and temples with pale champagne crystal halo and luminous freshwater pearls. Warm Kodak Portra 35mm film halation with Golden Glow and grain. Anisotropic PBR reflections, ray-traced shadows. Opening mouth parts delicate golden veil; smiling unleashes rich golden sparkle dust cascading across cheekbones. Photosensitive safe, zero strobing.",
        "archetype": "tiara",
        "tags": ["film", "35mm", "crown", "gold", "luxury", "couture"]
    },
    {
        "id": "acc1_liquid_chrome",
        "account_id": "1",
        "lens_name": "Y3K Liquid Mercury Halo",
        "prompt": "Weightless Y3K zero-G liquid mercury halo crown morphing above head with sculpted chrome cheekbone armor. Anisotropic mirror PBR reflections with fluid surface tension and ray-traced contact shadows. Opening mouth erupts orbiting refractive liquid chrome spheres into expanding toroidal shockwave; smiling triggers fluid ripple normal-map distortion across armor; head tilt shifts mercury droplets. Zero strobing, zero UI.",
        "archetype": "halo",
        "tags": ["y3k", "liquidmercury", "chrome", "zerog", "surreal"]
    }
]

def extract_keyframes(video_path: str, out_dir: str):
    timestamps = [1.0, 2.0, 3.0]
    for ts in timestamps:
        kf_out = os.path.join(out_dir, f"kf_{int(ts)}s.png")
        cmd = [
            "ffmpeg", "-y", "-ss", str(ts), "-i", video_path,
            "-vframes", "1", "-q:v", "2", kf_out
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def run_suite():
    base_dir = "/tmp/lens_diverse_suite"
    os.makedirs(base_dir, exist_ok=True)
    summary = []

    for l_conf in TEST_LENSES:
        lid = l_conf["id"]
        out_dir = os.path.join(base_dir, lid)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\n=======================================================")
        print(f"Testing {lid}: {l_conf['lens_name']} (Account #{l_conf['account_id']})")
        print(f"=======================================================")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("scene.scn", "Component.RenderMeshVisual Component.Head")
            z.writestr("scripts/Controller.js", "// Production safe script\nprint('Initialized');\n")
            z.writestr("meshes/hero.mesh", b"MESH_" * 1000)
        bundle_bytes = buf.getvalue()

        lens_data = {
            "account_id": l_conf["account_id"],
            "channel_id": l_conf["account_id"],
            "lens_name": l_conf["lens_name"],
            "prompt": l_conf["prompt"],
            "archetype": l_conf["archetype"],
            "tags": l_conf["tags"]
        }

        sim = LensSimulator(bundle_bytes, lens_data=lens_data, portrait_dir="assets")
        out_vid = os.path.join(out_dir, "preview_video.mp4")
        out_n = os.path.join(out_dir, "preview_neutral_simulated.png")
        out_t = os.path.join(out_dir, "preview_mouth_open_simulated.png")
        out_split = os.path.join(out_dir, "preview_split_comparison.png")
        out_icon = os.path.join(out_dir, "lens_icon.png")

        print("Rendering simulation video, split comparison, and previews...")
        sim.render_simulation_video(out_path=out_vid, out_neutral=out_n, out_trigger=out_t, account_id=l_conf["account_id"])
        sim.render_split_comparison(out_path=out_split, account_id=l_conf["account_id"])
        sim.generate_viral_lens_icon(out_path=out_icon, account_id=l_conf["account_id"])

        extract_keyframes(out_vid, out_dir)

        print("Auditing video quality and visual defect gates...")
        audit = LensSimulator.audit_preview_video(out_vid, require_audio=True)
        rms = audit.get("motion_variance", {}).get("avg_rms", 0.0)
        passed = audit.get("passed", False)
        errors = audit.get("errors", [])
        print(f"  Audit Passed: {passed} | RMS Motion: {rms:.2f} | Errors: {errors}")

        summary.append({
            "id": lid,
            "name": l_conf["lens_name"],
            "account": l_conf["account_id"],
            "passed": passed,
            "rms": rms,
            "errors": errors,
            "out_dir": out_dir
        })

    print("\n" + "=" * 65)
    print("DIVERSE SUITE SUMMARY:")
    for s in summary:
        status = "PASSED" if s["passed"] else f"FAILED ({len(s['errors'])} errors)"
        print(f"  [{status}] {s['id']}: RMS={s['rms']:.2f}")
    print("=" * 65)

if __name__ == "__main__":
    run_suite()
