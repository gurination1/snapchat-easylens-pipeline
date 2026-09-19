import os
import sys
import json
import zipfile
import io
import urllib.request

from lens_verifier import LensVerifier
import gemini_lens_agent
import pipeline_runner

def test_ion_pulse_velo_rejection():
    print("=== TEST 1: Ion Pulse Velo Rejection by Gate 5 ===")
    meta_path = "/root/snapchat-lens/artifacts/run_35434894216/snapchat-lens-verified-data/generated_lens_metadata.json"
    pub_path = "/root/snapchat-lens/artifacts/run_35434894216/snapchat-lens-verified-data/publish_status.json"
    
    with open(meta_path) as f:
        lens_data = json.load(f)
    with open(pub_path) as f:
        pub_status = json.load(f)

    # Merge blocks and controller code to simulate raw AILC payload
    lens_data["blocks"] = pub_status.get("blocks", [])
    lens_data["controller_code"] = pub_status.get("controller_code", "")

    url = lens_data["download_url"]
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        bundle_bytes = resp.read()

    verifier = LensVerifier(lens_data=lens_data, plan={"prompt": "test", "lens_name": "Ion Pulse Velo"})
    g5 = verifier.verify_controller_and_assets(bundle_bytes)

    print(f"Gate 5 Result: {g5} (Expected: False)")
    g5_report = verifier.report["gates"]["gate5_assets_and_controller"]
    print("Canvas API Detected:", g5_report.get("canvas_api_detected"))
    print("Canvas Violations Count:", len(g5_report.get("canvas_violations", [])))
    for v in g5_report.get("canvas_violations", []):
        print(f"  - {v}")

    assert g5 is False, "Gate 5 MUST REJECT Ion Pulse Velo"
    assert g5_report.get("canvas_api_detected") is True, "Gate 5 must flag canvas_api_detected"
    assert len(g5_report.get("canvas_violations", [])) > 0, "Gate 5 must list canvas violations"
    print(">>> TEST 1 PASSED: Ion Pulse Velo strictly rejected by Gate 5!\n")

def test_clean_bundle_acceptance():
    print("=== TEST 2: Clean Synthetic Bundle Acceptance by Gate 5 ===")
    # Build a clean mock zip without CanvasAPI
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as z:
        z.writestr("scripts/LensController.js", """
            // Clean controller with pure 3D face event triggers
            script.createEvent("OnStartEvent").bind(function() {
                script.visor.enabled = true;
            });
            script.face_events.onMouthOpened.add(function() {
                script.particles.enabled = true;
            });
        """)
        z.writestr("scene.scn", "Component.RenderMeshVisual Component.Head Component.ParticleSystem")

    clean_bundle = zip_buffer.getvalue()
    clean_lens_data = {
        "asset_statuses": {
            "prefetched_assets": {
                "3d_visor": {"status": "SUCCESS"}
            }
        },
        "blocks": [
            {"name": "Selfie Attachments", "key": "hud_visor", "description": "3D Visor"},
            {"name": "Sparkles", "key": "sparks", "description": "3D Particles"}
        ]
    }

    verifier = LensVerifier(lens_data=clean_lens_data, plan={"prompt": "clean prompt", "lens_name": "Clean Lens"})
    g5 = verifier.verify_controller_and_assets(clean_bundle)
    print(f"Clean Gate 5 Result: {g5} (Expected: True)")
    assert g5 is True, "Gate 5 should pass a clean bundle"
    print(">>> TEST 2 PASSED: Clean bundle accepted by Gate 5!\n")

def test_gate6_banned_tokens():
    print("=== TEST 3: Gate 6 Banned Spinner Tokens ===")
    banned_phrases = [
        "orbiting bars", "frequency bars", "equalizer crown", "spectrum rings",
        "equalizer bars", "audio-reactive bars", "sound visualizer rings",
        "rotating bars", "spinning bars", "equalizer halo", "frequency halo"
    ]

    for phrase in banned_phrases:
        test_prompt = f"Cyberpunk titanium visor with {phrase} around head, PBR metallic chrome, mouth open triggers shockwave."
        verifier = LensVerifier(lens_data={}, plan={"prompt": test_prompt, "lens_name": "Test"})
        g6 = verifier.verify_judge_ai()
        score = verifier.report["gates"]["gate6_judge_ai"]["score"]
        deductions = verifier.report["gates"]["gate6_judge_ai"]["deductions"]
        print(f"Phrase '{phrase}': Gate 6={g6}, Score={score}, Deductions={deductions}")
        assert any("banned 2D canvas spinner" in d for d in deductions), f"Expected deduction for '{phrase}'"
        assert g6 is False, f"Expected Gate 6 to reject prompt containing '{phrase}'"

    print(">>> TEST 3 PASSED: All banned spinner phrases rejected by Gate 6!\n")

def test_gemini_lens_agent_rules():
    print("=== TEST 4: Gemini Lens Agent Banned Rule Verification ===")
    p2 = gemini_lens_agent.ACCOUNT_PERSONAS["2"]["theme_focus"]
    print("Persona 2 theme_focus:", p2)
    assert "equalizer" not in p2.lower(), "Persona 2 must not contain 'equalizer'"
    assert "bars" not in p2.lower(), "Persona 2 must not contain 'bars'"
    assert "pure 3d assets only" in p2.lower()

    # Check fallback in pipeline_runner
    p2_fallback = pipeline_runner.STATIC_FALLBACKS["2"]["prompt"]
    print("Pipeline runner Persona 2 fallback:", p2_fallback)
    assert "equalizer" not in p2_fallback.lower(), "Pipeline runner fallback must not contain 'equalizer'"
    assert "bars" not in p2_fallback.lower(), "Pipeline runner fallback must not contain 'bars'"
    print(">>> TEST 4 PASSED: Persona 2 and fallbacks cleaned of all spinner phrases!\n")

if __name__ == "__main__":
    test_ion_pulse_velo_rejection()
    test_clean_bundle_acceptance()
    test_gate6_banned_tokens()
    test_gemini_lens_agent_rules()
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
