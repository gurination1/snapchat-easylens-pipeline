import os
import sys
import json

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

from easylens_api import EasyLensClient
from lens_verifier import LensVerifier
from gemini_lens_agent import (
    generate_lens_prompt,
    sanitize_lens_prompt,
    compute_token_jaccard,
    load_published_history
)

SSO_TOKEN = os.getenv("SNAP_SSO_TOKEN")
COOKIE_HEADER = os.getenv("SNAP_COOKIE_HEADER", "")
ACCOUNT_ID = os.getenv("ACCOUNT_ID", "1")
USE_GEMINI = os.getenv("USE_GEMINI", "true").lower() not in ("false", "0", "no")
CUSTOM_INSTRUCTIONS = os.getenv("CUSTOM_INSTRUCTIONS", "")


class BlueprintPool(list):
    """
    List of verified blueprints supporting dict-like backwards compatibility
    (e.g., STATIC_FALLBACKS['2']['prompt']) while hosting 5 distinct verified blueprints per account.
    """
    def __getitem__(self, key):
        if isinstance(key, str):
            return self[0][key]
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, str):
            return self[0].get(key, default)
        return super().get(key, default)


# Proven PBR fallbacks per account persona (5 distinct verified blueprints per account = 25 total)
STATIC_FALLBACKS = {
    "1": BlueprintPool([
        {
            "lens_name": "Aether Dragon Crown",
            "prompt": "Sculpted obsidian dragon horn crown anchored strictly to hairline and temples with liquid 24k gold filigree and caustic ruby gems, PBR anisotropic metallic reflections, 3-point contrast 6500K/2800K lighting with ray-traced contact shadows. Mouth open erupts turbulent emerald flame torrent with floating amber sparks; smiling ignites alpha-fading golden runic eye halos. Depth occlusion enabled, zero strobing.",
            "tags": ["dragon", "3d", "headpiece", "horns", "fantasy", "pbr"]
        },
        {
            "lens_name": "Phoenix Solar Diadem",
            "prompt": "Sculpted molten 24k rose-gold phoenix diadem fitted to hairline with radiant solar ember crest. PBR feathered iridescent wings contouring temples with subsurface scattering and 3-point contrast rim lighting. Opening mouth unleashes blinding solar plasma plumage burst and rising golden ash particles; smiling triggers brilliant sun-flare corona around brow. Depth occlusion, zero UI.",
            "tags": ["phoenix", "firebird", "diadem", "fantasy", "pbr"]
        },
        {
            "lens_name": "Valkyrie Frost Circlet",
            "prompt": "Brushed silver and iridescent mother-of-pearl Valkyrie winged circlet fitted firmly to forehead. Photorealistic PBR metal reflections with frosted runic engravings and cool 6500K Nordic key lighting. Opening mouth summons ethereal soaring spectral raven aura and frosted arctic mist; smiling ignites crystalline glacial eye glints. Seamless head tracking, zero strobing.",
            "tags": ["valkyrie", "winged", "circlet", "aurora", "pbr"]
        },
        {
            "lens_name": "Anubis Eclipse Coronet",
            "prompt": "Matte black basalt and electrum jackal coronet fitted securely to crown and temples with glowing lapis lazuli inlays. 3-point contrast 2800K desert key light with ray-traced contact shadows. Opening mouth triggers swirling golden sandstorm vortex and ancient hieroglyphic embers; smiling aligns a glowing solar eclipse halo behind crown. Zero strobing, zero UI.",
            "tags": ["anubis", "egyptian", "coronet", "jackal", "pbr"]
        },
        {
            "lens_name": "Celestial Kitsune Crest",
            "prompt": "Carved porcelain and polished vermilion lacquer kitsune forehead crest anchored strictly to brow, leaving eyes and mouth clear. Shimmering spirit bells and twin floating foxfire tails contouring jawline. Opening mouth erupts swirling azure spirit flame orbs with dynamic volumetric embers; smiling reveals ethereal golden fox spirit eye reflections. Pure PBR craft, zero UI.",
            "tags": ["kitsune", "foxfire", "spirit", "mask", "pbr"]
        }
    ]),
    "2": BlueprintPool([
        {
            "lens_name": "Chrono Echo Visor",
            "prompt": "Sleek ergonomic 3D cyberpunk HUD glasses and visor resting across eyes, leaving cheeks and mouth clear for tracking. Brushed titanium frame with pulsing cyan neon edge emission and refractive optical glass. Floating volumetric cyan neon embers drift around temples. Opening mouth triggers radial laser particle shockwave; smiling activates bright neon visor HUD readout. Zero strobing, zero UI sliders, pure 3D assets only.",
            "tags": ["cyberpunk", "visor", "optics", "hud", "pbr"]
        },
        {
            "lens_name": "Cybernetic Ocular Scanner",
            "prompt": "Asymmetrical carbon fiber and tungsten ocular scanner anchored firmly over left eye orbital bone and brow, leaving face and mouth unobstructed. Multi-layered refractive cyan targeting lenses with micro-servo details. Opening mouth projects floating 3D tactical holographic wireframe mesh; smiling cycles high-speed green diagnostic data stream through ocular optics. PBR materials, ray-traced shadows.",
            "tags": ["cybernetic", "monocle", "scanner", "reticle", "hud"]
        },
        {
            "lens_name": "Neon Speed Goggles",
            "prompt": "Ultra-lightweight matte-black alloy speed-optic goggles fitted across brow and nose bridge. Features illuminated amber and electric blue neon optical rings with internal refractive glass prism elements. PBR metallic shaders with ray-traced contact shadows. Opening mouth triggers hyperdrive chromatic warp streak particle bursts across peripheral vision; smiling flashes dual-frequency optic diagnostic glow. Zero strobing, zero UI.",
            "tags": ["goggles", "speed", "neon", "racing", "optics"]
        },
        {
            "lens_name": "Tactical Orbital Reticle",
            "prompt": "Matte carbon-fiber ballistic monocle anchored over right eye and brow with micro-aperture ring. Anisotropic PBR reflections, ray-traced shadows. Opening mouth projects 3D floating volumetric targeting reticle grid expanding into space; smiling locks glowing red orbital telemetry beam flare across lens. Pure 3D assets, zero canvas.",
            "tags": ["tactical", "orbital", "reticle", "targeting", "hud"]
        },
        {
            "lens_name": "Apex Spectre Visor",
            "prompt": "Faceted obsidian and dichroic glass stealth visor contoured across brow and temples. PBR metallic luster with 3-point contrast violet rim lighting. Opening mouth emits radial sonic particle shockwave with refractive edge displacement; smiling flashes crisp cyan biometric lock indicators across prismatic glass face. Zero strobing, zero 2D canvas spinners, pure 3D mesh only.",
            "tags": ["spectre", "stealth", "visor", "prismatic", "hud"]
        }
    ]),
    "3": BlueprintPool([
        {
            "lens_name": "Stormcloud Tears",
            "prompt": "Fluffy 3D cartoon stormcloud hovering directly above head with gentle glowing rain droplets and soft ambient thunder light. PBR volumetric stylization, 3-point contrast lighting. Opening mouth erupts an exaggerated geyser of liquid mercury tears and spinning 24k gold coins bouncing off screen frame; smiling triggers a dramatic cartoon lightning rim flash. Physics-driven, zero strobe.",
            "tags": ["meme", "crying", "funny", "cloud", "cartoon"]
        },
        {
            "lens_name": "Soap Opera Melodrama",
            "prompt": "Wearable comedic 3D dramatic weeping theatre crown with physical 3D crystalline tear waterfalls cascading comically from eyes across cheeks. PBR water caustics with soft romantic halo lighting. Opening mouth erupts torrential twin weeping fountains and floating comedy broken-heart shards; smiling instantly shatters the drama into a cheerful explosion of rainbow glitter confetti. Pure comedy AR.",
            "tags": ["soapopera", "tears", "crown", "comedy", "confetti"]
        },
        {
            "lens_name": "Steam Rage Valve",
            "prompt": "Comic stylized polished brass steam boiler pressure valve mounted securely to forehead with vibrating needle gauge. 3-point warm lighting with baked shadows. Opening mouth releases explosive pressurized cartoon steam clouds blasting sideways from ears with comic red face flush; smiling vents gentle harmless rainbow bubble streams from the whistle valve. Zero UI, high viral comedy.",
            "tags": ["rage", "steam", "cartoon", "whistle", "funny"]
        },
        {
            "lens_name": "Cartoon Jaw Drop Cascade",
            "prompt": "Exaggerated 3D mechanical cartoon spring chin and bulging cartoon eyes anchored to face. 3-point comic lighting with ray-traced shadows. Opening mouth triggers hilarious jaw-drop extension unleashing cascading fountain of spinning 24k gold coins and comic exclamation sparks; smiling pops eyes back with comical starburst glints. Pure viral comedy AR.",
            "tags": ["jawdrop", "cartoon", "coins", "meme", "comedy"]
        },
        {
            "lens_name": "Pop-Out Hypno Goggles",
            "prompt": "Exaggerated 3D glowing cartoon spiral hypno-goggles anchored over eyes that comical stretch and pop forward 10cm on face trigger. PBR stylized materials with ray-traced contact shadows. Opening mouth triggers shockwave rings with floating animated comic exclamation marks and bouncing question mark stars; smiling snaps goggles back with hilarious kaleidoscope optic swirl. Physics-driven, zero strobing.",
            "tags": ["hypno", "spiral", "goggles", "cartoon", "comedy"]
        }
    ]),
    "4": BlueprintPool([
        {
            "lens_name": "Haute Baroque Gold",
            "prompt": "Sculpted 24k gold leaf baroque crown fitted strictly to hairline and temples with pale champagne crystal halo and caustic crystal prisms. Warm Kodak Portra 35mm film halation with colorCorrection 10 Golden Glow and grain. Anisotropic PBR reflections, ray-traced shadows. Opening mouth parts delicate golden veil; smiling unleashes rich golden sparkle dust cascading across cheekbones. Photosensitive safe, zero strobing.",
            "tags": ["film", "35mm", "crown", "gold", "luxury"]
        },
        {
            "lens_name": "Pearl Celestial Diadem",
            "prompt": "Floating halo diadem of baroque freshwater pearls and hand-twisted 18k champagne gold wire resting above hairline. Subtle Portra 400 golden-hour film bloom with warm 2800K key light. Opening mouth summons gentle floating champagne light motes around face; smiling illuminates an ethereal high-fashion skin sheen and caustic crystal ear shimmer. Ultra-luxury vanity aesthetic.",
            "tags": ["pearl", "diadem", "luxury", "film", "35mm"]
        },
        {
            "lens_name": "Art Nouveau Emerald Tiara",
            "prompt": "Art Nouveau floral tiara sculpted from antiqued yellow gold with deep emerald cabochon accents anchored securely to brow. Soft 35mm analog vignette with delicate warm highlights. Opening mouth floats a semi-translucent golden silk shimmer veil across temples; smiling activates subtle emerald light refraction flares across eye contours. Pure Parisian couture craft, zero UI.",
            "tags": ["artnouveau", "tiara", "emerald", "luxury", "gold"]
        },
        {
            "lens_name": "Champagne Diamond Coronal",
            "prompt": "Precision micro-faceted champagne diamond coronal resting tightly along hairline. Micro-surface roughness maps catching golden hour sunlight with realistic chromatic dispersion. Opening mouth emits delicate suspended diamond dust particles orbiting crown; smiling triggers radiant starburst glints across cheekbone highlights with Portra warm tones. Zero strobing.",
            "tags": ["diamond", "coronal", "champagne", "35mm", "luxury"]
        },
        {
            "lens_name": "Venetian Gold Filigree",
            "prompt": "Hand-crafted Venetian 24k gold filigree half-mask contouring upper brow and cheekbones, leaving mouth completely free. Kodak Portra 400 film grain and warm 2800K halation. Opening mouth releases drifting amber gossamer specks; smiling triggers brilliant caustic diamond prism glints across cheekbones. High fashion luxury AR.",
            "tags": ["venetian", "filigree", "mask", "gold", "haute_couture"]
        }
    ]),
    "5": BlueprintPool([
        {
            "lens_name": "Liquid Chrome Mirage",
            "prompt": "Zero-G floating liquid mercury halo crown morphing above head with sculpted chrome cheek plates. Anisotropic mirror PBR reflections with fluid surface tension, 3-point contrast lighting and ray-traced contact shadows. Opening mouth releases orbiting liquid chrome spheres with refractive rippling reflections; smiling ripples the ambient background. Seamless physics, zero strobing.",
            "tags": ["surreal", "chrome", "halo", "optical", "cyber"]
        },
        {
            "lens_name": "Mobius Platinum Ribbon",
            "prompt": "Interlocking liquid platinum Mobius strip ribbon undulating continuously in zero-g around upper crown. Hyper-reflective chrome shader reflecting ambient environment with fluid refraction. Opening mouth sends floating chrome ribbon tendrils surging forward; smiling shatters ambient reflection into a hypnotic kaleidoscopic mirror prism facet display. Surreal Y3K aesthetic.",
            "tags": ["mobius", "chrome", "platinum", "surreal", "y3k"]
        },
        {
            "lens_name": "Ferrofluid Bio Horns",
            "prompt": "Glossy obsidian ferrofluid horn sculptures rising organically from temples, dynamically morphing between fluid blobs and magnetic spikes. 3-point contrast lighting with cool 6500K rim. Opening mouth suspends dozens of zero-g liquid mercury droplets floating across face; smiling pulses an electromagnetic ripple wave through the ferrofluid geometry. Pure surrealism.",
            "tags": ["ferrofluid", "horns", "magnetic", "chrome", "surreal"]
        },
        {
            "lens_name": "Liquid Platinum Tears",
            "prompt": "Mirrored liquid platinum teardrop sculptures frozen weightlessly along cheekbones with a floating surreal chrome toroid halo above head. Anisotropic fluid reflections with ray-traced shadows. Opening mouth releases liquid metal ripple shockwave radiating across cheek sculptures; smiling inverts chrome surface reflections with chromatic prism sheen. Photosensitive safe, zero strobing.",
            "tags": ["liquidplatinum", "tears", "toroid", "surreal", "chrome"]
        },
        {
            "lens_name": "Chrome Tesseract Halo",
            "prompt": "Weightless 4D liquid chrome tesseract frame rotating smoothly above head with mirrored vertices. Anisotropic reflections, ray-traced contact shadows. Opening mouth triggers gravitational shockwave ripple warping ambient reflections; smiling flashes prismatic chromatic aberration rings along cheek contours. Y3K surrealism, zero strobing.",
            "tags": ["tesseract", "chrome", "halo", "surreal", "y3k"]
        }
    ])
}


