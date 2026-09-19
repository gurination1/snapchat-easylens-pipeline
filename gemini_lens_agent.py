import os
import sys
import json
import time
import requests

CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest"
]


def get_gemini_api_keys():
    keys = []
    if os.getenv("GEMINI_API_KEY"):
        keys.append(os.getenv("GEMINI_API_KEY").strip())
    if os.getenv("GEMINI_API_KEYS"):
        for k in os.getenv("GEMINI_API_KEYS").split(","):
            k = k.strip()
            if k and k not in keys:
                keys.append(k)
    return keys


ACCOUNT_PERSONAS = {
    "1": {
        "channel": "MythicBeasts_AR",
        "genre": "3D Mythic Headpiece & Elemental Breath",
        "theme_focus": "Sculpted obsidian dragon horn crown anchored to temples with liquid 24k gold filigree and caustic ruby gems, PBR anisotropic metallic reflections, 3-point contrast 6500K/2800K lighting with ray-traced contact shadows. Mouth open erupts turbulent emerald flame torrent with floating amber sparks; smiling ignites bright golden runic eye halos. Depth occlusion enabled, zero strobing.",
        "primary_trigger": "MouthOpen (Turbulent emerald dragon flame torrent & embers) / Smile (Bright golden runic eye halos)",
        "tag_pool": ["dragon", "3d", "headpiece", "horns", "fantasy", "pbr"]
    },
    "2": {
        "channel": "RaveMotion_Studio",
        "genre": "Cyberpunk Audio-Reactive Visor & Beat FX",
        "theme_focus": "Sleek ergonomic 3D cyberpunk HUD glasses and holographic visor resting across eyes, leaving cheeks and mouth uncovered for clean facial tracking. Brushed titanium frame with pulsing cyan neon edge emission and refractive glass. Orbiting audio-reactive equalizer bars halo head. 3-point contrast lighting with ray-traced shadows. Opening mouth triggers radial laser shockwave; smiling activates bright neon visor HUD readout. Zero strobing, zero easing curves.",
        "primary_trigger": "MouthOpen (Laser particle shockwave) / Smile (Neon visor HUD flare)",
        "tag_pool": ["cyberpunk", "visor", "rave", "music", "audioreactive", "neon"]
    },
    "3": {
        "channel": "WarpShock_Comedy",
        "genre": "Viral Meme & Exaggerated Face AR",
        "theme_focus": "Fluffy 3D cartoon stormcloud hovering directly above head with gentle glowing rain droplets and soft ambient thunder light. PBR volumetric stylization, 3-point contrast lighting. Opening mouth erupts an exaggerated geyser of liquid mercury tears and spinning 24k gold coins bouncing off screen frame; smiling triggers a dramatic cartoon lightning rim flash. Physics-driven, zero strobe.",
        "primary_trigger": "MouthOpen (Exaggerated geyser of liquid tears & coins) / Smile (Dramatic cartoon lightning rim flash)",
        "tag_pool": ["meme", "crying", "funny", "cloud", "cartoon", "morph"]
    },
    "4": {
        "channel": "Lumiere_Atelier",
        "genre": "35mm Analog Luxury & Haute Couture",
        "theme_focus": "Sculpted 24k gold leaf baroque crown fitted to temples with pale champagne crystal halo and caustic crystal prisms. Warm Kodak Portra 35mm film halation with colorCorrection 10 Golden Glow and grain. Anisotropic PBR reflections, ray-traced shadows. Smiling unleashes rich golden sparkle dust cascading across cheekbones. Photosensitive safe, zero strobing.",
        "primary_trigger": "Smile (Golden sparkle dust caustics across cheekbones) / BrowRaise (Prismatic crystal shimmer)",
        "tag_pool": ["film", "35mm", "crown", "gold", "luxury", "aesthetic"]
    },
    "5": {
        "channel": "Chrono_Mirage",
        "genre": "Surrealism & Zero-G Liquid Chrome",
        "theme_focus": "Zero-G floating liquid mercury halo crown morphing above head with sculpted chrome cheek plates. Anisotropic mirror PBR reflections with fluid surface tension, 3-point contrast lighting and ray-traced contact shadows. Opening mouth releases orbiting liquid chrome spheres with refractive rippling reflections; smiling ripples the ambient background. Seamless physics, zero strobing.",
        "primary_trigger": "MouthOpen (Orbiting liquid chrome spheres around head) / Smile (Fluid ripple normal-map distortion)",
        "tag_pool": ["surreal", "chrome", "halo", "optical", "cyber", "mirage"]
    }
}


