import json
import os
import sys
import re

import gemini_lens_agent
from gemini_lens_agent import (
    CHANNEL_PROMPT_MATRICES,
    ACCOUNT_PERSONAS,
    sanitize_lens_prompt,
    select_channel_archetype,
    validate_candidate_concept,
    load_published_history,
    compute_token_jaccard,
)
import pipeline_runner
from pipeline_runner import (
    STATIC_FALLBACKS,
    BlueprintPool,
    select_lru_fallback,
)
from lens_verifier import LensVerifier


def test_archetype_matrix_expansion():
    print("=== TEST 1: Archetype Matrix 50 Fleet Concepts ===")
    assert len(CHANNEL_PROMPT_MATRICES) == 5, f"Expected 5 channels, got {len(CHANNEL_PROMPT_MATRICES)}"
    
    total_archetypes = 0
    all_ids = set()
    all_names = set()

    expected_channels = {
        "1": "MythicBeasts_AR",
        "2": "SciFi_Optics",
        "3": "WarpShock_Comedy",
        "4": "Lumiere_Atelier",
        "5": "Chrono_Mirage"
    }

    for aid, name in expected_channels.items():
        spec = CHANNEL_PROMPT_MATRICES[aid]
        assert spec["channel_name"] == name, f"Channel {aid} name mismatch: {spec['channel_name']}"
        archetypes = spec["archetypes"]
        assert len(archetypes) == 10, f"Account {aid} ({name}) must have 10 archetypes, got {len(archetypes)}"
        total_archetypes += len(archetypes)

        for arch in archetypes:
            aid_id = arch["id"]
            assert aid_id not in all_ids, f"Duplicate archetype ID: {aid_id}"
            all_ids.add(aid_id)

            a_name = arch["name"]
            assert a_name not in all_names, f"Duplicate archetype name: {a_name}"
            all_names.add(a_name)

            focus = arch["focus"]
            assert 150 <= len(focus) <= 460, f"Archetype {aid_id} focus length {len(focus)} out of range (150-460)"
            
            # Anchoring
            assert re.search(r'\b(head|face|forehead|temple|brow|eyes|cheeks|hairline|crown)\b', focus, re.I), \
                f"Archetype {aid_id} missing head/face anchoring"

            # Trigger mechanism
            assert re.search(r'\b(mouth|smile|open|eyes|brow|glints?|flares?|breath|tears?)\b', focus, re.I), \
                f"Archetype {aid_id} missing trigger mechanism"

            # PBR specification
            assert any(tok in focus.lower() for tok in ["pbr", "metallic", "anisotropic", "mercury", "basalt", "gold", "subsurface", "chrome", "ray-traced", "shadow", "prismatic"]), \
                f"Archetype {aid_id} missing PBR specification"

            # Anti-slop / banned tokens
            assert not re.search(r'\b(tween|easing|bezier|canvas|bars|slider|purple gradient|floating blob)\b', focus, re.I), \
                f"Archetype {aid_id} contains forbidden token: {focus}"

    print(f"Total archetypes across fleet: {total_archetypes} (10 per channel * 5 channels)")
    assert total_archetypes == 50, f"Expected 50 total archetypes, got {total_archetypes}"
    print(">>> TEST 1 PASSED: 50 distinct fleet concepts verified!\n")


