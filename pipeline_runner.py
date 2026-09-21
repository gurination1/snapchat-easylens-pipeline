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
ACCOUNT_ID = str(os.getenv("ACCOUNT_ID", "1"))
if ACCOUNT_ID not in ("1", "2", "3", "4", "5"):
    raise ValueError(f"Invalid ACCOUNT_ID '{ACCOUNT_ID}'. Snapchat fleet strictly enforces Accounts 1, 2, 3, 4, 5.")
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
            "lens_name": "Ghibli Watercolor Cloud Crown",
            "prompt": "Hand-painted Ghibli watercolor cumulus cloud crown resting above hairline with floating soot spirit dust and celestial spirit serpent coils. Soft cel-shaded gouache textures with warm 2800K sunlight ray-traced highlights. Opening mouth erupts swirling sakura petal cyclone; smiling spawns cheerful soot sprites around temples; head tilt shifts floating spirit dust. Pure 3D PBR fantasy, zero strobing, zero UI.",
            "tags": ["ghibli", "watercolor", "anime", "clouds", "spirit", "pbr"]
        },
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
            "prompt": "Brushed silver and iridescent mother-of-pearl Valkyrie winged circlet fitted firmly to forehead. Photorealistic PBR metal reflections with frosted runic engravings and cool 6500K Nordic key lighting. Opening mouth summons ethereal soaring spectral raven aura; smiling ignites crystalline glacial eye glints. Seamless head tracking, zero strobing.",
            "tags": ["valkyrie", "winged", "circlet", "aurora", "pbr"]
        },
        {
            "lens_name": "Celestial Kitsune Crest",
            "prompt": "Carved porcelain and polished vermilion lacquer kitsune forehead crest anchored strictly to brow, leaving eyes and mouth clear. Shimmering spirit bells and twin floating foxfire tails contouring jawline. Opening mouth erupts swirling azure spirit flame orbs with dynamic volumetric embers; smiling reveals ethereal golden fox spirit eye reflections. Pure PBR craft, zero UI.",
            "tags": ["kitsune", "foxfire", "spirit", "crest", "pbr"]
        }
    ]),
    "2": BlueprintPool([
        {
            "lens_name": "90s Cyber Camcorder Visor",
            "prompt": "Retro-futuristic 90s cyber camcorder visor frame contoured across brow and temples with holographic rec timestamp and magnetic phosphor glass. PBR brushed titanium, cathode-ray scanline reflections. Opening mouth discharges magnetic tape-rip glitch shockwave and RGB chromatic particle split; smiling pulses neon REC battery flare; head tilt shifts scanlines. Zero strobing, pure 3D AR craft, zero UI.",
            "tags": ["camcorder", "vhs", "glitch", "cyberpunk", "visor", "pbr"]
        },
        {
            "lens_name": "Chrono Echo Visor",
            "prompt": "Sleek ergonomic 3D cyberpunk glasses and visor resting across eyes, leaving cheeks and mouth clear for tracking. Brushed titanium frame with pulsing cyan neon edge emission and refractive optical glass. Floating volumetric cyan neon embers drift around temples. Opening mouth triggers radial laser particle shockwave; smiling illuminates glowing neon visor frame rim. Zero strobing, zero text, zero UI sliders, pure 3D assets only.",
            "tags": ["cyberpunk", "visor", "optics", "hud", "pbr"]
        },
        {
            "lens_name": "Cybernetic Ocular Scanner",
            "prompt": "Asymmetrical carbon fiber and tungsten ocular optic anchored over left eye orbital bone and brow, leaving face and mouth unobstructed. Multi-layered refractive cyan glass lenses with micro-servo details. Opening mouth projects floating 3D wireframe mesh orb; smiling pulses glowing emerald light through ocular lenses. PBR materials, ray-traced shadows, zero text.",
            "tags": ["cybernetic", "monocle", "scanner", "reticle", "hud"]
        },
        {
            "lens_name": "Neon Speed Goggles",
            "prompt": "Ultra-lightweight matte-black alloy speed-optic goggles fitted across brow and nose bridge. Features illuminated amber and electric blue neon optical rings with internal refractive glass prism elements. PBR metallic shaders with ray-traced contact shadows. Opening mouth triggers hyperdrive chromatic warp streak particle bursts across peripheral vision; smiling pulses warm amber glow across goggles frame. Zero strobing, zero text, zero UI.",
            "tags": ["goggles", "speed", "neon", "racing", "optics"]
        },
        {
            "lens_name": "Apex Spectre Visor",
            "prompt": "Faceted obsidian and dichroic glass stealth visor contoured across brow and temples. PBR metallic luster with 3-point contrast violet rim lighting. Opening mouth emits radial sonic particle shockwave with refractive edge displacement; smiling pulses brilliant violet prism reflections across glass face. Zero strobing, zero 2D canvas spinners, zero screen text, pure 3D mesh only.",
            "tags": ["spectre", "stealth", "visor", "prismatic", "hud"]
        }
    ]),
    "3": BlueprintPool([
        {
            "lens_name": "Viral Karaoke Lyric Headpiece",
            "prompt": "Pulsing 3D neon musical staff headpiece contoured around brow with orbiting treble clef notes and bouncing rhythm sphere balls. PBR emissive neon shaders with 3-point contrast lighting. Opening mouth unleashes explosive pulsing neon musical note shockwave and basswave rings; smiling makes rhythm spheres bounce in tempo across brow; head tilt sways musical staff. High virality, zero UI.",
            "tags": ["karaoke", "lyrics", "neon", "music", "meme", "viral"]
        },
        {
            "lens_name": "Stormcloud Tears",
            "prompt": "Fluffy 3D cartoon stormcloud hovering directly above head with gentle glowing rain droplets and soft ambient thunder light. PBR volumetric stylization, 3-point contrast lighting. Opening mouth erupts an exaggerated geyser of liquid mercury tears and spinning 24k gold coins bouncing off screen frame; smiling triggers a dramatic cartoon lightning rim flash. Physics-driven, zero strobe.",
            "tags": ["meme", "crying", "funny", "cloud", "cartoon"]
        },
        {
            "lens_name": "Soap Opera Melodrama Tears",
            "prompt": "Wearable comedic 3D dramatic weeping theatre crown with physical crystalline tear waterfalls cascading comically from eyes across cheeks. PBR water caustics with soft romantic halo lighting. Opening mouth erupts torrential twin weeping waterfalls, broken-heart shards, and spinning 24k gold coin shower; smiling shatters drama into cheerful rainbow confetti; head tilt curves tear streams. Pure viral comedy AR.",
            "tags": ["soapopera", "tears", "melodrama", "brokenheart", "coins", "comedy"]
        },
        {
            "lens_name": "Steam Rage Valve",
            "prompt": "Comic stylized polished brass steam boiler pressure valve mounted securely to forehead with vibrating needle gauge. 3-point warm lighting with baked shadows. Opening mouth releases explosive pressurized cartoon steam clouds blasting sideways from ears with comic red face flush; smiling vents gentle harmless rainbow bubble streams from the whistle valve. Zero UI, high viral comedy.",
            "tags": ["rage", "steam", "cartoon", "whistle", "funny"]
        },
        {
            "lens_name": "Pop-Out Hypno Goggles",
            "prompt": "Exaggerated 3D glowing cartoon spiral hypno-goggles anchored over eyes that comical stretch and pop forward 10cm on face trigger. PBR stylized materials with ray-traced contact shadows. Opening mouth triggers shockwave rings with floating animated comic exclamation marks and bouncing question mark stars; smiling snaps goggles back with hilarious kaleidoscope optic swirl. Physics-driven, zero strobing.",
            "tags": ["hypno", "spiral", "goggles", "cartoon", "comedy"]
        }
    ]),
    "4": BlueprintPool([
        {
            "lens_name": "High-Fashion Parisian Couture",
            "prompt": "High-fashion Parisian couture 24k gold leaf baroque crown fitted to hairline with draped raw freshwater pearls and caustic crystal prisms. Warm Kodak Portra 400 film grain and analog halation bloom. Opening mouth triggers radiant champagne spark motes orbiting crown; smiling cascades radiant golden sparkle dust across cheekbones; head tilt catches prismatic diamond dispersion. Pure Parisian luxury, zero UI.",
            "tags": ["parisian", "couture", "goldleaf", "pearls", "portra400", "luxury"]
        },
        {
            "lens_name": "Haute Baroque Gold",
            "prompt": "Sculpted 24k gold leaf baroque crown fitted strictly to hairline and temples with pale champagne crystal halo and caustic crystal prisms. Warm Kodak Portra 35mm film halation with colorCorrection 10 Golden Glow and grain. Anisotropic PBR reflections, ray-traced shadows. Opening mouth triggers orbiting pale champagne diamond prisms; smiling unleashes rich golden sparkle dust cascading across cheekbones. Photosensitive safe, zero strobing.",
            "tags": ["film", "35mm", "crown", "gold", "luxury"]
        },
        {
            "lens_name": "Pearl Celestial Diadem",
            "prompt": "Floating halo diadem of baroque freshwater pearls and hand-twisted 18k champagne gold wire resting above hairline. Subtle Portra 400 golden-hour film bloom with warm 2800K key light. Opening mouth summons gentle floating champagne light motes around face; smiling illuminates an ethereal high-fashion skin sheen and caustic crystal ear shimmer. Ultra-luxury vanity aesthetic.",
            "tags": ["pearl", "diadem", "luxury", "film", "35mm"]
        },
        {
            "lens_name": "Art Nouveau Emerald Tiara",
            "prompt": "Art Nouveau floral tiara sculpted from antiqued yellow gold with deep emerald cabochon accents anchored securely to brow. Soft 35mm analog vignette with delicate warm highlights. Opening mouth pulses radiant emerald crystal prism halo above crown; smiling activates subtle emerald light refraction flares across eye contours. Pure Parisian couture craft, zero UI.",
            "tags": ["artnouveau", "tiara", "emerald", "luxury", "gold"]
        },
        {
            "lens_name": "Champagne Diamond Coronal",
            "prompt": "Precision micro-faceted champagne diamond coronal resting tightly along hairline. Micro-surface roughness maps catching golden hour sunlight with realistic chromatic dispersion. Opening mouth emits delicate suspended diamond dust particles orbiting crown; smiling triggers radiant starburst glints across cheekbone highlights with Portra warm tones. Zero strobing.",
            "tags": ["diamond", "coronal", "champagne", "35mm", "luxury"]
        }
    ]),
    "5": BlueprintPool([
        {
            "lens_name": "Y3K Liquid Mercury Halo",
            "prompt": "Weightless Y3K zero-G liquid mercury halo crown morphing above head with sculpted chrome cheekbone armor. Anisotropic mirror PBR reflections with fluid surface tension and ray-traced contact shadows. Opening mouth erupts orbiting refractive liquid chrome spheres into expanding toroidal shockwave; smiling triggers fluid ripple normal-map distortion across armor; head tilt shifts mercury droplets. Zero strobing, zero UI.",
            "tags": ["y3k", "liquidmercury", "chrome", "zerog", "surreal", "pbr"]
        },
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
        }
    ])
}


