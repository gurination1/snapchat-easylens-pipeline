import os
import sys
import json
import time
import requests

CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.1-pro-preview",
    "gemini-3.5-flash"
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
        "theme_focus": "3D dragon horned crown sculpted securely onto head with anisotropic obsidian scales and gold filigree. Opening mouth unleashes animated emerald fire particle stream with flying embers. Glowing runic eyes on smile.",
        "primary_trigger": "MouthOpen (Emerald dragon flame particles) / Smile (Glowing runic eyes)",
        "tag_pool": ["dragon", "3d", "headpiece", "horns", "fantasy", "pbr"]
    },
    "2": {
        "channel": "RaveMotion_Studio",
        "genre": "Cyberpunk Audio-Reactive Visor & Beat FX",
        "theme_focus": "3D holographic cyberpunk visor fitted over user's eyes with floating audio visualizer spectrum bars around head. Opening mouth unleashes glowing neon laser particle shockwaves with chromatic aberration.",
        "primary_trigger": "MouthOpen (Laser particle blast) / Smile (Neon spectrum flare)",
        "tag_pool": ["cyberpunk", "visor", "rave", "music", "audioreactive", "neon"]
    },
    "3": {
        "channel": "WarpShock_Comedy",
        "genre": "Viral Meme & Exaggerated Face AR",
        "theme_focus": "3D comedic stormcloud hovering directly above user's head with rain particles. Opening mouth erupts an exaggerated voluminous geyser of liquid mercury tears and gold coins. Smiling triggers a dramatic cartoon lightning flash.",
        "primary_trigger": "MouthOpen (Geyser of liquid tears & coins) / Smile (Lightning flash)",
        "tag_pool": ["meme", "crying", "funny", "cloud", "cartoon", "morph"]
    },
    "4": {
        "channel": "Lumiere_Atelier",
        "genre": "35mm Analog Luxury & Haute Couture",
        "theme_focus": "Sculpted 24k gold leaf baroque crown attached firmly to forehead and temples with caustic crystal prisms. Subtle Kodak 35mm film halation with caustic sparkle dust particles bursting across cheekbones on smile.",
        "primary_trigger": "Smile (Prism caustic sparkle dust) / BrowRaise (Golden shimmer)",
        "tag_pool": ["film", "35mm", "crown", "gold", "luxury", "aesthetic"]
    },
    "5": {
        "channel": "Chrono_Mirage",
        "genre": "Surrealism & Zero-G Liquid Chrome",
        "theme_focus": "3D floating liquid mercury halo crown morphing directly above user's head with chrome facial plates. Opening mouth emits orbiting liquid chrome spheres with refractive rippling reflections.",
        "primary_trigger": "MouthOpen (Orbiting liquid chrome spheres) / Smile (Mirror ripple distortion)",
        "tag_pool": ["surreal", "chrome", "halo", "optical", "cyber", "mirage"]
    }
}


def extract_json(text: str) -> dict:
    text = text.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
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
        "STRICT ANTI-SLOP & PRODUCTION QUALITY RULES:\n"
        "1. BANNED: Generic purple gradients, floating disembodied blobs, rubbery plastic textures, and jittery motion.\n"
        "2. MANDATORY: Physically Based Rendering (PBR) materials (anisotropic metal, porous basalt, liquid mercury, 24k gold, subsurface scattering).\n"
        "3. MANDATORY: 3-point contrast lighting (key light + contrasting 6500K/2800K directional rim lighting + ray-traced contact shadows).\n"
        "4. MANDATORY FRONT-CAMERA SELFIE ANCHORING: Primary 3D object MUST be anchored directly to HEAD or FACE (e.g., fitted crown, sculpted horns, cyberpunk visor, face armor, floating halo). NEVER attach to shoulders or full-body tracking.\n"
        "5. MANDATORY ANIMATION & INTERACTIVE PARTICLES: Must describe animated particle effects or glowing mesh reactions explicitly triggered by opening mouth or smiling (e.g., opening mouth emits glowing particle flame/laser beam/coins; smiling triggers eye flare).\n"
        "6. COMPLIANCE & SAFETY:\n"
        "   - Under 480 characters for the prompt string to prevent AILC backend truncation.\n"
        "   - Zero trademarked/copyrighted names (NO Marvel, Goku, Pokemon, Nike, etc. Use generic archetype nouns).\n"
        "   - Zero race/skin tone alterations. Non-human fantasy surfaces (chrome, gold leaf, stone) only.\n"
        "   - No rapid white flashing/strobe (photosensitive safety compliance).\n"
        "   - No weapons pointed directly at camera/face.\n\n"
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
                res = requests.post(url, json=payload, timeout=25)
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
