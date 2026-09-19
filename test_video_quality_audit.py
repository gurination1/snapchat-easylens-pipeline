#!/usr/bin/env python3
"""
Test Suite: Video Quality & Motion Freeze Inspector for Snapchat Bolt CDN
Tests audit_preview_video and Gate 7 integration across positive & negative invariants.
"""

import os
import sys
import json
import io
import zipfile
import subprocess
import numpy as np
import cv2

from lens_verifier import LensVerifier, audit_preview_video
from lens_simulator import LensSimulator


def test_audit_test_portrait():
    print("=== TEST 1: Audit assets/test_portrait.mp4 ===")
    test_portrait_path = "assets/test_portrait.mp4"
    assert os.path.exists(test_portrait_path), f"Missing {test_portrait_path}"

    res = audit_preview_video(test_portrait_path)
    print(f"Result for {test_portrait_path}:")
    print(f"  Passed: {res['passed']}")
    print(f"  Size: {res['file_size_bytes']} bytes (passed={res['file_size_passed']})")
    print(f"  Resolution: {res['resolution']} (passed={res['resolution_passed']})")
    print(f"  Black detect: {res['black_detect']}")
    print(f"  Freeze detect: {res['freeze_detect']}")
    print(f"  Motion RMS: {res['motion_variance']['avg_rms']:.4f} (passed={res['motion_variance']['passed']})")
    print(f"  Audio: {res['audio']}")
    print(f"  Errors: {res['errors']}")

    assert res["passed"] is True, f"test_portrait.mp4 must pass all video quality checks: {res['errors']}"
    assert res["file_size_passed"] is True
    assert res["resolution_passed"] is True
    assert res["resolution"] in ([720, 1280], [1080, 1920])
    assert res["black_detect"]["passed"] is True
    assert res["freeze_detect"]["passed"] is True
    assert res["motion_variance"]["passed"] is True
    assert res["motion_variance"]["avg_rms"] > 0.8
    assert res["audio"]["passed"] is True
    print(">>> TEST 1 PASSED: assets/test_portrait.mp4 strictly approved!\n")


def test_audit_newly_generated_preview():
    print("=== TEST 2: Generate New preview_video.mp4 & Audit ===")
    out_video = "preview_video.mp4"
    if os.path.exists(out_video):
        os.remove(out_video)

    # Build synthetic bundle with 3D mesh
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("scene.scn", "Component.RenderMeshVisual Component.Head Component.ParticleSystem")
        z.writestr("visor.mesh", b"MESH" * 20000)

    sim = LensSimulator(
        bundle_bytes=buf.getvalue(),
        lens_data={"lens_name": "Titanium Cyber Visor", "account_id": "2"},
        portrait_dir="assets"
    )
    sim.inspect_bundle()
    out_n, out_t = sim.render_simulation_screenshots("test_n.png", "test_t.png")
    generated = sim.render_simulation_video(out_path=out_video, out_neutral=out_n, out_trigger=out_t, account_id="2")

    assert generated == out_video, "render_simulation_video must return output video path"
    assert os.path.exists(out_video), "preview_video.mp4 must exist"

    res = audit_preview_video(out_video)
    print(f"Result for newly generated {out_video}:")
    print(f"  Passed: {res['passed']}")
    print(f"  Size: {res['file_size_bytes']} bytes (passed={res['file_size_passed']})")
    print(f"  Resolution: {res['resolution']} (passed={res['resolution_passed']})")
    print(f"  Black detect: {res['black_detect']}")
    print(f"  Freeze detect: {res['freeze_detect']}")
    print(f"  Motion RMS: {res['motion_variance']['avg_rms']:.4f} (passed={res['motion_variance']['passed']})")
    print(f"  Audio: {res['audio']}")
    print(f"  Errors: {res['errors']}")

    assert res["passed"] is True, f"Newly generated preview_video.mp4 must pass: {res['errors']}"
    assert res["file_size_passed"] is True
    assert res["resolution_passed"] is True
    assert res["black_detect"]["passed"] is True
    assert res["freeze_detect"]["passed"] is True
    assert res["motion_variance"]["passed"] is True
    assert res["motion_variance"]["avg_rms"] > 0.8
    assert res["audio"]["passed"] is True
    if res["audio"]["has_audio"]:
        assert res["audio"]["codec"] in ["aac", "mp3", "opus"]
        assert res["audio"]["sync_passed"] is True
    print(">>> TEST 2 PASSED: newly generated preview_video.mp4 strictly approved!\n")