def select_lru_fallback(account_id: str, history: list = None) -> dict:
    """
    Selects the least-recently-used (LRU) static blueprint across ALL 25 verified blueprints
    from all 5 genres (Mythic, Cyber, Comedy, Luxury, Chrome), guaranteeing cross-genre rotation.
    """
    aid = str(account_id)
    if history is None:
        history = load_published_history("published_lenses.json")

    # Master pool of all 25 blueprints across all 5 genres
    all_blueprints = []
    for gid, b_pool in STATIC_FALLBACKS.items():
        for bp in b_pool:
            item = dict(bp)
            item["genre_id"] = gid
            all_blueprints.append(item)

    acc_lenses = [x for x in history if str(x.get("account_id")) == aid]
    last_genre = None
    if acc_lenses:
        last_name = acc_lenses[-1].get("lens_name", "").lower()
        for bp in all_blueprints:
            if bp["lens_name"].lower() in last_name:
                last_genre = bp["genre_id"]
                break

    candidates = [bp for bp in all_blueprints if bp["genre_id"] != last_genre] or all_blueprints

    def bp_score(bp):
        bp_name = bp["lens_name"].lower()
        count = sum(1 for x in history if bp_name in x.get("lens_name", "").lower())
        acc_count = sum(1 for x in acc_lenses if bp_name in x.get("lens_name", "").lower())
        last_ts = max([x.get("timestamp", "") for x in history if bp_name in x.get("lens_name", "").lower()] or [""])
        return (last_ts != "", last_ts, count, acc_count)

    selected = min(candidates, key=bp_score)
    return {
        "lens_name": selected["lens_name"],
        "prompt": sanitize_lens_prompt(selected["prompt"]),
        "tags": selected["tags"]
    }