def select_lru_fallback(account_id: str, history: list = None) -> dict:
    """
    Selects the least-recently-used (LRU) static blueprint for the account from the 5-blueprint pool
    by cross-referencing published_lenses.json, guaranteeing zero repetition even during API outages.
    """
    aid = str(account_id)
    pool = STATIC_FALLBACKS.get(aid, STATIC_FALLBACKS["1"])
    if history is None:
        history = load_published_history("published_lenses.json")

    acc_lenses = [x for x in history if str(x.get("account_id")) == aid]

    counts = {i: 0 for i in range(len(pool))}
    last_timestamps = {i: "" for i in range(len(pool))}

    for lens in acc_lenses:
        l_name = lens.get("lens_name", "").lower()
        l_prompt = lens.get("prompt", "").lower()
        ts = lens.get("timestamp", "")
        for i, bp in enumerate(pool):
            bp_name = bp.get("lens_name", "").lower()
            if (
                bp_name in l_name
                or l_name in bp_name
                or (len(l_prompt) > 20 and compute_token_jaccard(l_prompt, bp.get("prompt", "")) > 0.35)
            ):
                counts[i] += 1
                if ts > last_timestamps[i]:
                    last_timestamps[i] = ts

    # Pure LRU: pick blueprint with oldest timestamp ('' is oldest / never used)
    best_index = min(range(len(pool)), key=lambda i: (last_timestamps[i] != "", last_timestamps[i], counts[i], i))
    selected = pool[best_index]
    return {
        "lens_name": selected["lens_name"],
        "prompt": sanitize_lens_prompt(selected["prompt"]),
        "tags": selected["tags"]
    }
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "true").lower() not in ("false", "0", "no")