def extract_json(raw_text: str) -> dict:
    text = raw_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text, strict=False)
    except Exception:
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            clean_text = match.group(0)
            try:
                return json.loads(clean_text, strict=False)
            except Exception:
                # Replace unescaped literal newlines inside quotes
                sanitized = re.sub(r'(?<!\\)\n', r'\\n', clean_text)
                return json.loads(sanitized, strict=False)
        raise


def generate_lens_prompt(account_id: str = "1", custom_instructions: str = "") -> dict:
    api_keys = get_gemini_api_keys()
    if not api_keys:
        raise ValueError("Missing GEMINI_API_KEY or GEMINI_API_KEYS environment variable.")

    persona = ACCOUNT_PERSONAS.get(str(account_id), ACCOUNT_PERSONAS["1"])

    system_prompt = (
        "You are an Elite Snapchat AR Director and Principal Prompt Engineer for Snapchat EasyLens (Lens Studio Web SnapML/AILC).\n"
        "Your task is to engineer an insanely high-quality, anti-slop, compliance-verified Lens prompt that guarantees high virality and engagement.\n\n"
        "STRICT ANTI-SLOP, ANTI-CRINGE & PRODUCTION QUALITY RULES:\n"
        "1. ZERO ON-SCREEN DEVELOPER UI, SLIDERS, OR BUTTONS: The lens must be 100% immersive full-screen camera AR. STRICTLY FORBID all touch sliders, UI parameter panels, controller widgets, or debug buttons (no 'Rings', 'Wave', 'Flare' sliders).\n"
        "2. ZERO ON-SCREEN TEXT, LABELS, WATERMARKS, OR GREETINGS: Do NOT generate or render any text, subtitles, greetings, watermarks, or score counters on screen (no 'Thank you', no 'Tap to Start', no UI labels). The lens must be pure visual and auditory AR.\n"
        "3. BANNED SLOP: Generic purple gradients, floating disembodied blobs, rubbery plastic textures, cheesy clipart, and jittery motion.\n"
        "4. MANDATORY PBR CRAFT: Physically Based Rendering materials (anisotropic brushed titanium, liquid mercury, 24k gold filigree, refractive optical glass, subsurface scattering).\n"
        "5. MANDATORY 3-POINT CONTRAST LIGHTING: Key light + contrasting 6500K/2800K directional rim lighting + baked ray-traced contact shadows.\n"
        "6. MANDATORY FRONT-CAMERA SELFIE ANCHORING: Primary 3D object MUST be anchored directly to HEAD or FACE (e.g. fitted titanium visor across eyes leaving mouth exposed, sculpted crown on forehead, zero-G halo above head). NEVER attach to shoulders or full-body tracking. NEVER generate opaque full-face motorcycle helmets that occlude the mouth on mouth-trigger lenses.\n"
        "7. MANDATORY ANIMATION & DYNAMIC FACE TRIGGERS: Must describe animated reactive responses on Face Events: opening mouth triggers high-energy volumetric reaction (particle shockwave, emerald flame torrent, liquid tears geyser); smiling triggers radiant bloom, eye flares, or holographic HUD flare. Seamless, photosensitive-safe, zero strobe.\n"
        "8. COMPLIANCE & SAFETY:\n"
        "   - Under 480 characters for the prompt string to prevent AILC backend truncation.\n"
        "   - Zero trademarked/copyrighted names (NO Marvel, Goku, Pokemon, Nike, etc. Use generic archetype nouns).\n"
        "   - Zero race/skin tone alterations. Non-human fantasy surfaces (chrome, gold leaf, stone) only.\n"
        "   - No rapid white flashing/strobe (photosensitive safety compliance).\n"
        "   - No weapons pointed directly at camera/face.\n"
        "9. STRICT JAVASCRIPT ENGINE COMPATIBILITY (ZERO TWEEN / ZERO EASING CURVES):\n"
        "   - Lens Studio Web script runtime crashes with fatal ReferenceError on undeclared TWEEN references.\n"
        "   - NEVER use the words 'smooth tween', 'bezier curve', 'ease-in', 'ease-out', or 'custom easing curve' in the prompt, as this causes the AILC code generator to hallucinate undeclared `TWEEN.Easing` references that crash the Lens.\n"
        "   - Describe transitions using discrete visual triggers or particle streams: 'Opening mouth triggers instant radial cyan laser shockwave; smiling triggers radiant neon HUD flare with soft golden bloom'.\n"
        "   - Mandate zero external TWEEN dependencies; use native Lens Studio component triggers only.\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "lens_name": "Catchy 2-4 word Title without trademarked terms",\n'
        '  "prompt": "Dense, single-paragraph EasyLens prompt under 480 characters",\n'
        '  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],\n'
        '  "visual_hook": "1-line explanation of the 0.2s psychological hook",\n'
        '  "trigger_sequence": "1-line explanation of the face-trigger interaction"\n'
        "}"
    )

    user_prompt = (
        f"Generate a unique, viral Lens concept for Account #{account_id} ({persona['channel']}).\n"
        f"Genre: {persona['genre']}\n"
        f"Core Theme: {persona['theme_focus']}\n"
        f"Primary Trigger Mechanism: {persona['primary_trigger']}\n"
        f"Recommended Tag Pool: {', '.join(persona['tag_pool'])}\n"
        "CRITICAL: Full-screen camera effect only. ZERO developer UI sliders, ZERO on-screen text, ZERO floating buttons. ZERO custom easing/TWEEN curves.\n"
    )

    # Deduplication memory from published history
    if os.path.exists("published_lenses.json"):
        try:
            with open("published_lenses.json", "r") as f:
                history = json.load(f)
            if history:
                recent_lines = [
                    f"- '{item.get('lens_name')}' (Acc #{item.get('account_id')}): {item.get('visual_hook', '')}"
                    for item in history[-15:]
                ]
                user_prompt += (
                    "\nPREVIOUSLY CREATED LENSES IN FLEET (CRITICAL ANTI-DUPLICATION RULE: DO NOT DUPLICATE OR RECYCLE THESE):\n"
                    + "\n".join(recent_lines)
                    + "\nMake this new concept fresh, distinctive, and completely novel!\n"
                )
        except Exception:
            pass

    if custom_instructions:
        user_prompt += f"Special User Direction: {custom_instructions}\n"

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
            "maxOutputTokens": 2048
        }
    }

    last_err = None
    for model_name in CANDIDATE_MODELS:
        for key in api_keys[:3]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            try:
                print(f"[GEMINI] Trying model {model_name} with key {key[:8]}... for Account #{account_id}")
                res = requests.post(url, json=payload, timeout=45)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    result = extract_json(raw_text)

                    # Post-validation of length
                    if len(result.get("prompt", "")) > 480:
                        print("[WARN] Prompt length exceeded 480 chars, trimming gracefully...")
                        result["prompt"] = result["prompt"][:477] + "..."

                    print(f"[GEMINI OK] Model: {model_name}")
                    print(f"[GEMINI OK] Generated Lens: {result.get('lens_name')}")
                    print(f"[GEMINI OK] Prompt: {result.get('prompt')}")
                    print(f"[GEMINI OK] Tags: {result.get('tags')}")
                    return result
                else:
                    last_err = f"{res.status_code}: {res.text}"
                    print(f"[GEMINI WARN] Model {model_name} returned {res.status_code}")
                    time.sleep(1)
            except Exception as e:
                last_err = str(e)
                print(f"[GEMINI WARN] Request exception: {e}")
                time.sleep(1)

    raise RuntimeError(f"All Gemini models and keys failed. Last error: {last_err}")


if __name__ == "__main__":
    acc = sys.argv[1] if len(sys.argv) > 1 else "1"
    output = generate_lens_prompt(acc)
    print(json.dumps(output, indent=2))