def test_tone_and_hooks_enforcement():
    print("=== TEST 2: Aesthetic Tones and Emotional Hooks Verification ===")
    
    # Account 1: MythicBeasts (dragon, phoenix, valkyrie, anubis, kitsune, leviathan)
    a1_tokens = ["dragon", "phoenix", "valkyrie", "anubis", "kitsune", "serpent", "gorgon", "chimera", "garuda", "leviathan"]
    a1_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["1"]["archetypes"]])
    for tok in a1_tokens:
        assert tok in a1_foci, f"Account 1 missing key mythic token: {tok}"

    # Account 2: SciFi_Optics (hud, visor, scanner, reticle, telemetry - ZERO canvas)
    a2_tokens = ["visor", "scanner", "reticle", "telemetry", "spectacles", "monocular"]
    a2_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["2"]["archetypes"]])
    for tok in a2_tokens:
        assert tok in a2_foci, f"Account 2 missing scifi optic token: {tok}"
    assert "canvas" not in a2_foci, "Account 2 must contain zero canvas references"
    assert "bars" not in a2_foci, "Account 2 must contain zero bar references"

    # Account 3: WarpShock_Comedy (stormcloud, crying, waterfall tears, steam rage, jaw-drop, gold coins)
    a3_tokens = ["stormcloud", "tears", "steam", "jaw-drop", "coins", "confetti", "hypno"]
    a3_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["3"]["archetypes"]])
    for tok in a3_tokens:
        assert tok in a3_foci, f"Account 3 missing comedy token: {tok}"

    # Account 4: Lumiere_Atelier (35mm film, 24k gold leaf, freshwater pearls, Portra 400, sparkle dust)
    a4_tokens = ["35mm", "gold leaf", "pearl", "portra", "sparkle dust", "filigree", "moonstone"]
    a4_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["4"]["archetypes"]])
    for tok in a4_tokens:
        assert tok in a4_foci, f"Account 4 missing luxury film token: {tok}"

    # Account 5: Chrono_Mirage (Y3K, liquid chrome, zero-g mercury halo, mobius, ferrofluid)
    a5_tokens = ["liquid mercury", "chrome", "zero-g", "mobius", "ferrofluid", "surface tension", "tesseract"]
    a5_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["5"]["archetypes"]])
    for tok in a5_tokens:
        assert tok in a5_foci, f"Account 5 missing Y3K chrome token: {tok}"

    print(">>> TEST 2 PASSED: Channel aesthetic tones and emotional hooks verified!\n")


def test_preflight_prompt_sanitizer():
    print("=== TEST 3: Pre-flight Prompt Sanitizer ===")
    dirty_prompts = [
        ("Visor with orbiting frequency bars haloing the crown and 2d canvas spinner.",
         ["frequency bars", "orbiting bars", "canvas", "spinner"]),
        ("Equalizer crown with spectrum rings and smooth tweening ease-in easing curve on canvasapi.",
         ["equalizer crown", "spectrum rings", "tween", "easing curve", "canvasapi"]),
        ("Audio-reactive bars rotating around head with generic purple gradient and floating disembodied blob.",
         ["audio-reactive bars", "rotating bars", "purple gradient", "floating disembodied blob"]),
        ("Spinning bars and sound visualizer rings on 2D canvas with developer UI sliders.",
         ["spinning bars", "sound visualizer rings", "canvas", "ui slider"]),
    ]

    for dirty, forbidden in dirty_prompts:
        cleaned = sanitize_lens_prompt(dirty)
        print(f"Original: {dirty}")
        print(f"Cleaned:  {cleaned}\n")
        assert len(cleaned) <= 460, f"Cleaned prompt exceeds 460 chars: {len(cleaned)}"
        for tok in forbidden:
            assert tok not in cleaned.lower(), f"Forbidden token '{tok}' still in cleaned: {cleaned}"
        # Verifier Gate 6 check on cleaned
        verifier = LensVerifier(lens_data={}, plan={"prompt": cleaned, "lens_name": "Sanitized Test"})
        verifier.verify_judge_ai()
        g6_report = verifier.report["gates"]["gate6_judge_ai"]
        deductions = g6_report.get("deductions", [])
        assert not any("banned 2D canvas spinner" in d for d in deductions), f"Sanitizer left spinner phrase in: {cleaned}"

    print(">>> TEST 3 PASSED: Pre-flight Prompt Sanitizer scrubs all forbidden tokens!\n")


