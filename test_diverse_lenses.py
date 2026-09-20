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
        "id": "acc1_valkyrie",
        "account_id": "1",
        "lens_name": "Valkyrie Frost Circlet",
        "prompt": "Ethereal valkyrie frost circlet with cold blue crystal gems, silver wings, and soft shimmering rim glow",
        "archetype": "circlet",
        "tags": ["mythic", "valkyrie", "circlet", "fantasy", "crystals"]
    },
    {
        "id": "acc1_phoenix",
        "account_id": "1",
        "lens_name": "Phoenix Flame Diadem",
        "prompt": "Ancient phoenix flame diadem with 24k gold filigree spires, faceted rubies, and ambient ember aura",
        "archetype": "diadem",
        "tags": ["mythic", "phoenix", "gold", "diadem", "fire"]
    },
    {
        "id": "acc2_chrono_visor",
        "account_id": "2",
        "lens_name": "Chrono HUD Visor",
        "prompt": "Cyberpunk titanium ocular visor with holographic targeting reticle, telemetry readout, and neon cyan glass",
        "archetype": "visor",
        "tags": ["cyber", "visor", "hud", "sci-fi", "cyan"]
    },
    {
        "id": "acc2_speed_goggles",
        "account_id": "2",
        "lens_name": "Hyperdrive Speed Goggles",
        "prompt": "High-octane neon amber racing spectacles with asymmetric holographic lenses, HUD telemetry, and carbon fiber temples",
        "archetype": "goggles",
        "tags": ["cyber", "goggles", "speed", "hud", "amber"]
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
