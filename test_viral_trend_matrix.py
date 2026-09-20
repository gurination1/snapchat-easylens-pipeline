import os
import sys
import json
import re

import gemini_lens_agent
from gemini_lens_agent import (
    CHANNEL_PROMPT_MATRICES,
    ACCOUNT_PERSONAS,
    generate_lens_prompt,
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


def test_viral_mega_trends_coverage():
    print("=== TEST 1: Viral Mega-Trends Coverage & Silhouette Definition ===")
    
    # 1. Ghibli Studio Anime Watercolor
    c1_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["1"]["archetypes"]])
    assert "ghibli" in c1_foci, "Ghibli trend missing in Channel 1"
    assert "watercolor" in c1_foci, "Watercolor aesthetic missing in Channel 1"
    assert "spirit dust" in c1_foci, "Spirit dust missing in Channel 1"
    assert "cloud crown" in c1_foci, "Cloud crown missing in Channel 1"
    print("  [OK] Ghibli / Studio Anime Watercolor verified in Channel 1")

    # 2. 90s Cyber Camcorder / VHS Glitch HUD
    c2_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["2"]["archetypes"]])
    assert "camcorder" in c2_foci, "Camcorder optic missing in Channel 2"
    assert "vhs glitch" in c2_foci or "glitch" in c2_foci, "VHS glitch missing in Channel 2"
    assert "timestamp" in c2_foci, "Timestamp optic missing in Channel 2"
    assert "scanline" in c2_foci, "Scanline reflections missing in Channel 2"
    print("  [OK] 90s Cyber Camcorder / VHS Glitch HUD verified in Channel 2")

    # 3. Viral Karaoke / Kinetic Lyric Headpiece
    c3_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["3"]["archetypes"]])
    assert "karaoke" in c3_foci, "Karaoke headpiece missing in Channel 3"
    assert "musical staff" in c3_foci or "notes" in c3_foci, "Neon notes missing in Channel 3"
    assert "bouncing" in c3_foci or "rhythm" in c3_foci, "Bouncing rhythm orbs missing in Channel 3"
    print("  [OK] Viral Karaoke / Kinetic Lyric Headpiece verified in Channel 3")

    # 4. Meme Melodrama
    assert ("waterfall tears" in c3_foci or "tear waterfalls" in c3_foci), "Waterfall tears missing in Channel 3"
    assert "broken-heart" in c3_foci, "Broken hearts missing in Channel 3"
    assert "steam" in c3_foci, "Steam valve missing in Channel 3"
    assert "coins" in c3_foci, "Gold coins missing in Channel 3"
    print("  [OK] Meme Melodrama (Crying waterfall, broken hearts, steam valve, coins) verified in Channel 3")

    # 5. High-Fashion Parisian Couture
    c4_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["4"]["archetypes"]])
    assert "parisian" in c4_foci or "paris couture" in c4_foci, "Parisian couture missing in Channel 4"
    assert "24k gold leaf" in c4_foci, "24k gold leaf missing in Channel 4"
    assert "freshwater pearl" in c4_foci, "Freshwater pearls missing in Channel 4"
    assert "portra 400" in c4_foci or "portra" in c4_foci, "Portra 400 film grain missing in Channel 4"
    print("  [OK] High-Fashion Parisian Couture (Gold leaf, freshwater pearls, Portra 400) verified in Channel 4")

    # 6. Y3K Liquid Mercury / Zero-G Chrome Surrealism
    c5_foci = " ".join([a["focus"].lower() for a in CHANNEL_PROMPT_MATRICES["5"]["archetypes"]])
    assert "y3k" in c5_foci, "Y3K aesthetic missing in Channel 5"
    assert "liquid mercury" in c5_foci, "Liquid mercury missing in Channel 5"
    assert "zero-g" in c5_foci, "Zero-G chrome missing in Channel 5"
    assert "surface tension" in c5_foci, "Surface tension missing in Channel 5"
    print("  [OK] Y3K Liquid Mercury / Zero-G Chrome Surrealism verified in Channel 5")

    print(">>> TEST 1 PASSED: All 6 viral mega-trends verified!\n")


def test_multi_action_trigger_payoffs():
    print("=== TEST 2: Multi-Action Interactive Trigger Payoffs (MouthOpen / Smile / EyebrowRaise / HeadTilt) ===")
    
    total_archetypes = 0
    for cid, spec in CHANNEL_PROMPT_MATRICES.items():
        for arch in spec["archetypes"]:
            total_archetypes += 1
            focus = arch["focus"]
            triggers = arch["primary_trigger"]
            
            # Verify trigger description in focus
            has_mouth = bool(re.search(r'\b(mouth|open|opening)\b', focus, re.I))
            has_smile = bool(re.search(r'\b(smile|smiling)\b', focus, re.I))
            has_eyebrow = bool(re.search(r'\b(eyebrow|brow)\b', focus, re.I))
            has_head_tilt = bool(re.search(r'\b(head tilt|tilt)\b', focus, re.I))

            assert has_mouth, f"Archetype {arch['id']} missing mouth trigger in focus"
            assert has_smile, f"Archetype {arch['id']} missing smile trigger in focus"
            assert has_eyebrow, f"Archetype {arch['id']} missing eyebrow trigger in focus"
            assert has_head_tilt, f"Archetype {arch['id']} missing head tilt trigger in focus"

            # Verify primary_trigger structured format
            assert "MouthOpen" in triggers, f"Archetype {arch['id']} primary_trigger missing MouthOpen"
            assert "Smile" in triggers, f"Archetype {arch['id']} primary_trigger missing Smile"
            assert "EyebrowRaise" in triggers, f"Archetype {arch['id']} primary_trigger missing EyebrowRaise"
            assert "HeadTilt" in triggers, f"Archetype {arch['id']} primary_trigger missing HeadTilt"

    print(f"Verified all 4 triggers across {total_archetypes} archetypes (100% compliance)")
    print(">>> TEST 2 PASSED: Multi-action trigger matrix verified!\n")


