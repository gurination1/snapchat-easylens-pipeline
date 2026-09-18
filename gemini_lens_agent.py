import os
import sys
import json
import time
import requests

CANDIDATE_MODELS = [
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-2.5-pro"
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
        "channel": "TitanForge_AR",
        "genre": "Mythic 3D Beasts & Familiars",
        "theme_focus": "3D photorealistic perched dragons, wyverns, or cyber beasts with ray-traced contact shadows and volumetric breath weapons on mouth open.",
        "primary_trigger": "MouthOpen (Breath weapon / roar / attack)",
        "tag_pool": ["dragon", "3d", "creature", "fantasy", "pbr", "beast"]
    },
    "2": {
        "channel": "RaveMotion_Studio",
        "genre": "Full-Body Dance & Audio-Reactive Stage",
        "theme_focus": "Full-body tracking with twin holographic dancing clones, audio-reactive floor laser rings, futuristic club visualizer.",
        "primary_trigger": "FullBody Movement / HeadTilt (Audio waveform visor)",
        "tag_pool": ["dance", "fullbody", "rave", "music", "audioreactive", "neon"]
    },
    "3": {
        "channel": "WarpShock_Comedy",
        "genre": "Viral Meme & Cognitive Dissonance",
        "theme_focus": "Hyper-expressive melodrama morph (crying/grief dissonance), fluid 3D tears geyser on mouth open, comic raincloud.",
        "primary_trigger": "MouthOpen (Gushing cartoon tears) / Smile (Dramatic lightning zoom)",
        "tag_pool": ["meme", "crying", "funny", "drama", "morph", "prank"]
    },
    "4": {
        "channel": "Lumiere_Atelier",
        "genre": "35mm Analog Luxury & High-Fashion",
        "theme_focus": "Kodak Portra 400 35mm film aesthetic, authentic red halation, 24k sculpted gold leaf headprop, warm golden hour sun flare.",
        "primary_trigger": "Smile (Prism caustic light burst across cheekbones)",
        "tag_pool": ["film", "35mm", "portra400", "beauty", "luxury", "aesthetic"]
    },
    "5": {
        "channel": "Chrono_Mirage",
        "genre": "Surrealism & Zero-G Liquid Chrome",
        "theme_focus": "Avant-garde liquid mercury halo crown morphing in zero gravity, ray-traced chrome reflections, infinite mirror portal background.",
        "primary_trigger": "Smile (Infinite kaleidoscopic mirror portal) / BrowRaise (Orbiting chrome spheres)",
        "tag_pool": ["surreal", "chrome", "optical", "cyber", "art", "mirage"]
    }
}


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
        "4. MANDATORY: Exact physical anchoring (perched securely on outer shoulder, wrapped around collarbone, or fitted crown headprop).\n"
        "5. MANDATORY: Explicit face triggers (opening mouth triggers breath/vfx; smiling triggers bloom/flare; raising eyebrows charges aura).\n"
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
    if custom_instructions:
        user_prompt += f"Special User Direction: {custom_instructions}\n"

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
            "maxOutputTokens": 1000
        }
    }

    last_err = None
    for model_name in CANDIDATE_MODELS:
        for key in api_keys[:5]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            try:
                print(f"[GEMINI] Trying model {model_name} with key {key[:6]}... for Account #{account_id}")
                res = requests.post(url, json=payload, timeout=25)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    result = json.loads(raw_text)

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