def test_rejection_invariants():
    print("=== TEST 3: Negative Invariant Rejections ===")

    # 1. Non-existent file
    r_none = audit_preview_video("non_existent_file.mp4")
    assert r_none["passed"] is False
    assert any("does not exist" in e for e in r_none["errors"])
    print("  ✓ Non-existent file correctly rejected")

    # 2. File size < 50KB
    small_file = "test_too_small.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=10",
        "-t", "0.1", "-c:v", "libx264", "-crf", "50", "-pix_fmt", "yuv420p", small_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    r_small = audit_preview_video(small_file)
    os.remove(small_file)
    assert r_small["passed"] is False
    assert any("<= 50KB" in e for e in r_small["errors"])
    print("  ✓ Undersized video (<50KB) correctly rejected")

    # 3. Wrong resolution (e.g. 640x360 landscape)
    wrong_res_file = "test_wrong_res.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30",
        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", wrong_res_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    r_res = audit_preview_video(wrong_res_file)
    os.remove(wrong_res_file)
    assert r_res["passed"] is False
    assert any("Resolution" in e for e in r_res["errors"])
    print("  ✓ Invalid resolution (640x360) correctly rejected")

    # 4. Black frames detection (blackdetect)
    black_file = "test_black_frames.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=720x1280:r=30",
        "-t", "1.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", black_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    r_black = audit_preview_video(black_file)
    os.remove(black_file)
    assert r_black["passed"] is False
    assert r_black["black_detect"]["passed"] is False
    assert any("black" in e.lower() for e in r_black["errors"])
    print("  ✓ Black frames sequence correctly rejected")

    # 5. Freeze frame detection (freezedetect >= 0.4s)
    freeze_file = "test_frozen_video.mp4"
    # Create video holding 1 static test frame for 1.5 seconds
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "smptebars=s=720x1280:r=30",
        "-t", "1.5", "-c:v", "libx264", "-pix_fmt", "yuv420p", freeze_file
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    r_freeze = audit_preview_video(freeze_file)
    os.remove(freeze_file)
    assert r_freeze["passed"] is False
    assert r_freeze["freeze_detect"]["passed"] is False
    assert r_freeze["motion_variance"]["passed"] is False  # static image RMS is 0
    assert any("freeze" in e.lower() for e in r_freeze["errors"])
    print("  ✓ Frozen video (>=0.4s) correctly rejected by freezedetect & motion variance")

    # 6. Require audio rejection when audio is missing
    r_no_audio = audit_preview_video("assets/test_portrait.mp4", require_audio=True)
    assert r_no_audio["passed"] is False
    assert any("Audio track missing" in e for e in r_no_audio["errors"])
    print("  ✓ Missing audio correctly rejected when require_audio=True")

    print(">>> TEST 3 PASSED: All negative invariants strictly rejected!\n")


def test_gate7_integration():
    print("=== TEST 4: Gate 7 Verifier Hook Integration ===")
    # Build clean mock bundle
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("scene.scn", "Component.RenderMeshVisual Component.Head Component.ParticleSystem")
        z.writestr("visor.mesh", b"MESH" * 20000)

    lens_data = {
        "lens_name": "Cyber Titanium HUD",
        "account_id": "2",
        "asset_statuses": {
            "prefetched_assets": {
                "titanium_visor": {"status": "SUCCESS"}
            }
        }
    }

    import lens_simulator
    orig_judge = lens_simulator.LensSimulator.judge_visuals_with_gemini_vision
    lens_simulator.LensSimulator.judge_visuals_with_gemini_vision = lambda *a, **kw: {
        "passed": True, "score": 92, "virality_score": 92,
        "is_background_only": False, "is_cringe_or_defective": False,
        "has_foreground_3d": True, "critique": "Optimal anatomical fit"
    }

    try:
        verifier = LensVerifier(lens_data=lens_data, plan={"prompt": "PBR metallic visor chrome mouth open", "lens_name": "Cyber Titanium HUD"})
        g7 = verifier.verify_visual_simulation(buf.getvalue())
        g7_report = verifier.report["gates"]["gate7_visual_simulation"]
        print(f"Gate 7 Result: {g7}")
        print(f"Video audit inside Gate 7 report: {g7_report.get('video_audit', {}).get('passed')}")

        assert "video_audit" in g7_report, "Gate 7 report must include video_audit"
        assert g7_report["video_audit"]["passed"] is True, "Video audit in Gate 7 must pass"
        assert g7 is True, "Gate 7 must pass when video audit and visual analysis pass"

        # Now simulate a defective video in Gate 7 by mocking render_simulation_video to return a corrupt/frozen video
        corrupt_video = "corrupt_test_preview.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=720x1280:r=30",
            "-t", "1.0", "-c:v", "libx264", "-pix_fmt", "yuv420p", corrupt_video
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        class MockSimulatorDefective(lens_simulator.LensSimulator):
            def render_simulation_video(self, *args, **kwargs):
                return corrupt_video

        orig_sim = lens_simulator.LensSimulator
        lens_simulator.LensSimulator = MockSimulatorDefective
        try:
            defective_verifier = LensVerifier(lens_data=lens_data, plan={"prompt": "PBR metallic visor chrome", "lens_name": "Cyber Titanium HUD"})
            g7_defective = defective_verifier.verify_visual_simulation(buf.getvalue())
            print(f"Gate 7 with defective video: {g7_defective} (Expected: False)")
            print(f"Defective verifier errors: {defective_verifier.report['errors']}")
            assert g7_defective is False, "Gate 7 MUST FAIL when preview video fails audit"
            assert any("Gate 7 Failed: Video Audit Error" in err or "automated quality & freeze audit" in err for err in defective_verifier.report["errors"])
            print("  ✓ Gate 7 strictly rejects defective video and logs exact audit failure reasons")
        finally:
            lens_simulator.LensSimulator = orig_sim
            if os.path.exists(corrupt_video):
                os.remove(corrupt_video)
    finally:
        lens_simulator.LensSimulator.judge_visuals_with_gemini_vision = orig_judge

    print(">>> TEST 4 PASSED: Gate 7 integration verified with 100% precision!\n")


if __name__ == "__main__":
    test_audit_test_portrait()
    test_audit_newly_generated_preview()
    test_rejection_invariants()
    test_gate7_integration()
    print("🎉 ALL VIDEO QUALITY AUDIT TESTS PASSED SUCCESSFULLY!")
