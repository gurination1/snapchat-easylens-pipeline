import os
import io
import json
import zipfile
import subprocess
from lens_verifier import LensVerifier
from lens_simulator import LensSimulator

def test_syntax_error_rejected():
    print("=== TEST 1: JS Syntax Error Detection via node -c ===")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("broken_script.js", "function broken( { return 42; }")
    
    verifier = LensVerifier(lens_data={"asset_statuses": {"prefetched_assets": {"mesh": {}}}})
    passed = verifier.verify_controller_and_assets(buf.getvalue())
    g5 = verifier.report["gates"]["gate5_assets_and_controller"]
    print(f"Passed: {passed} (Expected: False)")
    print(f"Fatal errors: {g5['fatal_script_errors']}")
    assert passed is False
    assert any("Syntax Error" in err for err in g5["fatal_script_errors"])
    print(">>> TEST 1 PASSED!\n")

def test_dom_global_rejected():
    print("=== TEST 2: Browser DOM Global Rejection (window/document) ===")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("dom_script.js", "function init() { window.location.href = 'https://snapchat.com'; }")
    
    verifier = LensVerifier(lens_data={"asset_statuses": {"prefetched_assets": {"mesh": {}}}})
    passed = verifier.verify_controller_and_assets(buf.getvalue())
    g5 = verifier.report["gates"]["gate5_assets_and_controller"]
    print(f"Passed: {passed} (Expected: False)")
    print(f"Fatal errors: {g5['fatal_script_errors']}")
    assert passed is False
    assert any("window" in err for err in g5["fatal_script_errors"])
    print(">>> TEST 2 PASSED!\n")

def test_valid_js_accepted():
    print("=== TEST 3: Valid Script Acceptance ===")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("clean_controller.js", "var count = 10; function tick() { count += 1; return count; }")
    
    verifier = LensVerifier(lens_data={"asset_statuses": {"prefetched_assets": {"mesh": {}}}})
    passed = verifier.verify_controller_and_assets(buf.getvalue())
    g5 = verifier.report["gates"]["gate5_assets_and_controller"]
    print(f"Passed: {passed} (Expected: True)")
    assert passed is True
    assert len(g5["fatal_script_errors"]) == 0
    print(">>> TEST 3 PASSED!\n")

def test_video_audit_black_screen():
    print("=== TEST 4: Black Screen Video Rejection ===")
    black_vid = "/tmp/test_black.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=720x1280:d=3:r=30",
        "-c:v", "libx264", "-b:v", "2000k", "-minrate", "2000k", "-maxrate", "2000k", "-bufsize", "4000k",
        "-pix_fmt", "yuv420p",
        black_vid
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    
    audit = LensSimulator.audit_preview_video(black_vid)
    print("Black video audit:", audit)
    if os.path.exists(black_vid):
        os.remove(black_vid)
    assert audit["passed"] is False
    err_str = " ".join(audit.get("errors", [])) + " " + str(audit.get("error", ""))
    assert any(w in err_str.lower() for w in ["black", "small", "motion"])
    print(">>> TEST 4 PASSED!\n")

def test_video_audit_motion_portrait():
    print("=== TEST 5: Real Motion Portrait Acceptance & Variance ===")
    portrait_vid = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "test_portrait.mp4")
    assert os.path.exists(portrait_vid)
    
    audit = LensSimulator.audit_preview_video(portrait_vid)
    print("Motion video audit:", audit)
    assert audit["passed"] is True
    assert audit["motion_variance"]["avg_rms"] > 0.8
    assert audit["resolution"] == [720, 1280]
    print(">>> TEST 5 PASSED!\n")

def test_audio_resolver():
    print("=== TEST 6: Niche Audio Resolver ===")
    sim = LensSimulator(b"", lens_data={"lens_name": "Test"}, portrait_dir="assets")
    tracks = {
        "1": sim.resolve_audio_track(account_id="1"),
        "2": sim.resolve_audio_track(account_id="2"),
        "3": sim.resolve_audio_track(account_id="3"),
        "4": sim.resolve_audio_track(account_id="4"),
        "5": sim.resolve_audio_track(account_id="5")
    }
    for aid, path in tracks.items():
        print(f"Account {aid} Audio Track: {path}")
        assert path is not None and os.path.exists(path)
    assert "mythic_roar.mp3" in tracks["1"]
    assert "cyber_pulse.mp3" in tracks["2"]
    assert "comedy_pop.mp3" in tracks["3"]
    assert "luxury_shimmer.mp3" in tracks["4"]
    assert "mercury_drift.mp3" in tracks["5"]
    print(">>> TEST 6 PASSED!\n")

def main():
    test_syntax_error_rejected()
    test_dom_global_rejected()
    test_valid_js_accepted()
    test_video_audit_black_screen()
    test_video_audit_motion_portrait()
    test_audio_resolver()
    print("ALL ADVANCED GATE VERIFICATIONS PASSED WITH 100% SUCCESS!")

if __name__ == "__main__":
    main()