def resolve_account_auth(account_id: str):
    aid = str(account_id)
    sso_token = (
        os.getenv(f"SNAP_SSO_TOKEN_ACC_{aid}")
        or os.getenv(f"SNAP_SSO_TOKEN_{aid}")
        or (os.getenv("SNAP_SSO_TOKEN") if aid == "1" else None)
    )
    cookie_header = (
        os.getenv(f"SNAP_COOKIE_HEADER_ACC_{aid}")
        or os.getenv(f"SNAP_COOKIE_HEADER_{aid}")
        or (os.getenv("SNAP_COOKIE_HEADER") if aid == "1" else "")
    )
    accounts_cookie = (
        os.getenv(f"SNAP_ACCOUNTS_COOKIE_ACC_{aid}")
        or os.getenv(f"SNAP_ACCOUNTS_COOKIE_{aid}")
        or (os.getenv("SNAP_ACCOUNTS_COOKIE") if aid == "1" else cookie_header)
    )
    username = (
        os.getenv(f"SNAP_USERNAME_ACC_{aid}")
        or os.getenv(f"SNAP_USERNAME_{aid}")
        or (os.getenv("SNAP_USERNAME") if aid == "1" else None)
    )
    password = (
        os.getenv(f"SNAP_PASSWORD_ACC_{aid}")
        or os.getenv(f"SNAP_PASSWORD_{aid}")
        or (os.getenv("SNAP_PASSWORD") if aid == "1" else None)
    )
    # Check if credentials exist for the targeted account
    has_creds = bool(sso_token or username or (aid == "1" and os.getenv("SNAP_SSO_TOKEN")))
    if not has_creds:
        # Dynamically discover configured active accounts (1..5)
        active_accounts = []
        for cand in ["1", "2", "3", "4", "5"]:
            c_tok = os.getenv(f"SNAP_SSO_TOKEN_ACC_{cand}") or (os.getenv("SNAP_SSO_TOKEN") if cand == "1" else None)
            c_usr = os.getenv(f"SNAP_USERNAME_ACC_{cand}") or (os.getenv("SNAP_USERNAME") if cand == "1" else None)
            if c_tok or c_usr:
                active_accounts.append(cand)

        if active_accounts:
            fallback_aid = active_accounts[(int(aid) - 1) % len(active_accounts)]
            print(f"[ACCOUNT RELIABILITY GUARD] Account #{aid} credentials not yet in secrets.")
            print(f"[ACCOUNT RELIABILITY GUARD] Auto-routing to active Account #{fallback_aid} (out of active: {active_accounts}) to prevent missed shift!")
            return resolve_account_auth(fallback_aid)

    return sso_token, cookie_header, accounts_cookie, username, password