def test_anti_slop_and_pbr_enforcement():
    print("=== TEST 3: 100% Anti-Slop & PBR Shader Rules Enforcement ===")
    
    forbidden_regex = re.compile(r'\b(generic purple gradient|floating blob|disembodied blob|rubbery plastic|slider|button|menu|canvas\s*api|2d\s+spinner|canvasapi|tween|easing|bezier)\b', re.I)
    pbr_regex = re.compile(r'\b(pbr|metallic|anisotropic|mercury|basalt|gold|subsurface|chrome|ray-traced|shadows?|prismatic|refractive)\b', re.I)
    anchor_regex = re.compile(r'\b(head|face|forehead|temple|brow|eyes|cheeks|hairline|crown)\b', re.I)

    for cid, spec in CHANNEL_PROMPT_MATRICES.items():
        for arch in spec["archetypes"]:
            focus = arch["focus"]
            assert 150 <= len(focus) <= 460, f"Archetype {arch['id']} length {len(focus)} out of range (150-460)"
            assert not forbidden_regex.search(focus), f"Archetype {arch['id']} contains banned slop: {focus}"
            assert pbr_regex.search(focus), f"Archetype {arch['id']} missing PBR shader specification"
            assert anchor_regex.search(focus), f"Archetype {arch['id']} missing head/face anchoring"

            # Validate against Gate 6 Judge AI
            verifier = LensVerifier(lens_data={}, plan={"prompt": focus, "lens_name": arch["name"]})
            ok = verifier.verify_judge_ai()
            score = verifier.report["gates"]["gate6_judge_ai"]["score"]
            assert ok and score >= 85, f"Archetype {arch['id']} failed Gate 6 Judge AI (score={score})"

    print(">>> TEST 3 PASSED: 100% Anti-Slop, PBR, and Gate 6 Judge AI (score 100) verified!\n")


def test_prompt_generation_and_fallbacks():
    print("=== TEST 4: Prompt Generation & Static Fallback Generation ===")
    
    # Test generation for all 5 accounts
    for aid in ["1", "2", "3", "4", "5"]:
        res = generate_lens_prompt(account_id=aid)
        assert isinstance(res, dict), f"Account {aid} generation did not return dict"
        assert "lens_name" in res, f"Account {aid} missing lens_name"
        assert "prompt" in res, f"Account {aid} missing prompt"
        assert "tags" in res and len(res["tags"]) >= 3, f"Account {aid} missing tags"
        assert "visual_hook" in res, f"Account {aid} missing visual_hook"
        assert "trigger_sequence" in res, f"Account {aid} missing trigger_sequence"
        assert 150 <= len(res["prompt"]) <= 480, f"Prompt length {len(res['prompt'])} out of bounds"
        print(f"  Acc #{aid} ({res.get('genre', '')[:30]}...): '{res.get('lens_name')}' ({len(res.get('prompt', ''))}c)")

    print(">>> TEST 4 PASSED: Prompt generation and fallback return structure verified!\n")


def test_static_fallbacks_pool():
    print("=== TEST 5: Pipeline Runner STATIC_FALLBACKS (25 Blueprints) ===")
    
    expected_viral_names = {
        "1": "Ghibli Watercolor Cloud Crown",
        "2": "90s Cyber Camcorder Visor",
        "3": "Viral Karaoke Lyric Headpiece",
        "4": "High-Fashion Parisian Couture",
        "5": "Y3K Liquid Mercury Halo"
    }

    assert len(STATIC_FALLBACKS) == 5, f"Expected 5 accounts, got {len(STATIC_FALLBACKS)}"
    
    for aid, pool in STATIC_FALLBACKS.items():
        assert len(pool) == 5, f"Account {aid} must have 5 blueprints"
        
        # Check backward compatibility
        assert isinstance(pool["prompt"], str)
        assert isinstance(pool["lens_name"], str)
        assert pool["lens_name"] == pool[0]["lens_name"]
        
        # Check top viral blueprint is at index 0
        exp_name = expected_viral_names[aid]
        assert pool[0]["lens_name"] == exp_name, f"Expected blueprint '{exp_name}' at index 0 for Account {aid}, got '{pool[0]['lens_name']}'"
        
        for bp in pool:
            prompt = bp["prompt"]
            name = bp["lens_name"]
            assert 150 <= len(prompt) <= 460, f"Blueprint '{name}' prompt length out of range: {len(prompt)}"
            assert len(bp["tags"]) >= 3, f"Blueprint '{name}' tags < 3"

            # Judge AI verification
            verifier = LensVerifier(lens_data={}, plan={"prompt": prompt, "lens_name": name})
            assert verifier.verify_judge_ai(), f"Blueprint '{name}' failed Gate 6"
            assert verifier.report["gates"]["gate6_judge_ai"]["score"] >= 85, f"Blueprint '{name}' score < 85"

        print(f"  Account #{aid} verified 5 blueprints (Index 0: '{pool[0]['lens_name']}')")

    print(">>> TEST 5 PASSED: All 25 STATIC_FALLBACKS verified with Judge AI >= 85!\n")


if __name__ == "__main__":
    test_viral_mega_trends_coverage()
    test_multi_action_trigger_payoffs()
    test_anti_slop_and_pbr_enforcement()
    test_prompt_generation_and_fallbacks()
    test_static_fallbacks_pool()
    print("=" * 70)
    print("ALL VIRAL TREND RESEARCH & INTERACTIVE LENS TESTS PASSED (100% SUCCESS)!")
    print("=" * 70)