AUTO_PUBLISH = os.getenv("AUTO_PUBLISH", "false").lower() in ("true", "1", "yes")


def resolve_account_auth(account_id: str):
    aid = str(account_id)
    if aid not in ("1", "2", "3", "4", "5"):
        raise ValueError(f"Invalid account ID '{aid}'. Fleet strictly enforces Accounts 1, 2, 3, 4, 5.")
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
        or os.getenv(f"SNAP_ACCOUNTS_COOKIE_ACC_{aid}")
        or (os.getenv("SNAP_ACCOUNTS_COOKIE") if aid == "1" else cookie_header)
    )
    account_default_users = {
        "1": "gman21478",
        "2": "gurination24@gmail.com",
        "3": "ehwtheh@gmail.com",
        "4": "galllgil049@gmail.com",
        "5": "ytnew5911@gmail.com"
    }
    username = (
        os.getenv(f"SNAP_USERNAME_ACC_{aid}")
        or os.getenv(f"SNAP_USERNAME_{aid}")
        or (os.getenv("SNAP_USERNAME") if aid == "1" else None)
        or account_default_users.get(aid)
    )
    password = (
        os.getenv(f"SNAP_PASSWORD_ACC_{aid}")
        or os.getenv(f"SNAP_PASSWORD_{aid}")
        or os.getenv("SNAP_PASSWORD", "")
    )
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
    from snap_auth_automator import is_user_matching_account
    try:
        if sso_token or accounts_cookie:
            user = client.verify_auth()
            if user and not is_user_matching_account(user, ACCOUNT_ID):
                print(f"[AUTH MISMATCH] Active session for Account #{ACCOUNT_ID} belongs to @{user.get('username')}, NOT Account #{ACCOUNT_ID}! Discarding.")
                user = None
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
            print(f"[AUTO-AUTH SUCCESS] Fresh session verified for Account #{ACCOUNT_ID}: {user.get('displayName')} (@{user.get('username')})")
        except Exception as auth_err:
            print(f"[FATAL AUTH ERROR] Autonomous auth failed: {auth_err}")
            sys.exit(1)

    print(f"Logged in as: {user.get('displayName')} (@{user.get('username')})")

    # Step 1B: Autonomous Snapchat Monetization & Payout Terms Approval
    if os.getenv("AUTO_APPROVE_MONETIZATION", "true").lower() in ("true", "1", "yes"):
        try:
            from approve_snap_monetization import approve_account_monetization
            m_res = approve_account_monetization(
                account_id=ACCOUNT_ID,
                cookie_str=getattr(client, "accounts_cookie", "") or getattr(client, "cookie_header", "") or (client.session.headers.get("Cookie", "") if hasattr(client, "session") else ""),
                ticket=client.sso_token,
                user=user
            )
            payout_ok = m_res.get("LENS_CREATOR_PAYOUT_TOS", False)
            ildg_ok = m_res.get("ILDG_TOS", False)
            print(f"[MONETIZATION STATUS] Account #{ACCOUNT_ID}: Payout TOS={payout_ok} | ILDG TOS={ildg_ok}")
        except Exception as m_err:
            print(f"[MONETIZATION CHECK WARN] Non-fatal monetization approval notice: {m_err}")

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

    failed_archetypes = []
    curr_archetype_id = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\n{'='*60}")
        print(f"=== PIPELINE GENERATION ATTEMPT {attempt}/{MAX_ATTEMPTS} (ACCOUNT #{ACCOUNT_ID}) ===")
        print(f"{'='*60}")

        current_instructions = CUSTOM_INSTRUCTIONS
        if attempt > 1:
            err_summary = "; ".join(report.get("errors", []))
            current_instructions = (
                f"{CUSTOM_INSTRUCTIONS} [STRICT RETRY]: Previous attempt failed verification with errors: {err_summary}. "
                "CRITICAL: Zero easing curves, zero TWEEN references, zero CanvasAPI / 2D canvas loading wheels, zero UI sliders, zero screen text, zero numbers, pure native 3D mesh and particles only!"
            ).strip()

        # Step 0: Determine Prompt, Lens Name, and Tags
        if USE_GEMINI and attempt < 3:
            print(f"\n=== STEP 0: AUTONOMOUS GEMINI PROMPT ARCHITECT (ACCOUNT #{ACCOUNT_ID}, ATTEMPT {attempt}) ===")
            try:
                gemini_plan = generate_lens_prompt(
                    account_id=ACCOUNT_ID,
                    custom_instructions=current_instructions,
                    exclude_archetypes=failed_archetypes
                )
                prompt = gemini_plan["prompt"]
                lens_name = gemini_plan["lens_name"]
                tags = gemini_plan.get("tags", static_tags)
                curr_archetype_id = gemini_plan.get("archetype")
                with open("gemini_generation_plan.json", "w") as f:
                    json.dump(gemini_plan, f, indent=2)
                print(f"[GEMINI SUCCESS] Lens: {lens_name} (Archetype: {curr_archetype_id})")
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
            if curr_archetype_id and curr_archetype_id not in failed_archetypes:
                failed_archetypes.append(curr_archetype_id)
            if attempt < MAX_ATTEMPTS:
                print(f"[AUTO-HEAL] Re-attempting generation with strict anti-UI/anti-TWEEN rules and rotating away from archetype '{curr_archetype_id}'...")

    if not passed:
        print("\n[FATAL ERROR] All generation attempts failed verification! Aborting publish to protect account catalog.")
        print(f"Final Errors: {json.dumps(report.get('errors', []), indent=2)}")
        sys.exit(1)

    if AUTO_PUBLISH:
        print("\n=== STEP 6: PUBLISHING VERIFIED LENS TO SNAPCHAT CATALOG ===")
        actual_lens_name = (lens_data.get("lens_name") or "").strip()
        final_lens_name = actual_lens_name if actual_lens_name else (lens_name or "Obsidian Pyrodrake 3D")
        print(f"[METADATA BINDING] Bound final_lens_name strictly to EasyLens 3D bundle: '{final_lens_name}'")

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

        # Check for high-impact preview image with full lens effect from Gate 7
        preview_img_url = None
        preview_img_key = None
        preview_img_path = g7.get("trigger_preview") or g7.get("neutral_preview") or "preview_mouth_open_simulated.png"
        if not os.path.exists(preview_img_path):
            preview_img_path = "preview_neutral_simulated.png"
        if os.path.exists(preview_img_path):
            print("\n=== STEP 5.6: UPLOADING HIGH-IMPACT PREVIEW IMAGE (FULL AR EFFECT) TO BOLT CDN ===")
            try:
                with open(preview_img_path, "rb") as f:
                    pi_bytes = f.read()
                preview_img_url, preview_img_key = client.upload_preview_video(pi_bytes)
                print(f"[PREVIEW IMAGE OK] CDN URL: {preview_img_url}")
                print(f"[PREVIEW IMAGE OK] AES Key: {preview_img_key[:10]}...")
            except Exception as e:
                print(f"[PREVIEW IMAGE WARN] Bolt upload failed ({e}). Proceeding without preview image.")

        # Check for viral lens icon from Gate 7
        icon_url = None
        icon_key = None
        icon_path = g7.get("lens_icon") or "lens_icon.png"
        if os.path.exists(icon_path):
            print("\n=== STEP 5.7: UPLOADING HIGH-CTR VIRAL LENS ICON ('THE PICK') TO BOLT CDN ===")
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
            icon_encryption_key=icon_key,
            preview_image_url=preview_img_url,
            preview_image_encryption_key=preview_img_key
        )
        print("Publish response:", pub_res)

        status_data = None
        if checkpoint_id:
            print("\n=== STEP 7: MONITORING SNAPCODE & SUBMISSION STATUS ===")
            try:
                status_data = client.get_publish_status(checkpoint_id, max_wait_sec=45)
                if status_data:
                    print(f"[SUCCESS] Published Lens ID: {status_data.get('lens_central_lens_id')}")
                    print(f"[SUCCESS] Catalog Status: {status_data.get('status')}")
                    with open("publish_status.json", "w") as f:
                        json.dump(status_data, f, indent=2)
            except Exception as mon_err:
                print(f"[STATUS MONITOR WARN] Polling timed out or network error ({mon_err}), but lens was already submitted successfully!")

        # Step 7B: Autonomous Top Performer Payouts & Lens+ Program Enrollment
        pub_lens_id = (status_data or {}).get("lens_central_lens_id") or pub_res.get("lens_central_lens_id")
        payout_enrolled = False
        if pub_lens_id and os.getenv("AUTO_APPROVE_MONETIZATION", "true").lower() in ("true", "1", "yes"):
            print(f"\n=== STEP 7B: ENROLLING PUBLISHED LENS ({pub_lens_id}) INTO TOP PERFORMER PAYOUTS ===")
            from approve_snap_monetization import approve_account_monetization
            for enroll_try in range(2):
                try:
                    enroll_res = approve_account_monetization(
                        account_id=ACCOUNT_ID,
                        cookie_str=getattr(client, "accounts_cookie", "") or getattr(client, "cookie_header", "") or (client.session.headers.get("Cookie", "") if hasattr(client, "session") else ""),
                        ticket=client.sso_token,
                        user=user,
                        target_lens_id=pub_lens_id,
                        target_lens_url=f"https://my-lenses.snapchat.com/lens/{pub_lens_id}"
                    )
                    payout_enrolled = bool(
                        enroll_res.get("target_lens_verified", False)
                        or enroll_res.get("top_performer_toggled", False)
                    )
                    print(f"[STEP 7B ATTEMPT {enroll_try+1}] Payout Enrollment result: enrolled={payout_enrolled}")
                    if payout_enrolled:
                        break
                    print(f"[STEP 7B ATTEMPT {enroll_try+1}] Lens not yet verified enrolled; waiting 25s for catalog ingestion...")
                    time.sleep(25)
                except Exception as enroll_err:
                    print(f"[STEP 7B WARN] Payout enrollment notice (attempt {enroll_try+1}): {enroll_err}")
                    time.sleep(10)

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
            "lens_id": pub_lens_id,
            "checkpoint_id": checkpoint_id,
            "prompt": prompt,
            "tags": tags,
            "visual_hook": (gemini_plan or {}).get("visual_hook", "") if USE_GEMINI else "",
            "has_preview_video": bool(preview_url),
            "preview_url": preview_url,
            "has_preview_image": bool(preview_img_url),
            "preview_image_url": preview_img_url,
            "has_lens_icon": bool(icon_url),
            "icon_url": icon_url,
            "creator_rewards_enrolled": payout_enrolled,
            "status": (status_data or {}).get("status", "pending")
        }
        history.append(entry)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
        print(f"[STATE] Recorded '{final_lens_name}' to {history_file} (Total fleet lenses: {len(history)}, Payout Enrolled: {payout_enrolled})")

    print("\n=== PIPELINE FINISHED SUCCESSFULLY WITH 100% VERIFICATION ===")


if __name__ == "__main__":
    main()