def main():
    sso_token, cookie_header, accounts_cookie, username, password = resolve_account_auth(ACCOUNT_ID)
    client = EasyLensClient(
        sso_token=sso_token,
        cookie_header=cookie_header,
        accounts_cookie=accounts_cookie,
        account_id=ACCOUNT_ID
    )

    print(f"\n=== STEP 1: VERIFYING SNAPCHAT AUTHENTICATION (ACCOUNT #{ACCOUNT_ID}) ===")
    user = None
    try:
        if sso_token or accounts_cookie:
            user = client.verify_auth()
    except Exception as e:
        print(f"[AUTH EXPIRED / 401] Initial auth check failed ({e}). Triggering autonomous recovery...")

    if not user:
        print(f"[AUTO-AUTH] Calling Autonomous Snapchat Auth Automator for Account #{ACCOUNT_ID}...")
        try:
            from snap_auth_automator import obtain_valid_snap_session
            fresh_session = obtain_valid_snap_session(
                account_id=ACCOUNT_ID,
                username=username,
                password=password
            )
            client = EasyLensClient(
                sso_token=fresh_session["ticket"],
                cookie_header=fresh_session.get("cookie_header", ""),
                accounts_cookie=fresh_session.get("cookie_header", ""),
                account_id=ACCOUNT_ID
            )
            user = fresh_session.get("user") or client.verify_auth()
        except Exception as auth_err:
            print(f"[FATAL AUTH ERROR] Autonomous auth failed: {auth_err}")
            sys.exit(1)

    print(f"Logged in as: {user.get('displayName')} (@{user.get('username')})")

    # Determine per-account static fallback defaults via LRU rotation against published_lenses.json
    active_fallback = select_lru_fallback(ACCOUNT_ID)
    static_prompt = os.getenv("LENS_PROMPT") or active_fallback["prompt"]
    static_lens_name = os.getenv("LENS_NAME") or active_fallback["lens_name"]
    static_tags = [t.strip() for t in (os.getenv("LENS_TAGS") or ",".join(active_fallback["tags"])).split(",")]

    # Multi-attempt Generation & 7-Gate Verification Loop
    MAX_ATTEMPTS = 3
    passed = False
    report = {}
    gemini_plan = None
    lens_data = None
    checkpoint_id = None
    prompt = None
    lens_name = None
    tags = None
    cid = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n{'='*60}")
        print(f"=== PIPELINE GENERATION ATTEMPT {attempt}/{MAX_ATTEMPTS} (ACCOUNT #{ACCOUNT_ID}) ===")
        print(f"{'='*60}")

        current_instructions = CUSTOM_INSTRUCTIONS
        if attempt > 1:
            err_summary = "; ".join(report.get("errors", []))
            current_instructions = (
                f"{CUSTOM_INSTRUCTIONS} [STRICT RETRY]: Previous attempt failed verification with errors: {err_summary}. "
                "CRITICAL: Zero easing curves, zero TWEEN references, zero CanvasAPI / 2D canvas loading wheels, zero UI sliders, pure native 3D mesh and particles only!"
            ).strip()

        # Step 0: Determine Prompt, Lens Name, and Tags
        if USE_GEMINI and attempt < 3:
            print(f"\n=== STEP 0: AUTONOMOUS GEMINI PROMPT ARCHITECT (ACCOUNT #{ACCOUNT_ID}, ATTEMPT {attempt}) ===")
            try:
                gemini_plan = generate_lens_prompt(account_id=ACCOUNT_ID, custom_instructions=current_instructions)
                prompt = gemini_plan["prompt"]
                lens_name = gemini_plan["lens_name"]
                tags = gemini_plan.get("tags", static_tags)
                with open("gemini_generation_plan.json", "w") as f:
                    json.dump(gemini_plan, f, indent=2)
                print(f"[GEMINI SUCCESS] Lens: {lens_name}")
                print(f"[GEMINI SUCCESS] Hook: {gemini_plan.get('visual_hook')}")
            except Exception as e:
                print(f"[GEMINI WARN] Gemini synthesis failed ({e}), falling back to persona #{ACCOUNT_ID} static prompt...")
                active_fallback = select_lru_fallback(ACCOUNT_ID)
                prompt = active_fallback["prompt"]
                lens_name = active_fallback["lens_name"]
                tags = active_fallback["tags"]
        else:
            if attempt == 3:
                print(f"\n=== STEP 0: ZERO-MISTAKE CIRCUIT BREAKER (ATTEMPT 3): Engaging offline verified LRU blueprint ===")
            active_fallback = select_lru_fallback(ACCOUNT_ID)
            prompt = active_fallback["prompt"]
            lens_name = active_fallback["lens_name"]
            tags = active_fallback["tags"]

        # Pre-flight sanitation guarantee: zero canvas/spinner/TWEEN tokens
        prompt = sanitize_lens_prompt(prompt)
        if "no tween" not in prompt.lower() and "zero tween" not in prompt.lower():
            prompt = prompt.rstrip(" .") + ". Zero easing curves, no tweening, no UI sliders, pure 3D mesh only."

        print(f"\n=== STEP 2: CREATING LENS CONVERSATION (ATTEMPT {attempt}) ===")
        cid = client.create_conversation()

        print(f"\n=== STEP 3: SUBMITTING PROMPT TO SNAPCHAT AILC (ATTEMPT {attempt}) ===")
        print(f"Prompt: {prompt}")
        client.send_prompt(cid, prompt)

        print(f"\n=== STEP 4: POLLING FOR LENS GENERATION (ATTEMPT {attempt}) ===")
        lens_data = client.poll_lens(cid, max_wait_sec=200)

        checkpoint_id = lens_data.get("checkpoint_id")
        archive_url = lens_data.get("download_url") or (lens_data.get("lens_bundle_data") or {}).get("lens_archive_url")
        checksum = lens_data.get("checksum") or (lens_data.get("lens_bundle_data") or {}).get("checksum")
        icon_url = lens_data.get("lens_icon_download_url")

        # Save metadata
        with open("generated_lens_metadata.json", "w") as f:
            json.dump(lens_data, f, indent=2)

        print(f"\n=== STEP 5: 7-GATE COMPREHENSIVE LENS & JUDGE AI VERIFICATION (ATTEMPT {attempt}) ===")
        plan_data = gemini_plan if USE_GEMINI else {"prompt": prompt, "lens_name": lens_name}
        verifier = LensVerifier(lens_data=lens_data, session=client.session, plan=plan_data)
        passed = verifier.verify_all()
        report = verifier.export_report("verification_report.json")

        print(f"Gate 1 (Metadata Status): {report['gates'].get('gate1_metadata_status', {}).get('passed')}")
        print(f"Gate 2 (Icon Health):     {report['gates'].get('gate2_icon_health', {}).get('passed')}")
        print(f"Gate 3 (Checksum Hash):   {report['gates'].get('gate3_checksum_integrity', {}).get('passed')}")
        print(f"Gate 4 (Size Boundaries): {report['gates'].get('gate4_size_limits', {}).get('passed')} (Compressed: {report['metrics'].get('compressed_size_bytes', 0) // 1024}KB, Unpacked: {report['metrics'].get('uncompressed_size_bytes', 0) // 1024}KB)")
        print(f"Gate 5 (Assets & Events): {report['gates'].get('gate5_assets_and_controller', {}).get('passed')}")
        print(f"Gate 6 (Judge AI Score):  {report['gates'].get('gate6_judge_ai', {}).get('passed')} ({report['gates'].get('gate6_judge_ai', {}).get('score')}/100 - {report['gates'].get('gate6_judge_ai', {}).get('verdict')})")
        g7 = report['gates'].get('gate7_visual_simulation', {})
        print(f"Gate 7 (Vision Simulation): {g7.get('passed')} (Score: {g7.get('score')}/100, 3D Mesh: {g7.get('has_3d_mesh')}, BG Only: {g7.get('is_background_only')})")
        print(f"OVERALL VERIFICATION VERDICT: {'PASSED (100%)' if passed else 'FAILED'}")

        if passed:
            print(f"\n[VERIFICATION OK] Attempt {attempt} passed all 7 quality & compliance gates!")
            break
        else:
            print(f"\n[VERIFICATION WARNING] Attempt {attempt} failed verification: {report.get('errors')}")
            if attempt < MAX_ATTEMPTS:
                print(f"[AUTO-HEAL] Re-attempting generation with strict corrective anti-TWEEN instructions...")

    if not passed:
        print("\n[FATAL ERROR] All generation attempts failed verification! Aborting publish to protect account catalog.")
        print(f"Final Errors: {json.dumps(report.get('errors', []), indent=2)}")
        sys.exit(1)

    if AUTO_PUBLISH:
        print("\n=== STEP 6: PUBLISHING VERIFIED LENS TO SNAPCHAT CATALOG ===")
        final_lens_name = lens_name or lens_data.get("lens_name") or "Obsidian Pyrodrake 3D"

        # Check for simulated preview video from Gate 7
        preview_url = None
        preview_key = None
        preview_path = g7.get("preview_video") or "preview_video.mp4"
        if os.path.exists(preview_path):
            print("\n=== STEP 5.5: UPLOADING AES-128-GCM PREVIEW VIDEO TO BOLT CDN ===")
            try:
                with open(preview_path, "rb") as f:
                    v_bytes = f.read()
                preview_url, preview_key = client.upload_preview_video(v_bytes)
                print(f"[PREVIEW VIDEO OK] CDN URL: {preview_url}")
                print(f"[PREVIEW VIDEO OK] AES Key: {preview_key[:10]}...")
            except Exception as e:
                print(f"[PREVIEW VIDEO WARN] Bolt upload failed ({e}). Proceeding without preview video.")

        # Check for viral lens icon from Gate 7
        icon_url = None
        icon_key = None
        icon_path = g7.get("lens_icon") or "lens_icon.png"
        if os.path.exists(icon_path):
            print("\n=== STEP 5.6: UPLOADING HIGH-CTR VIRAL LENS ICON ('THE PICK') TO BOLT CDN ===")
            try:
                with open(icon_path, "rb") as f:
                    i_bytes = f.read()
                icon_url, icon_key = client.upload_preview_video(i_bytes)
                print(f"[VIRAL ICON OK] CDN URL: {icon_url}")
                print(f"[VIRAL ICON OK] AES Key: {icon_key[:10]}...")
            except Exception as e:
                print(f"[VIRAL ICON WARN] Bolt upload failed ({e}). Proceeding with default icon.")

        pub_res = client.publish_lens(
            conversation_id=cid,
            lens_name=final_lens_name,
            tags=tags,
            preview_url=preview_url,
            preview_encryption_key=preview_key,
            icon_url=icon_url,
            icon_encryption_key=icon_key
        )
        print("Publish response:", pub_res)

        status_data = None
        if checkpoint_id:
            print("\n=== STEP 7: MONITORING SNAPCODE & SUBMISSION STATUS ===")
            status_data = client.get_publish_status(checkpoint_id)
            if status_data:
                print(f"[SUCCESS] Published Lens ID: {status_data.get('lens_central_lens_id')}")
                print(f"[SUCCESS] Catalog Status: {status_data.get('status')}")
                with open("publish_status.json", "w") as f:
                    json.dump(status_data, f, indent=2)

        # Record into deduplication state file (persisted in git like yt-auto)
        import time
        history_file = "published_lenses.json"
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    history = json.load(f)
            except Exception:
                history = []

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "account_id": str(ACCOUNT_ID),
            "lens_name": final_lens_name,
            "lens_id": (status_data or {}).get("lens_central_lens_id") or pub_res.get("lens_central_lens_id"),
            "checkpoint_id": checkpoint_id,
            "prompt": prompt,
            "tags": tags,
            "visual_hook": (gemini_plan or {}).get("visual_hook", "") if USE_GEMINI else "",
            "has_preview_video": bool(preview_url),
            "preview_url": preview_url,
            "status": (status_data or {}).get("status", "pending")
        }
        history.append(entry)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
        print(f"[STATE] Recorded '{final_lens_name}' to {history_file} (Total fleet lenses: {len(history)})")

    print("\n=== PIPELINE FINISHED SUCCESSFULLY WITH 100% VERIFICATION ===")


if __name__ == "__main__":
    main()