def test_offline_verified_blueprint_pool():
    print("=== TEST 4: Offline Verified Blueprint Pool (25 Blueprints) ===")
    assert len(STATIC_FALLBACKS) == 5, f"Expected 5 accounts in STATIC_FALLBACKS, got {len(STATIC_FALLBACKS)}"
    
    total_blueprints = 0
    all_bp_names = set()

    for aid, pool in STATIC_FALLBACKS.items():
        assert isinstance(pool, BlueprintPool) or isinstance(pool, list), f"Pool for {aid} must be list/BlueprintPool"
        assert len(pool) == 5, f"Account {aid} must have 5 blueprints, got {len(pool)}"
        total_blueprints += len(pool)

        # Backwards compatibility check
        assert isinstance(pool["prompt"], str), f"STATIC_FALLBACKS['{aid}']['prompt'] must return string"
        assert pool["prompt"] == pool[0]["prompt"], "pool['prompt'] must match pool[0]['prompt']"
        assert isinstance(pool["lens_name"], str), f"STATIC_FALLBACKS['{aid}']['lens_name'] must return string"
        assert pool["lens_name"] == pool[0]["lens_name"], "pool['lens_name'] must match pool[0]['lens_name']"

        for bp in pool:
            name = bp["lens_name"]
            assert name not in all_bp_names, f"Duplicate blueprint name: {name}"
            all_bp_names.add(name)

            prompt = bp["prompt"]
            assert 150 <= len(prompt) <= 460, f"Blueprint '{name}' prompt length {len(prompt)} out of range (150-460)"
            assert len(bp["tags"]) >= 3, f"Blueprint '{name}' must have >= 3 tags"

            # Verify with Gate 6 Judge AI rubric
            verifier = LensVerifier(lens_data={}, plan={"prompt": prompt, "lens_name": name})
            g6 = verifier.verify_judge_ai()
            score = verifier.report["gates"]["gate6_judge_ai"]["score"]
            deductions = verifier.report["gates"]["gate6_judge_ai"]["deductions"]
            assert g6 is True, f"Blueprint '{name}' failed Gate 6 Judge AI! Score: {score}, Deductions: {deductions}"
            assert score >= 85, f"Blueprint '{name}' score {score} < 85 threshold"

    print(f"Total offline blueprints: {total_blueprints} (5 accounts * 5 blueprints)")
    assert total_blueprints == 25, f"Expected 25 total blueprints, got {total_blueprints}"
    print(">>> TEST 4 PASSED: All 25 offline blueprints verified with Judge AI >= 85!\n")


def test_lru_rotation_and_deduplication():
    print("=== TEST 5: LRU Rotation & Deduplication against published_lenses.json ===")
    history = load_published_history("published_lenses.json")
    print(f"Loaded {len(history)} historical lenses from published_lenses.json")

    for aid in ["1", "2", "3", "4", "5"]:
        # 1. Test select_channel_archetype
        selected_arch, banned_nouns = select_channel_archetype(aid, history)
        print(f"Account #{aid} selected archetype: '{selected_arch['name']}' ({selected_arch['id']})")
        print(f"Account #{aid} dynamically banned nouns: {banned_nouns}")

        # Ensure selected archetype is valid and has valid prompt
        assert selected_arch is not None
        assert "id" in selected_arch
        assert "focus" in selected_arch

        # 2. Test select_lru_fallback
        fallback_bp = select_lru_fallback(aid, history=history)
        print(f"Account #{aid} LRU Static Fallback: '{fallback_bp['lens_name']}'")
        assert fallback_bp is not None
        assert "lens_name" in fallback_bp
        assert "prompt" in fallback_bp
        assert len(fallback_bp["prompt"]) <= 460

        # Verify that fallback concept is not duplicating the most recent published lens for this account
        acc_lenses = [x for x in history if str(x.get("account_id")) == aid]
        if acc_lenses:
            latest_lens = acc_lenses[-1]
            latest_name = latest_lens.get("lens_name", "")
            # Must not duplicate exact title
            assert fallback_bp["lens_name"].lower() != latest_name.lower(), \
                f"Account #{aid} LRU selected duplicate of latest published lens '{latest_name}'"

    # Simulate sequential fallback rotation across 5 calls for Account 2 to prove 100% rotation
    sim_history = []
    selected_fallbacks = []
    for step in range(5):
        chosen = select_lru_fallback("2", history=sim_history)
        selected_fallbacks.append(chosen["lens_name"])
        sim_history.append({
            "account_id": "2",
            "lens_name": chosen["lens_name"],
            "prompt": chosen["prompt"],
            "timestamp": f"2026-09-19T12:0{step}:00Z"
        })

    print("Account #2 5-step LRU clean simulation sequence:", selected_fallbacks)
    assert len(set(selected_fallbacks)) == 5, f"LRU must cycle through all 5 blueprints without repetition: {selected_fallbacks}"

    print(">>> TEST 5 PASSED: LRU rotation and deduplication verified against published_lenses.json!\n")


if __name__ == "__main__":
    test_archetype_matrix_expansion()
    test_tone_and_hooks_enforcement()
    test_preflight_prompt_sanitizer()
    test_offline_verified_blueprint_pool()
    test_lru_rotation_and_deduplication()
    print("=" * 60)
    print("ALL 5 MULTI-TONE & SELF-HEALING ARCHITECTURE TESTS PASSED (100% SUCCESS)!")
    print("=" * 60)
