import os
import sys
import json
import time
import re
import requests

CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
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

    # Fallback to local_env.sh if running locally and env var not propagated
    if not keys and os.path.exists("/root/local_env.sh"):
        try:
            with open("/root/local_env.sh", "r") as f:
                content = f.read()
            match = re.search(r"export GEMINI_API_KEY=[\"\x27]?([^\"\x27\r\n]+)", content)
            if match:
                keys.append(match.group(1).strip())
            match_multi = re.search(r"export GEMINI_API_KEYS=[\"\x27]?([^\"\x27\r\n]+)", content)
            if match_multi:
                for k in match_multi.group(1).split(","):
                    k = k.strip()
                    if k and k not in keys:
                        keys.append(k)
        except Exception:
            pass

    return keys


# ==============================================================================
# 5-CHANNEL NICHE DIFFERENTIATION & PROMPT MATRICES (ZERO CROSS-CONTAMINATION)
# ==============================================================================
CHANNEL_PROMPT_MATRICES = {
    "1": {
        "channel_name": "MythicBeasts_AR",
        "genre": "Mythological Beasts, Celestial Crowns & Elemental Breath",
        "craft_dials": {
            "design_variance": 0.88,
            "visual_density": 0.92,
            "motion_intensity": 0.90
        },
        "forbidden_cross_contamination": [
            "cyberpunk HUD", "neon visors", "crying memes", "cartoon stormcloud",
            "modern sunglasses", "cheap 2D stickers", "canvas spinners", "developer UI sliders"
        ],
        "tag_pool": ["dragon", "phoenix", "mythology", "3d", "headpiece", "crown", "fantasy", "pbr"],
        "archetypes": [
            {
                "id": "dragon_pyrodrake",
                "name": "Obsidian Dragon Crown & Emerald Pyro-Torrent",
                "signature_tokens": ["dragon", "wyvern", "pyrodrake", "dragon horn"],
                "focus": "Sculpted obsidian dragon horn crown anchored to temples with liquid 24k gold filigree and caustic ruby gems, PBR anisotropic metallic reflections, 3-point contrast 6500K/2800K lighting with ray-traced contact shadows. Opening mouth erupts turbulent emerald flame torrent with floating amber sparks; smiling ignites golden runic eye halos. Depth occlusion enabled, zero strobing, no sliders.",
                "primary_trigger": "MouthOpen (Turbulent emerald dragon flame torrent & embers) / Smile (Bright golden runic eye halos)",
                "visual_hook": "Instantaneous snap of gleaming obsidian and gold dragon horns fitted to the user's head with hyper-realistic reflections and reactive dragon flame."
            },
            {
                "id": "phoenix_solar",
                "name": "Phoenix Solar Diadem & Blinding Plumage Shockwave",
                "signature_tokens": ["phoenix", "firebird", "solar diadem", "solar plasma"],
                "focus": "Sculpted molten 24k rose-gold phoenix diadem fitted to hairline with radiant solar ember crest. PBR feathered iridescent wings contouring temples with subsurface scattering and 3-point contrast rim lighting. Opening mouth unleashes blinding solar plasma plumage burst and rising golden ash particles; smiling triggers brilliant sun-flare corona around brow. Zero strobing, zero UI.",
                "primary_trigger": "MouthOpen (Blinding solar plumage shockwave & golden ash) / Smile (Radiant sun-flare corona)",
                "visual_hook": "Luminous molten rose-gold phoenix crown blazes to life across the forehead with fiery solar radiance in 0.2s."
            },
            {
                "id": "valkyrie_aurora",
                "name": "Valkyrie Winged Helm & Frosted Aurora Mist",
                "signature_tokens": ["valkyrie", "winged circlet", "aurora borealis", "frosted arctic"],
                "focus": "Brushed silver and iridescent mother-of-pearl Valkyrie winged circlet fitted firmly to forehead. Photorealistic PBR metal reflections with frosted runic engravings and cool 6500K Nordic key lighting. Opening mouth summons ethereal soaring spectral raven aura and frosted arctic mist; smiling ignites crystalline glacial eye glints. Seamless head tracking, zero strobing.",
                "primary_trigger": "MouthOpen (Spectral raven aura & frosted arctic mist) / Smile (Crystalline glacial eye glints)",
                "visual_hook": "Peerless Nordic warrior aesthetic: shimmering silver Valkyrie wings frame the temples with swirling aurora borealis mist."
            },
            {
                "id": "celestial_kitsune",
                "name": "Celestial Kitsune Mask & Azure Spirit Foxfire",
                "signature_tokens": ["kitsune", "foxfire", "spirit fox", "vermilion lacquer"],
                "focus": "Carved porcelain and polished vermilion lacquer kitsune forehead crest anchored strictly to brow, leaving eyes and mouth clear. Shimmering spirit bells and twin floating foxfire tails contouring jawline. Opening mouth erupts swirling azure spirit flame orbs with dynamic volumetric embers; smiling reveals ethereal golden fox spirit eye reflections. Pure PBR craft, zero UI.",
                "primary_trigger": "MouthOpen (Swirling azure foxfire orbs & spirit embers) / Smile (Ethereal golden spirit eye flares)",
                "visual_hook": "Ancient spirit fox crest snaps onto brow with mesmerizing azure foxfire dancing around face."
            },
            {
                "id": "anubis_eclipse",
                "name": "Anubis Jackal Coronet & Swirling Sandstorm Vortex",
                "signature_tokens": ["anubis", "jackal coronet", "sandstorm vortex", "hieroglyphic"],
                "focus": "Anubis matte black basalt and electrum jackal coronet fitted securely to crown and temples with glowing lapis lazuli inlays. 3-point contrast 2800K desert key light with ray-traced contact shadows. Opening mouth triggers swirling golden sandstorm vortex and ancient hieroglyphic embers; smiling aligns a glowing solar eclipse halo behind crown. Zero strobing, zero UI.",
                "primary_trigger": "MouthOpen (Swirling golden sandstorm vortex & embers) / Smile (Radiant solar eclipse halo)",
                "visual_hook": "Imposing ancient Egyptian jackal coronet rises with dark basalt geometry and swirling golden sandstorm vortex."
            },
            {
                "id": "leviathan_frost",
                "name": "Leviathan Abyssal Coronet & Glacial Geyser",
                "signature_tokens": ["leviathan", "abyssal coronet", "frost serpent", "cryo-crystals"],
                "focus": "Deep ocean Leviathan serpent horns sculpted from anisotropic sapphire ice and electrum filigree anchored to brow. PBR metallic reflections with ray-traced contact shadows. Opening mouth unleashes pressurized sub-zero frost geyser with floating cryo-crystals; smiling ignites piercing runic blue gaze flares. Depth occlusion enabled, zero UI.",
                "primary_trigger": "MouthOpen (Pressurized sub-zero frost geyser & cryo-crystals) / Smile (Piercing runic blue gaze flares)",
                "visual_hook": "Majestic abyssal sapphire horns grip the brow, unleashing an explosive sub-zero cryo-crystal geyser on mouth open."
            },
            {
                "id": "ouroboros_solar",
                "name": "Gilded Ouroboros Serpent Circlet & Solar Flare",
                "signature_tokens": ["ouroboros", "serpent circlet", "solar plasma flare", "coiled serpent"],
                "focus": "Interlocking 24k gold ouroboros serpent circlet coiled snugly around hairline with radiant ruby eyes. PBR metallic reflections and 3-point contrast 2800K lighting. Opening mouth triggers concentric solar plasma flare rings radiating outward; smiling ignites glittering molten gold embers cascading down cheeks. Seamless head tracking, zero strobing.",
                "primary_trigger": "MouthOpen (Concentric solar plasma flare rings) / Smile (Glittering molten gold cheek embers)",
                "visual_hook": "Ancient golden serpent coils around hairline with glowing ruby eyes, bursting with radiant solar flares."
            },
            {
                "id": "gorgon_aegis",
                "name": "Obsidian Gorgon Viper Crest & Petrifying Gaze",
                "signature_tokens": ["gorgon", "viper crest", "petrifying mist", "bronze serpents"],
                "focus": "Regal basalt and bronze Gorgon viper tiara fitted across forehead, micro-scaled serpents undulating with ray-traced shadows. PBR metallic luster and warm rim light. Opening mouth summons swirling emerald petrification mist with floating basalt dust; smiling flashes brilliant golden serpentine eye glints. Seamless head tracking, zero strobing.",
                "primary_trigger": "MouthOpen (Swirling emerald petrification mist & basalt dust) / Smile (Serpentine golden eye flares)",
                "visual_hook": "Dark mythical Gorgon vipers crown the brow in polished basalt and bronze, summoning swirling emerald petrification mist."
            },
            {
                "id": "chimera_infernal",
                "name": "Infernal Chimera Horned Helm & Magma Sparks",
                "signature_tokens": ["chimera", "infernal helm", "magma sparks", "meteoric iron"],
                "focus": "Polished meteoric iron and electrum Chimera horned circlet fitted to head and temples with smoldering obsidian plates. 3-point contrast lighting with ray-traced shadows. Opening mouth erupts volcanic magma sparks and billowing crimson embers; smiling awakens radiant molten gold fissure lines running along cheekbones. Pure PBR fantasy craft, zero UI.",
                "primary_trigger": "MouthOpen (Volcanic magma sparks & crimson embers) / Smile (Molten gold cheek fissure lines)",
                "visual_hook": "Meteoric iron horned helm smolders against the temples, erupting with volcanic magma embers and golden cheek runes."
            },
            {
                "id": "garuda_celestial",
                "name": "Celestial Garuda Feathered Crown & Divine Gale",
                "signature_tokens": ["garuda", "feathered crown", "divine gale", "sacred lotus"],
                "focus": "Sculpted 24k beaten gold Garuda crest with iridescent feathered plumes contouring brow and temples. Soft celestial rim lighting and subsurface scattering. Opening mouth unleashes swirling divine gale vortex with floating golden sacred lotus petals; smiling triggers blinding golden solar beam flares from brow. Zero strobing, zero UI.",
                "primary_trigger": "MouthOpen (Swirling divine gale vortex & golden lotus petals) / Smile (Blinding golden solar beam flares)",
                "visual_hook": "Opulent feathered Garuda crest sweeps across brow in 24k gold, commanding a vortex of glowing golden lotus petals."
            }
        ]
    },
    "2": {
        "channel_name": "SciFi_Optics",
        "genre": "Cyberpunk HUD Eyewear, Retinal Scanners & Kinetic Optics",
        "craft_dials": {
            "design_variance": 0.85,
            "visual_density": 0.90,
            "motion_intensity": 0.85
        },
        "forbidden_cross_contamination": [
            "2D canvas spinners", "flat screen overlays", "dragons", "mythical beasts",
            "cartoon crying clouds", "gold baroque filigree", "medieval helmets", "crying memes", "developer UI sliders"
        ],
        "tag_pool": ["cyberpunk", "visor", "optics", "hud", "scifi", "tech", "pbr", "audioreactive"],
        "archetypes": [
            {
                "id": "titanium_holo_visor",
                "name": "Brushed Titanium Holo-Visor & Radial Shockwave",
                "signature_tokens": ["visor", "holo-visor", "laser shockwave"],
                "focus": "Ergonomic cyberpunk HUD visor resting strictly across eyes leaving cheeks and mouth clear for tracking. Brushed titanium frame with pulsing cyan neon edge emission, PBR anisotropic reflections, and ray-traced shadows. Opening mouth triggers radial laser particle shockwave; smiling activates bright neon visor HUD telemetry readout. Zero strobing, zero UI sliders, pure 3D assets only.",
                "primary_trigger": "MouthOpen (Radial cyan laser particle shockwave) / Smile (Neon visor HUD telemetry flare)",
                "visual_hook": "Instantaneous snap of high-fidelity brushed titanium and refractive glass catching live reflections in 0.2s."
            },
            {
                "id": "cybernetic_ocular_scanner",
                "name": "Cybernetic Ocular Scanner & Retinal Data Stream",
                "signature_tokens": ["ocular scanner", "retinal scanner", "cybernetic monocle", "targeting reticle", "ocular"],
                "focus": "Asymmetrical carbon fiber and tungsten ocular scanner anchored firmly over left eye orbital bone and brow, leaving face and mouth unobstructed. Multi-layered refractive cyan targeting lenses with micro-servo details. Opening mouth projects floating 3D tactical holographic wireframe mesh; smiling cycles high-speed green diagnostic data stream through ocular optics. PBR materials, ray-traced shadows.",
                "primary_trigger": "MouthOpen (3D tactical holographic wireframe projection) / Smile (High-speed green data stream pulse)",
                "visual_hook": "Elite cyberpunk tactical scanner locks onto eye with animated focal reticles and sharp volumetric telemetry."
            },
            {
                "id": "neon_speed_goggles",
                "name": "Neon Speed-Optic Goggles & Chromatic Hyperdrive",
                "signature_tokens": ["goggles", "speed-optic", "hyperdrive", "racer"],
                "focus": "Ultra-lightweight matte-black alloy speed-optic goggles fitted across brow and nose bridge. Features illuminated amber and electric blue neon optical rings with internal refractive glass prism elements. PBR metallic shaders with ray-traced contact shadows. Opening mouth triggers hyperdrive chromatic warp streak particle bursts across peripheral vision; smiling flashes dual-frequency optic diagnostic glow. Zero strobing, zero UI.",
                "primary_trigger": "MouthOpen (Hyperdrive chromatic warp particle streaks) / Smile (Dual-frequency optic diagnostic flash)",
                "visual_hook": "Aerodynamic racing goggles snap onto face with glowing neon optical rings catching cinematic light."
            },
            {
                "id": "mech_pilot_telemetry",
                "name": "Mech Pilot HUD Frame & Telemetry EMP Ring",
                "signature_tokens": ["mech pilot", "telemetry glyphs", "emp ring", "target-lock"],
                "focus": "Anodized cobalt-titanium open-frame pilot HUD glasses fitted securely along upper cheekbones and temples. PBR metallic frame with floating volumetric amber flight telemetry glyphs orbiting brow. Opening mouth discharges sonic cyan EMP wave particle ring expanding outward; smiling activates high-precision tactical target-lock bracket flash across lenses. Fully 3D face anchored, zero UI sliders.",
                "primary_trigger": "MouthOpen (Cyan sonic EMP particle ring expansion) / Smile (Tactical target-lock bracket flash)",
                "visual_hook": "Military-grade mech pilot telemetry frame materializes with crisp floating HUD glyphs and dynamic EMP pulse."
            },
            {
                "id": "quantum_neural_monocular",
                "name": "Quantum Neural Monocular & Volumetric Hologram",
                "signature_tokens": ["quantum", "neural monocle", "monocular", "planetary hologram"],
                "focus": "Sleek chrome-plated neural monocular optic docked along right temple and cheek with floating quantum focal rings. Anisotropic PBR reflections with deep purple laser prism optics. Opening mouth projects spinning volumetric miniature planetary hologram between eyebrows; smiling triggers high-energy neural pulse wave radiating through chrome temple connector. No text, zero UI.",
                "primary_trigger": "MouthOpen (Volumetric planetary hologram projection) / Smile (High-energy neural pulse wave flare)",
                "visual_hook": "Futuristic neural optic locks into temple with floating holographic focal rings and planetary projection."
            },
            {
                "id": "tactical_orbital_reticle",
                "name": "Tactical Orbital Targeting Monocle & Laser Lock",
                "signature_tokens": ["orbital reticle", "targeting monocle", "laser lock", "ballistic monocle"],
                "focus": "Matte carbon-fiber ballistic monocle anchored over right eye and brow with micro-aperture ring. Anisotropic PBR reflections, ray-traced shadows. Opening mouth projects 3D floating volumetric targeting reticle grid expanding into space; smiling locks glowing red orbital telemetry beam flare across lens. Pure 3D assets, native mobile AR.",
                "primary_trigger": "MouthOpen (3D volumetric targeting reticle grid) / Smile (Red orbital telemetry beam lock flare)",
                "visual_hook": "Carbon-fiber ballistic monocle locks over eye, projecting a crisp volumetric 3D orbital targeting grid in 0.2s."
            },
            {
                "id": "apex_spectre_visor",
                "name": "Stealth Spectre Prismatic Visor & Sonic Burst",
                "signature_tokens": ["spectre visor", "stealth visor", "prismatic glass", "biometric lock"],
                "focus": "Faceted obsidian and dichroic glass stealth visor contoured across brow and temples. 3-point contrast lighting with violet rim. Opening mouth emits radial sonic particle shockwave with refractive edge displacement; smiling flashes crisp cyan biometric lock indicators across prismatic glass face. Zero strobing, pure 3D mesh and volumetric particles only.",
                "primary_trigger": "MouthOpen (Radial sonic particle shockwave) / Smile (Cyan biometric lock indicators on glass)",
                "visual_hook": "Angular dichroic glass stealth visor reflects dark violet rim lighting, discharging a sonic particle wave on mouth open."
            },
            {
                "id": "neural_synapse_cortex",
                "name": "Cybernetic Synapse Brow Frame & Kinetic EMP",
                "signature_tokens": ["synapse frame", "brow frame", "optical conduits", "kinetic emp"],
                "focus": "Brushed aerospace aluminum neural bracket fitted firmly to brow with glowing micro-fiber optical conduits. Anisotropic PBR reflections and baked contact shadows. Opening mouth releases kinetic EMP spark wave surging across temples; smiling surges electric blue volumetric particle pulses through optical conduits. PBR metallic shaders, zero UI sliders.",
                "primary_trigger": "MouthOpen (Kinetic EMP spark wave surge across temples) / Smile (Electric blue volumetric particle conduit pulse)",
                "visual_hook": "High-tech aluminum neural bracket clamps to brow, pulsing electric blue light through fiber optic channels."
            },
            {
                "id": "subzero_cryo_optics",
                "name": "Cryo-Tactical Ballistic Visor & Frost Vent",
                "signature_tokens": ["cryo optics", "ballistic visor", "subzero vent", "frost jet"],
                "focus": "Cryogenic frosted polymer and tungsten tactical visor resting across eyes leaving mouth clear. Subsurface refraction with cool 6500K rim light. Opening mouth vents pressurized volumetric sub-zero cryo particle jets sideways from temple mounts; smiling activates laser diagnostic telemetry reticle glow. Pure 3D native AR.",
                "primary_trigger": "MouthOpen (Volumetric cryo particle jets from temples) / Smile (Laser diagnostic telemetry reticle glow)",
                "visual_hook": "Frosted tactical visor clamps over eyes, blasting pressurized sub-zero cryo vapor from temples on mouth open."
            },
            {
                "id": "matrix_overdrive_hud",
                "name": "Overdrive Telemetry Spectacles & Data Cascade",
                "signature_tokens": ["overdrive spectacles", "smart spectacles", "wireframe cubes", "telemetry cascade"],
                "focus": "Precision titanium wireframe smart spectacles docked to face, nose and brow with transparent optical prisms. Anisotropic reflections and ray-traced shadows. Opening mouth discharges floating 3D volumetric wireframe cubes expanding forward; smiling pulses high-speed emerald telemetry photon glints through glass lenses. Pure 3D AR, zero UI sliders.",
                "primary_trigger": "MouthOpen (3D volumetric wireframe cubes expanding forward) / Smile (High-speed emerald telemetry photon glints)",
                "visual_hook": "Ultra-thin titanium smart spectacles project floating 3D holographic wireframe geometry directly in front of the eyes."
            }
        ]
    },
    "3": {
        "channel_name": "WarpShock_Comedy",
        "genre": "Viral Memes, Kinetic Facial Warping & Dramatic Reactions",
        "craft_dials": {
            "design_variance": 0.95,
            "visual_density": 0.85,
            "motion_intensity": 0.95
        },
        "forbidden_cross_contamination": [
            "serious dark fantasy", "solemn mythic armor", "luxury haute couture",
            "serious tactical military HUD", "plain static items", "developer UI sliders"
        ],
        "tag_pool": ["meme", "crying", "funny", "cartoon", "comedy", "viral", "reaction"],
        "archetypes": [
            {
                "id": "fluffy_crying_stormcloud",
                "name": "Volumetric Cartoon Stormcloud & Liquid Teardrop Geyser",
                "signature_tokens": ["stormcloud", "cloud", "mercury teardrop", "gold coins bouncing"],
                "focus": "Fluffy PBR volumetric cartoon stormcloud anchored directly above head, casting soft contact shadows with 6500K/2800K directional rim lighting and ambient thunder glow. Opening mouth triggers exaggerated physics-driven liquid mercury teardrop geyser and spinning 24k gold coins bouncing off camera frame; smiling triggers warm comical lightning flash. Zero strobe, safe performance.",
                "primary_trigger": "MouthOpen (Exaggerated geyser of liquid tears & bouncing gold coins) / Smile (Dramatic comical lightning rim flash)",
                "visual_hook": "Fluffy 3D stormcloud hovers overhead with funny gentle rain, erupting into a hilarious gold-coin teardrop geyser on mouth open."
            },
            {
                "id": "soap_opera_melodrama",
                "name": "Soap-Opera Melodramatic Waterfall Tears & Glitter Confetti",
                "signature_tokens": ["soap-opera", "melodrama", "waterfall tears", "broken-heart"],
                "focus": "Vintage melodramatic soap-opera vignette with physical 3D crystalline tear waterfalls cascading comically from eyes across face. PBR water caustics with soft romantic halo lighting. Opening mouth erupts torrential twin weeping fountains and floating comedy broken-heart shards; smiling instantly shatters the drama into a cheerful explosion of rainbow glitter confetti. Pure comedy AR.",
                "primary_trigger": "MouthOpen (Torrential twin weeping waterfalls & broken hearts) / Smile (Explosive cheerful rainbow confetti burst)",
                "visual_hook": "Instant soap-opera drama: hyperbolic 3D waterfall tears cascade from eyes with hilarious melodrama, instantly clearing into confetti on smile."
            },
            {
                "id": "steam_rage_valve",
                "name": "Cartoon Steam-Whistle Pressure Valve & Rainbow Exhaust",
                "signature_tokens": ["steam-whistle", "steam plumes", "boiler valve", "rage whistle"],
                "focus": "Comic stylized polished brass steam boiler pressure valve mounted securely to forehead with vibrating needle gauge. 3-point warm lighting with baked shadows. Opening mouth releases explosive pressurized cartoon steam clouds blasting sideways from ears with comic red face flush; smiling vents gentle harmless rainbow bubble streams from the whistle valve. Zero UI, high viral comedy.",
                "primary_trigger": "MouthOpen (Explosive pressurized steam geysers from ears) / Smile (Gentle rainbow bubble exhaust stream)",
                "visual_hook": "Hilarious rage whistle: brass boiler valve on brow erupts giant cartoon steam plumes from ears on mouth open."
            },
            {
                "id": "laughing_gold_skull",
                "name": "Mini Laughing Golden Skull & Mega Confetti Cannon",
                "signature_tokens": ["laughing skull", "confetti cannon", "skull mascot"],
                "focus": "Stylized 3D polished 24k gold cartoon skull mascot hovering cheerfully above right shoulder and tilting with head movements. Opening mouth activates giant comic gold confetti cannon blasting party streamers and floating laughing emoji sparks across screen; smiling triggers comical golden tooth-twinkle starburst and energetic skull bobbing animation. Pure infectious joy.",
                "primary_trigger": "MouthOpen (Mega gold confetti cannon & party streamers) / Smile (Golden tooth-twinkle starburst & happy bobbing)",
                "visual_hook": "Charming golden cartoon skull mascot bounces beside head and fires a massive comical confetti blast on mouth open."
            },
            {
                "id": "hypno_spiral_shockwave",
                "name": "Pop-Out Spiral Hypno-Goggles & Cartoon Exclamation Sparks",
                "signature_tokens": ["spiral hypno", "hypno-goggles", "pop-out", "exclamation marks"],
                "focus": "Exaggerated 3D glowing cartoon spiral hypno-goggles anchored over eyes that comical stretch and pop forward 10cm on face trigger. PBR stylized materials with ray-traced contact shadows. Opening mouth triggers shockwave rings with floating animated comic exclamation marks and bouncing question mark stars; smiling snaps goggles back with hilarious kaleidoscope optic swirl. Physics-driven, zero strobing.",
                "primary_trigger": "MouthOpen (Pop-out goggle stretch & exclamation shockwave) / Smile (Kaleidoscopic optic swirl snap-back)",
                "visual_hook": "Cartoon bug-eyed shock: giant spiral hypno-goggles spring forward comically from face with floating question marks."
            },
            {
                "id": "jawdrop_coin_cascade",
                "name": "Cartoon Jaw-Drop Spring & Gold Coin Cascade",
                "signature_tokens": ["jaw-drop", "spring chin", "coin cascade", "bulging eyes"],
                "focus": "Exaggerated 3D mechanical cartoon spring chin and bulging cartoon eyes anchored to face. 3-point comic lighting with ray-traced shadows. Opening mouth triggers hilarious jaw-drop extension unleashing cascading fountain of spinning 24k gold coins and comic exclamation sparks; smiling pops eyes back with comical starburst glints. Pure viral comedy AR.",
                "primary_trigger": "MouthOpen (Hilarious jaw-drop spring extension & gold coin fountain) / Smile (Comical starburst eye pop-back)",
                "visual_hook": "Cartoon jaw drops 2 feet down on a bouncing spring, spraying thousands of spinning gold coins off screen."
            },
            {
                "id": "dramatic_anime_tears",
                "name": "Anime Torrential Weeping Jets & Rainbow Arc",
                "signature_tokens": ["anime tears", "weeping jets", "water torrents", "rainbow arc"],
                "focus": "Stylized oversized crystalline anime tear jets anchored to lower eye contours. PBR liquid reflections and ambient room lighting. Opening mouth unleashes twin high-pressure horizontal water torrents blasting outward with floating broken comic hearts; smiling instantly clears tears into an arching 3D rainbow halo over head. Physics-driven, zero strobing.",
                "primary_trigger": "MouthOpen (Twin horizontal cartoon water torrents & broken hearts) / Smile (Arching 3D rainbow halo over head)",
                "visual_hook": "Hyperbolic anime tears shoot out sideways like water cannons, clearing into an instant radiant rainbow halo on smile."
            },
            {
                "id": "mindblown_cosmic_pop",
                "name": "Mind-Blown Pop-Top Head & Galaxy Fireworks",
                "signature_tokens": ["mind-blown", "pop-top", "cosmic fireworks", "lightbulb crown"],
                "focus": "Stylized cartoon skull top-hatch fitted to hairline with bouncing miniature antenna. Anisotropic metallic reflections and baked shadows. Opening mouth pops hatch open with dramatic cartoon mushroom cloud of glowing rainbow star particles and floating comic UFOs; smiling triggers comical golden lightbulb illumination above crown with star glints. Pure comedy AR.",
                "primary_trigger": "MouthOpen (Pop-top hatch opens with rainbow cosmic mushroom cloud) / Smile (Glowing golden idea lightbulb illumination)",
                "visual_hook": "Top of the head pops open like a cartoon tin lid, erupting with a colorful mushroom cloud of cosmic stars and UFOs."
            },
            {
                "id": "pepper_fire_breath",
                "name": "Flaming Red Hot Pepper Crown & Comic Fire Jet",
                "signature_tokens": ["hot pepper", "fire breath", "chili horns", "cartoon flame"],
                "focus": "Cartoony glowing red chili pepper horns mounted to temples with sizzling PBR smoke embers. 3-point contrast lighting. Opening mouth blasts giant comic cartoon flame geyser forward with bouncing sweating teardrops; smiling cools face into icy cartoon frost with soothing blue halo sparkles. High-impact viral reaction AR.",
                "primary_trigger": "MouthOpen (Giant cartoon fire geyser & sweating teardrops) / Smile (Soothing icy frost & blue halo sparkles)",
                "visual_hook": "Glowing red chili horns sizzle at temples, blasting a hilarious comic fire jet forward when user opens mouth."
            },
            {
                "id": "dizzy_star_whirl",
                "name": "Comic Dizzy Bird Whirl & Feather Burst",
                "signature_tokens": ["dizzy stars", "chirping birds", "feather burst", "question marks"],
                "focus": "Stylized golden cartoon stars and miniature chirping canary models orbiting brow in zero-g. 3-point contrast lighting with soft shadows. Opening mouth scatters comical flurry of yellow feathers and floating giant comic question marks; smiling snaps stars into a sparkling celebratory crown above forehead. Zero UI sliders, pure meme fun.",
                "primary_trigger": "MouthOpen (Flurry of yellow feathers & comic question marks) / Smile (Sparkling celebratory star crown alignment)",
                "visual_hook": "Classic cartoon knock-out: animated yellow birds and dizzy stars spin around brow, erupting feathers on mouth open."
            }
        ]
    },
    "4": {
        "channel_name": "Lumiere_Atelier",
        "genre": "35mm Analog Luxury, Haute Couture & Golden Hour Aesthetics",
        "craft_dials": {
            "design_variance": 0.82,
            "visual_density": 0.95,
            "motion_intensity": 0.70
        },
        "forbidden_cross_contamination": [
            "cartoon memes", "crying coins", "cyberpunk neon HUDs", "monster horns",
            "cheap plastic stickers", "grotesque elements", "developer UI sliders"
        ],
        "tag_pool": ["film", "35mm", "crown", "gold", "luxury", "haute_couture", "aesthetic", "beauty"],
        "archetypes": [
            {
                "id": "haute_baroque_gold",
                "name": "Sculpted 24k Gold Leaf Baroque Crown & Caustic Sparkles",
                "signature_tokens": ["baroque", "24k gold leaf", "crystal prisms"],
                "focus": "Sculpted 24k gold leaf baroque crown fitted firmly to forehead and temples with embedded caustic crystal prisms. Anisotropic metal PBR reflections with Kodak 35mm film halation and subtle grain. Opening mouth parts delicate golden gossamer veil; smiling triggers rich golden sparkle dust particles cascading softly across cheekbones. Photosensitive safe, zero strobing.",
                "primary_trigger": "MouthOpen (Delicate golden gossamer veil parting) / Smile (Brilliant caustic sparkle dust cascading on cheekbones)",
                "visual_hook": "Instant flash of opulent 24k gold leaf and caustic crystal light refraction framing user's upper face with timeless analog warmth."
            },
            {
                "id": "pearl_celestial_diadem",
                "name": "Freshwater Pearl Celestial Diadem & Golden Hour Sheen",
                "signature_tokens": ["freshwater pearl", "pearl diadem", "champagne light motes"],
                "focus": "Floating halo diadem of baroque freshwater pearls and hand-twisted 18k champagne gold wire resting above hairline. Subtle Portra 400 golden-hour film bloom with warm 2800K key light. Opening mouth summons gentle floating champagne light motes around face; smiling illuminates an ethereal high-fashion skin sheen and caustic crystal ear shimmer. Ultra-luxury vanity aesthetic.",
                "primary_trigger": "MouthOpen (Floating champagne light motes around face) / Smile (Ethereal luminous skin sheen & crystal shimmer)",
                "visual_hook": "Ethereal halo of luminous pearls and champagne gold elevates face into a dreamy 35mm high-fashion editorial portrait."
            },
            {
                "id": "art_nouveau_tiara",
                "name": "Art Nouveau Emerald Tiara & Shimmering Gossamer Veil",
                "signature_tokens": ["art nouveau", "emerald cabochon", "gossamer veil", "paris couture"],
                "focus": "Art Nouveau floral tiara sculpted from antiqued yellow gold with deep emerald cabochon accents anchored securely to brow. Soft 35mm analog vignette with delicate warm highlights. Opening mouth floats a semi-translucent golden silk shimmer veil across temples; smiling activates subtle emerald light refraction flares across eye contours. Pure Parisian couture craft, zero UI.",
                "primary_trigger": "MouthOpen (Semi-translucent golden silk shimmer veil) / Smile (Emerald light refraction flares across eye contours)",
                "visual_hook": "Fin de siecle Parisian glamour: sculpted golden vines and glowing emerald cabochons frame the brow with filmic radiance."
            },
            {
                "id": "champagne_diamond_coronal",
                "name": "Champagne Micro-Faceted Diamond Coronal & Starburst Glints",
                "signature_tokens": ["champagne diamond", "diamond coronal", "faceted diamond"],
                "focus": "Precision micro-faceted champagne diamond coronal resting tightly along hairline. Micro-surface roughness maps catching golden hour sunlight with realistic chromatic dispersion. Opening mouth emits delicate suspended diamond dust particles orbiting crown; smiling triggers radiant starburst glints across cheekbone highlights with Portra warm tones. Zero strobing.",
                "primary_trigger": "MouthOpen (Suspended diamond dust particle orbital stream) / Smile (Radiant starburst glints on cheekbone highlights)",
                "visual_hook": "Breathtaking diamond brilliance: thousands of micro-faceted champagne gems shimmer under golden hour sun with analog film warmth."
            },
            {
                "id": "florentine_laurel_wreath",
                "name": "Gilded Florentine Laurel Leaf Wreath & Soft Sunbeams",
                "signature_tokens": ["florentine laurel", "laurel leaf wreath", "marble jasmine"],
                "focus": "Hand-hammered 24k gold Florentine laurel leaf wreath contoured to head with miniature carved marble jasmine blossoms. 3-point contrast lighting with soft golden volumetric god-rays framing silhouette. Opening mouth triggers gentle cascade of golden falling laurel petals; smiling illuminates soft golden-hour cheek glints and radiant warm skin bloom. Timeless luxury.",
                "primary_trigger": "MouthOpen (Gentle cascade of golden falling laurel petals) / Smile (Volumetric golden-hour cheek glints & warm skin bloom)",
                "visual_hook": "Majestic golden laurel wreath crowns the brow with delicate marble flowers and warm cinematic sunbeams."
            },
            {
                "id": "venetian_gold_filigree",
                "name": "Hand-Crafted Venetian 24k Gold Filigree Mask & Amber Glow",
                "signature_tokens": ["venetian mask", "gold filigree", "amber glow", "diamond prism"],
                "focus": "Hand-crafted Venetian 24k gold filigree half-mask contouring upper brow and cheekbones, leaving mouth completely free. Kodak Portra 400 film grain and warm 2800K halation. Opening mouth releases drifting amber gossamer specks; smiling triggers brilliant caustic diamond prism glints across cheekbones. High fashion luxury AR.",
                "primary_trigger": "MouthOpen (Drifting amber gossamer specks) / Smile (Caustic diamond prism cheek glints)",
                "visual_hook": "Exquisite Venetian lace hammered from 24k gold rests weightlessly across temples with rich analog film warmth."
            },
            {
                "id": "celestial_moonstone_halo",
                "name": "Iridescent Moonstone Platinum Circlet & Portra 400 Halation",
                "signature_tokens": ["moonstone circlet", "platinum circlet", "pearl dust", "dewy skin"],
                "focus": "Delicate platinum circlet set with shimmering rainbow moonstone cabochons resting at hairline. Subtle 35mm analog lens flare with golden-hour warmth and ray-traced shadows. Opening mouth summons ethereal floating celestial pearl dust around face; smiling illuminates radiant dewy skin sheen with caustic moonstone flares. Timeless couture.",
                "primary_trigger": "MouthOpen (Floating celestial pearl dust motes) / Smile (Dewy skin sheen & caustic moonstone flares)",
                "visual_hook": "Shimmering rainbow moonstones and pure platinum form a delicate celestial halo with dreamy 35mm film halation."
            },
            {
                "id": "gilded_butterfly_coronet",
                "name": "Gilded Gold Leaf Butterfly Coronet & Sunlit Petals",
                "signature_tokens": ["butterfly coronet", "gold leaf butterflies", "sunlit petals", "wing flutter"],
                "focus": "Sculpted 24k beaten gold filigree butterflies resting lightly across forehead and hair. Ray-traced contact shadows and warm golden lighting. Opening mouth awakens gentle wing flutter releasing drifting golden shimmer motes; smiling illuminates sparkling sunlight glints on cheekbone peaks. Elegant fine-art AR.",
                "primary_trigger": "MouthOpen (Gentle butterfly wing flutter & golden shimmer motes) / Smile (Sunlight sparkle glints on cheekbones)",
                "visual_hook": "Sculpted gold-leaf butterflies flutter softly at the hairline, showering the cheeks with warm sunlight sparkles."
            },
            {
                "id": "rose_gold_astral_tiara",
                "name": "Rose Gold Astral Starburst Tiara & Starlight Glints",
                "signature_tokens": ["rose gold tiara", "astral starburst", "morganite", "starlight veil"],
                "focus": "Hand-forged 18k rose gold astral starburst tiara anchored along brow with inset morganite gemstones. Portra film warmth with soft halation. Opening mouth releases cascading micro-glitter starlight veil; smiling triggers dazzling rose-gold starburst flares across eyes and cheekbones. Pure vanity elegance, zero UI.",
                "primary_trigger": "MouthOpen (Cascading micro-glitter starlight veil) / Smile (Dazzling rose-gold starburst eye flares)",
                "visual_hook": "Blushing 18k rose gold astral starburst tiara catches the golden-hour light with radiant morganite starlight glints."
            },
            {
                "id": "opal_sunburst_diadem",
                "name": "Australian Opal Sunburst Diadem & Golden Shimmer",
                "signature_tokens": ["opal diadem", "sunburst crown", "fire opal", "chromatic shimmer"],
                "focus": "Radiant sunburst diadem of fiery Australian opals and twisted yellow gold wire fitted securely above forehead. 3-point lighting with cinematic analog bloom. Opening mouth floats warm golden sun-dust motes across temples; smiling creates an exquisite chromatic rainbow shimmer across cheekbone highlights. Editorial beauty.",
                "primary_trigger": "MouthOpen (Warm golden sun-dust motes) / Smile (Chromatic rainbow shimmer on cheekbones)",
                "visual_hook": "Fiery Australian opals radiate in a golden sunburst halo above the brow, scattering vivid chromatic light across the face."
            }
        ]
    },
    "5": {
        "channel_name": "Chrono_Mirage",
        "genre": "Surrealism, Zero-G Liquid Chrome & Y3K Hypnotic Aesthetics",
        "craft_dials": {
            "design_variance": 0.92,
            "visual_density": 0.94,
            "motion_intensity": 0.88
        },
        "forbidden_cross_contamination": [
            "cartoon stormclouds", "traditional historical filigree", "retro cyan text HUDs",
            "meme gags", "medieval fantasy crowns", "developer UI sliders"
        ],
        "tag_pool": ["surreal", "chrome", "liquid_mercury", "halo", "y3k", "optical", "fluid"],
        "archetypes": [
            {
                "id": "liquid_mercury_halo",
                "name": "Zero-G Liquid Mercury Morphing Halo & Chrome Cheek Plates",
                "signature_tokens": ["liquid mercury halo", "chrome cheek plates", "surface tension"],
                "focus": "Ancillary surreal halo crown floating above head sculpted from highly-reflective liquid mercury with sculpted chrome cheekbone plates. Anisotropic mirror PBR reflections with fluid surface tension and ray-traced contact shadows. Opening mouth emits orbiting refractive chrome spheres; smiling triggers fluid surface ripples across chrome armor. Seamless physics, zero strobing.",
                "primary_trigger": "MouthOpen (Orbiting refractive liquid chrome spheres) / Smile (Fluid ripple normal-map distortion waves)",
                "visual_hook": "Instantaneous appearance of mesmerizing zero-g liquid mercury halo crown reflecting warped environment light in 0.2s."
            },
            {
                "id": "mobius_chrome_ribbon",
                "name": "Hypnotic Chrome Mobius Ribbon & Kaleidoscopic Mirror Shards",
                "signature_tokens": ["mobius", "liquid platinum ribbon", "kaleidoscopic mirror"],
                "focus": "Interlocking liquid platinum Mobius strip ribbon undulating continuously in zero-g around upper crown. Hyper-reflective chrome shader reflecting ambient environment with fluid refraction. Opening mouth sends floating chrome ribbon tendrils surging forward; smiling shatters ambient reflection into a hypnotic kaleidoscopic mirror prism facet display. Surreal Y3K aesthetic.",
                "primary_trigger": "MouthOpen (Floating chrome ribbon tendrils surging forward) / Smile (Hypnotic kaleidoscopic mirror facet reflection)",
                "visual_hook": "Futuristic liquid platinum Mobius ribbon twists weightlessly above head, refracting real-world surroundings into a surreal dreamscape."
            },
            {
                "id": "ferrofluid_biomorphic_horns",
                "name": "Glossy Black Ferrofluid Horns & Orbiting Mercury Droplets",
                "signature_tokens": ["ferrofluid", "magnetic spikes", "liquid mercury droplets"],
                "focus": "Glossy obsidian ferrofluid horn sculptures rising organically from temples, dynamically morphing between fluid blobs and magnetic spikes. 3-point contrast lighting with cool 6500K rim. Opening mouth suspends dozens of zero-g liquid mercury droplets floating across face; smiling pulses an electromagnetic ripple wave through the ferrofluid geometry. Pure surrealism.",
                "primary_trigger": "MouthOpen (Suspended zero-g liquid mercury droplet field) / Smile (Electromagnetic spike ripple wave through ferrofluid)",
                "visual_hook": "Alien bio-magnetic elegance: glossy black ferrofluid horns shift between liquid fluid and magnetic spikes along the temples."
            },
            {
                "id": "liquid_platinum_tears",
                "name": "Mirrored Liquid Platinum Tear-Tracks & Surreal Toroidal Halo",
                "signature_tokens": ["liquid platinum tear", "toroid halo", "molten mirrors"],
                "focus": "Mirrored liquid platinum teardrop sculptures frozen weightlessly along cheekbones with a floating surreal chrome toroid halo above head. Anisotropic fluid reflections with ray-traced shadows. Opening mouth releases liquid metal ripple shockwave radiating across cheek sculptures; smiling inverts chrome surface reflections with chromatic prism sheen. Photosensitive safe, zero strobing.",
                "primary_trigger": "MouthOpen (Liquid metal ripple shockwave across cheek sculptures) / Smile (Chromatic prism inversion on chrome surfaces)",
                "visual_hook": "High-concept surrealism: liquid platinum sculptures cling to cheekbones like molten mirrors beneath a weightless chrome toroid."
            },
            {
                "id": "iridescent_chrome_chrysalis",
                "name": "Reflective Liquid Bismuth Chrysalis & Chromatic Dispersion",
                "signature_tokens": ["bismuth chrysalis", "chromatic dispersion", "bubble ring"],
                "focus": "Ultra-reflective liquid bismuth and molten chrome chrysalis crest morphing over forehead with fluid tendrils framing temples. Shimmering prismatic surface iridescence with HDR environment reflections. Opening mouth expands an expanding liquid chrome bubble ring floating forward; smiling triggers fluid chromatic surface dispersion waves across face. Seamless zero-g AR.",
                "primary_trigger": "MouthOpen (Expanding liquid chrome bubble ring forward expansion) / Smile (Fluid chromatic dispersion waves across chrysalis)",
                "visual_hook": "Mesmerizing Y3K aesthetic: liquid bismuth and chrome crown undulates with iridescent rainbow reflections above the brow."
            },
            {
                "id": "hypercube_tesseract_halo",
                "name": "Zero-G Chrome Tesseract Halo & Gravitational Ripples",
                "signature_tokens": ["tesseract", "hypercube halo", "gravitational ripple", "liquid chrome vertices"],
                "focus": "Weightless 4D liquid chrome tesseract frame rotating smoothly above head with mirrored vertices. Anisotropic reflections, ray-traced contact shadows. Opening mouth triggers gravitational shockwave ripple warping ambient reflections; smiling flashes prismatic chromatic aberration rings along cheek contours. Y3K surrealism, zero strobing.",
                "primary_trigger": "MouthOpen (Gravitational shockwave ripple warping reflections) / Smile (Prismatic chromatic aberration cheek rings)",
                "visual_hook": "Weightless 4D liquid chrome tesseract rotates hypnotic above head, warping ambient light in real-time."
            },
            {
                "id": "liquid_titanium_spikes",
                "name": "Liquid Titanium Spire Horns & Molten Droplets",
                "signature_tokens": ["titanium spires", "molten droplets", "surface tension", "liquid horns"],
                "focus": "Sculpted liquid titanium spires rising weightlessly from head and temples, undulating with fluid surface tension. PBR metallic reflections with 3-point contrast 6500K rim lighting. Opening mouth releases floating orbit of reflective molten titanium spheres; smiling pulses fluid magnetic ripple waves through horn geometry. Pure zero-G aesthetics, zero strobing.",
                "primary_trigger": "MouthOpen (Floating orbit of reflective molten titanium spheres) / Smile (Fluid magnetic ripple wave through spires)",
                "visual_hook": "Molten titanium spires rise from temples with undulating surface tension, releasing floating chrome spheres on mouth open."
            },
            {
                "id": "cyber_chitin_exoshell",
                "name": "Iridescent Chrome Chitin Brow & Prismatic Sheen",
                "signature_tokens": ["chitin brow", "exoshell", "toroidal ring", "beetle-wing"],
                "focus": "Organic bio-surreal polished chrome brow shell with fluid beetle-wing iridescence fitted to forehead. PBR ray-traced shadows. Opening mouth releases expanding toroidal liquid mercury ring surging forward; smiling triggers radiant rainbow chromatic dispersion wave across face contours. High-concept Y3K.",
                "primary_trigger": "MouthOpen (Expanding toroidal liquid mercury ring surge) / Smile (Rainbow chromatic dispersion wave across face)",
                "visual_hook": "Surreal iridescent chrome chitin plating contours the brow, firing an expanding liquid mercury toroidal ring on mouth open."
            },
            {
                "id": "vortex_singularity_halo",
                "name": "Liquid Platinum Vortex Halo & Event Horizon Sheen",
                "signature_tokens": ["vortex halo", "singularity halo", "platinum accretion", "event horizon"],
                "focus": "Swirling zero-G liquid platinum accretion disc floating above hairline with dark mirrored core. Anisotropic mirror shaders catching studio lighting. Opening mouth emits miniature orbiting mercury droplets spiraling inward; smiling triggers fluid chrome surface wave expanding outward across cheeks. Surreal kinetic art.",
                "primary_trigger": "MouthOpen (Miniature mercury droplets spiraling inward to vortex) / Smile (Fluid chrome surface wave expanding across cheeks)",
                "visual_hook": "Mesmerizing zero-G liquid platinum vortex floats over hairline, pulling shimmering mercury droplets inward."
            },
            {
                "id": "quantum_mercury_droplets",
                "name": "Floating Zero-G Mercury Orb Field & Chrome Spikes",
                "signature_tokens": ["quantum mercury", "orb field", "droplet field", "mercury constellation"],
                "focus": "Suspended constellation of zero-G liquid mercury droplets hovering around temples and brow with fluid surface tension. Opening mouth surges droplets together into an undulating chrome headpiece; smiling shatters geometry into a shimmering cloud of mirror-finish micro-spheres. Seamless physics AR, zero strobing.",
                "primary_trigger": "MouthOpen (Zero-G droplets merge into undulating chrome headpiece) / Smile (Geometry shatters into shimmering micro-spheres)",
                "visual_hook": "Dozens of weightless liquid mercury droplets hover around temples, snapping into a sculpted chrome crown on mouth open."
            }
        ]
    }
}

# Retain backward compatibility for legacy imports
ACCOUNT_PERSONAS = {
    aid: {
        "channel": spec["channel_name"],
        "genre": spec["genre"],
        "theme_focus": spec["archetypes"][0]["focus"],
        "primary_trigger": spec["archetypes"][0]["primary_trigger"],
        "tag_pool": spec["tag_pool"]
    }
    for aid, spec in CHANNEL_PROMPT_MATRICES.items()
}


# ==============================================================================
# STRICT DEDUPLICATION & ANTI-REPETITION ENGINE
# ==============================================================================
def load_published_history(history_file="published_lenses.json"):
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def select_channel_archetype(account_id: str, history: list) -> tuple:
    """
    Analyzes publication history for this account and deterministically selects the
    least-recently-used archetype to guarantee 100% rotating diversity.
    Returns: (selected_archetype_dict, banned_recent_nouns)
    """
    spec = CHANNEL_PROMPT_MATRICES.get(str(account_id), CHANNEL_PROMPT_MATRICES["1"])
    archetypes = spec["archetypes"]
    acc_lenses = [x for x in history if str(x.get("account_id")) == str(account_id)]

    counts = {a["id"]: 0 for a in archetypes}
    last_timestamps = {a["id"]: "" for a in archetypes}

    for lens in acc_lenses:
        full_text = (lens.get("lens_name", "") + " " + lens.get("prompt", "")).lower()
        ts = lens.get("timestamp", "")
        for a in archetypes:
            if any(tok in full_text for tok in a["signature_tokens"]):
                counts[a["id"]] += 1
                if ts > last_timestamps[a["id"]]:
                    last_timestamps[a["id"]] = ts

    min_count = min(counts.values())
    tied = [a for a in archetypes if counts[a["id"]] == min_count]
    # Tie-break by oldest timestamp ('' is oldest)
    selected = min(tied, key=lambda a: last_timestamps[a["id"]])

    # Extract nouns from the most recent 3 lenses of this account to dynamically ban
    banned_nouns = set()
    for lens in acc_lenses[-3:]:
        title = lens.get("lens_name", "")
        for word in re.findall(r'[A-Za-z]{4,}', title):
            w_lower = word.lower()
            if w_lower not in ["halo", "lens", "crown", "face"]:
                banned_nouns.add(w_lower)

    return selected, list(banned_nouns)


def compute_token_jaccard(text1: str, text2: str) -> float:
    stops = {
        "a", "an", "the", "and", "or", "with", "of", "to", "in", "on", "for", "at",
        "by", "from", "is", "its", "user", "head", "face", "3d", "pbr", "zero"
    }
    t1 = set(re.findall(r'[a-zA-Z0-9]+', text1.lower())) - stops
    t2 = set(re.findall(r'[a-zA-Z0-9]+', text2.lower())) - stops
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


def sanitize_lens_prompt(prompt: str) -> str:
    """
    Pre-flight Prompt Sanitizer:
    Scrubs forbidden tokens (e.g. 'frequency bars', 'orbiting bars', 'equalizer crown',
    'spectrum rings', 'canvas', 'tween', 'easing') and replaces them with pure 3D mesh / particle equivalents.
    Guarantees zero-slop, compliance-safe prompt within character boundaries.
    """
    if not prompt:
        return prompt

    sanitized = prompt

    # Ordered mapping: specific compound patterns first, then generic tokens
    replacements = [
        # Compound spinner and bar patterns -> 3D particles and volumetric mesh
        (r'\b(?:orbiting|spinning|rotating)\s+(?:audio-reactive\s+|frequency\s+|sound\s+|spectrum\s+)?(?:bars?|rings?)\b', 'floating 3D volumetric particle rings'),
        (r'\b(?:equalizer|frequency|audio-reactive|sound\s+visualizer)\s+bars?\b', 'kinetic 3D particle filaments'),
        (r'\b(?:equalizer|frequency)\s+(?:crown|tiara|diadem)\b', 'sculpted 3D geometric crystal crown'),
        (r'\b(?:spectrum|sound\s+visualizer)\s+rings?\b', 'chromatic 3D particle halo'),
        (r'\b(?:equalizer|frequency)\s+halos?\b', 'pulsing 3D particle halo'),
        (r'\bequalizer\b', 'kinetic resonance'),
        (r'\bfrequency\s+bars?\b', 'volumetric 3D light pulse rings'),
        (r'\borbiting\s+bars?\b', 'floating 3D volumetric particle rings'),

        # Canvas API and 2D elements -> 3D mesh / viewport equivalents
        (r'\bcanvas\s*api\b', '3D mesh engine'),
        (r'\b(?:2d\s+)?canvas\s+spinners?\b', '3D particle shockwaves'),
        (r'\b2d\s+spinners?\b', '3D particle bursts'),
        (r'\b2d\s+canvas\b', '3D viewport'),
        (r'\bcanvas\b', '3D viewport'),

        # Runtime crashers: TWEEN and Easing curves -> instant / discrete triggers
        (r'\b(?:smooth\s+)?tween(?:ing)?\b', 'instant transition'),
        (r'\b(?:easing|bezier)\s+curves?\b', 'discrete particle bursts'),
        (r'\b(?:ease-in|ease-out)\b', 'linear trigger'),

        # Slop & UI keywords
        (r'\bgeneric\s+purple\s+gradient\b', 'rich anisotropic metallic sheen'),
        (r'\bfloating\s+(?:disembodied\s+)?blobs?\b', 'sculpted 3D geometry'),
        (r'\brubbery\s+plastic\b', 'anisotropic brushed titanium'),
        (r'\b(?:developer\s+)?ui\s+sliders?\b', 'face event triggers'),
        (r'\btap\s+to\s+start\b', 'automatic face detection'),
    ]

    for pattern, subst in replacements:
        sanitized = re.sub(pattern, subst, sanitized, flags=re.IGNORECASE)

    # Normalize whitespace and clean up double punctuation
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    sanitized = re.sub(r'\s+([,.;])', r'\1', sanitized)
    sanitized = re.sub(r',+', ',', sanitized)
    sanitized = re.sub(r'\.+', '.', sanitized)

    # Boundary enforcement: ensure under 460 chars
    if len(sanitized) > 460:
        cutoff = sanitized[:455].rfind('.')
        if cutoff > 280:
            sanitized = sanitized[:cutoff + 1]
        else:
            cutoff_space = sanitized[:455].rfind(' ')
            if cutoff_space > 280:
                sanitized = sanitized[:cutoff_space].rstrip(',;.') + '.'
            else:
                sanitized = sanitized[:457] + '...'

    return sanitized


def validate_candidate_concept(candidate: dict, account_id: str, history: list, banned_nouns: list) -> tuple:
    """
    Validates candidate lens concept against 7 strict quality and anti-repetition rules.
    Returns: (is_valid: bool, reason: str)
    """
    # Pre-flight sanitization before validation
    candidate["prompt"] = sanitize_lens_prompt(candidate.get("prompt", ""))
    prompt = candidate.get("prompt", "")
    lens_name = candidate.get("lens_name", "")

    # Rule 1: Length boundaries (150 - 480)
    if len(prompt) > 480:
        return False, f"Prompt length {len(prompt)} exceeds 480 chars"
    if len(prompt) < 150:
        return False, f"Prompt length {len(prompt)} is too short"

    # Rule 2: JS Engine Safety (Zero TWEEN / Easing curves)
    if re.search(r'\b(tween|easing|bezier|ease-in|ease-out)\b', prompt, re.I):
        return False, "Contains forbidden easing/TWEEN terminology causing runtime crash"

    # Rule 3: Anti-Slop (Zero UI, Zero Sliders, Zero Purple Blobs)
    if re.search(r'\b(slider|button|menu|tap to start|purple gradient|floating blob)\b', prompt, re.I):
        return False, "Contains banned generic slop or developer UI keywords"

    # Rule 4: Head/Face Anchoring requirement
    if not re.search(r'\b(head|face|forehead|temple|brow|eyes|cheeks|hairline|crown)\b', prompt, re.I):
        return False, "Missing mandatory front-camera head/face anchoring specification"

    # Rule 5: Cross-Account Title Deduplication
    title_words = set(re.findall(r'[a-zA-Z0-9]+', lens_name.lower()))
    for item in history:
        prev_title = item.get("lens_name", "")
        if prev_title.lower() == lens_name.lower():
            return False, f"Exact duplicate title matches existing lens: '{prev_title}'"
        prev_words = set(re.findall(r'[a-zA-Z0-9]+', prev_title.lower()))
        if title_words and prev_words:
            overlap = len(title_words & prev_words) / len(title_words | prev_words)
            if overlap > 0.50:
                return False, f"Title '{lens_name}' has {overlap:.0%} overlap with existing '{prev_title}'"

    # Rule 6: Account History Jaccard Similarity (Max 0.48)
    acc_lenses = [x for x in history if str(x.get("account_id")) == str(account_id)]
    for prev in acc_lenses[-5:]:
        sim = compute_token_jaccard(prompt, prev.get("prompt", ""))
        if sim > 0.48:
            return False, f"Prompt has {sim:.0%} similarity with recent lens '{prev.get('lens_name')}'"

    # Rule 7: Zero 2D Canvas / Spinner phrases
    banned_spinner_tokens = [
        "orbiting bars", "frequency bars", "equalizer crown", "spectrum rings",
        "equalizer bars", "audio-reactive bars", "sound visualizer rings",
        "rotating bars", "spinning bars", "equalizer halo", "frequency halo",
        "canvasapi", "canvas api"
    ]
    if any(tok in prompt.lower() for tok in banned_spinner_tokens):
        return False, "Contains banned 2D canvas spinner or frequency bar keywords"

    return True, "Valid"


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
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        clean_text = match.group(0)
        try:
            return json.loads(clean_text, strict=False)
        except Exception:
            pass

    # Order-independent regex fallback: captures string properties cleanly
    res = {}
    for key in ["lens_name", "prompt", "visual_hook", "trigger_sequence"]:
        m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if m:
            val = m.group(1).encode('utf-8').decode('unicode_escape', errors='ignore')
            res[key] = val.replace("\n", " ").strip()
        else:
            m2 = re.search(rf'"{key}"\s*:\s*"(.*?)"\s*,\s*"(?:lens_name|prompt|tags|visual_hook|trigger_sequence)"', text, re.DOTALL)
            if m2:
                res[key] = m2.group(1).replace("\n", " ").strip()

    tags_m = re.search(r'"tags"\s*:\s*\[(.*?)\]', text, re.DOTALL)
    if tags_m:
        res["tags"] = [re.sub(r'["\x27]', '', t).strip() for t in tags_m.group(1).split(",") if t.strip()]
    else:
        res["tags"] = []

    if "lens_name" in res and "prompt" in res:
        return res

    raise ValueError(f"Could not parse valid JSON from output: {text[:200]}...")


# ==============================================================================
# MAIN PROMPT GENERATOR
# ==============================================================================
def generate_lens_prompt(account_id: str = "1", custom_instructions: str = "") -> dict:
    aid = str(account_id)
    spec = CHANNEL_PROMPT_MATRICES.get(aid, CHANNEL_PROMPT_MATRICES["1"])
    history = load_published_history("published_lenses.json")
    selected_archetype, banned_nouns = select_channel_archetype(aid, history)

    api_keys = get_gemini_api_keys()

    dials = spec["craft_dials"]
    dials_str = (
        f"DESIGN_VARIANCE: {dials['design_variance']:.2f} (High architectural novelty)\n"
        f"VISUAL_DENSITY: {dials['visual_density']:.2f} (Rich PBR textures, caustic shaders, 3-point contrast lighting)\n"
        f"MOTION_INTENSITY: {dials['motion_intensity']:.2f} (Kinetic face-event responses)"
    )

    system_prompt = (
        "You are an Elite Snapchat AR Director and Principal Prompt Engineer for Snapchat EasyLens (Lens Studio Web SnapML/AILC).\n"
        "Your mission is to engineer an insanely high-quality, anti-slop, compliance-verified Lens prompt.\n\n"
        "STRICT PRODUCTION QUALITY & COMPLIANCE RULES:\n"
        "1. ZERO ON-SCREEN DEVELOPER UI, SLIDERS, OR BUTTONS: The lens must be 100% immersive full-screen camera AR. NEVER generate touch sliders, debug menus, or controller UI widgets.\n"
        "2. ZERO ON-SCREEN TEXT, LABELS, WATERMARKS, OR GREETINGS: Do NOT render any text, subtitles, greetings, watermarks, or score counters on screen.\n"
        "3. BANNED SLOP: Generic purple gradients, floating disembodied blobs, rubbery plastic textures, and 2D canvas spinners.\n"
        "4. MANDATORY PBR CRAFT: Physically Based Rendering materials (anisotropic brushed titanium, liquid mercury, 24k gold leaf, refractive optical glass, subsurface scattering).\n"
        "5. MANDATORY 3-POINT CONTRAST LIGHTING: Key light + contrasting 6500K/2800K directional rim lighting + ray-traced contact shadows.\n"
        "6. MANDATORY FRONT-CAMERA SELFIE ANCHORING: Primary 3D asset MUST anchor directly to HEAD or FACE (forehead, hairline, temples, cheekbones, or brow). NEVER attach to shoulders or full-body. NEVER occlude mouth on mouth-trigger lenses.\n"
        "7. STRICT JAVASCRIPT ENGINE COMPATIBILITY (ZERO TWEEN / ZERO EASING CURVES):\n"
        "   - NEVER use the words 'smooth tween', 'bezier curve', 'ease-in', 'ease-out', or 'easing curve'. Use discrete visual triggers and particle streams only.\n"
        "8. STRICT PROMPT LENGTH CONSTRAINT: The 'prompt' field MUST be under 460 characters (hard backend limit is 480).\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "lens_name": "Unique 2-4 word Title without trademarked terms",\n'
        '  "prompt": "Dense, single-paragraph EasyLens prompt between 300 and 460 characters",\n'
        '  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],\n'
        '  "visual_hook": "1-line explanation of the 0.2s psychological hook",\n'
        '  "trigger_sequence": "1-line explanation of the face-trigger interaction"\n'
        "}"
    )

    recent_fleet_lines = [
        f"- '{item.get('lens_name')}' (Acc #{item.get('account_id')}): {item.get('visual_hook', '')}"
        for item in history[-12:]
    ]

    user_prompt = (
        f"TARGET ACCOUNT: Account #{aid} ({spec['channel_name']})\n"
        f"GENRE: {spec['genre']}\n"
        f"ASSIGNED ROTATING ARCHETYPE: {selected_archetype['name']}\n"
        f"ARCHETYPE PROMPT SEED: {selected_archetype['focus']}\n"
        f"PRIMARY TRIGGER MECHANISM: {selected_archetype['primary_trigger']}\n\n"
        f"CRAFT DIALS:\n{dials_str}\n\n"
        f"FORBIDDEN CROSS-CONTAMINATION (STRICT FIREWALL FOR THIS CHANNEL):\n"
        f"Strictly DO NOT include any elements of: {', '.join(spec['forbidden_cross_contamination'])}\n\n"
    )

    if banned_nouns:
        user_prompt += (
            f"DYNAMIC ANTI-REPETITION CONSTRAINT: Do NOT use or reuse the words {list(banned_nouns)} "
            "in the title or prompt, as they were used in recent lenses for this channel. Synthesize fresh nomenclature!\n\n"
        )

    if recent_fleet_lines:
        user_prompt += (
            "RECENTLY PUBLISHED FLEET LENSES (CRITICAL: DO NOT DUPLICATE THESE TITLES OR VISUAL HOOKS):\n"
            + "\n".join(recent_fleet_lines) + "\n\n"
        )

    if custom_instructions:
        user_prompt += f"SPECIAL INSTRUCTIONS: {custom_instructions}\n"

    user_prompt += (
        "Generate a fresh, stunning, distinctive concept that matches the assigned rotating archetype while feeling completely unique. "
        "Strictly ensure prompt length is between 300 and 460 characters."
    )

    # Static fallback prepared in case of complete API failure
    static_fallback = {
        "lens_name": selected_archetype["name"].split("&")[0].strip(),
        "prompt": sanitize_lens_prompt(selected_archetype["focus"]),
        "tags": spec["tag_pool"],
        "visual_hook": selected_archetype["visual_hook"],
        "trigger_sequence": selected_archetype["primary_trigger"],
        "archetype": selected_archetype["id"],
        "craft_dials": dials
    }

    if not api_keys:
        print("[GEMINI WARN] No Gemini API keys found. Returning archetype-matched static fallback.")
        return static_fallback

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.75,
            "maxOutputTokens": 2048
        }
    }

    last_err = None
    for model_name in CANDIDATE_MODELS:
        for key in api_keys[:3]:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            try:
                print(f"[GEMINI] Trying model {model_name} for Acc #{aid} ({selected_archetype['id']})...")
                res = requests.post(url, json=payload, timeout=35)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    result = extract_json(raw_text)
                    result["prompt"] = sanitize_lens_prompt(result.get("prompt", ""))

                    # Post-validation
                    valid, reason = validate_candidate_concept(result, aid, history, banned_nouns)
                    if not valid:
                        print(f"[GEMINI RETRY] Generated concept failed validation: {reason}. Healing prompt...")
                        if "exceeds 480" in reason and len(result.get("prompt", "")) > 470:
                            p = result["prompt"]
                            cutoff = p[:460].rfind(".")
                            if cutoff > 280:
                                result["prompt"] = p[:cutoff + 1]
                            else:
                                result["prompt"] = p[:457] + "..."
                            result["prompt"] = sanitize_lens_prompt(result["prompt"])
                            valid, reason = validate_candidate_concept(result, aid, history, banned_nouns)

                    if valid:
                        result["archetype"] = selected_archetype["id"]
                        result["craft_dials"] = dials
                        print(f"[GEMINI OK] Model: {model_name}")
                        print(f"[GEMINI OK] Generated Lens: {result.get('lens_name')}")
                        print(f"[GEMINI OK] Archetype: {selected_archetype['id']}")
                        print(f"[GEMINI OK] Prompt ({len(result.get('prompt', ''))}c): {result.get('prompt')}")
                        return result
                    else:
                        print(f"[GEMINI WARN] Validation rejected candidate: {reason}")
                else:
                    last_err = f"{res.status_code}: {res.text}"
                    print(f"[GEMINI WARN] Model {model_name} returned {res.status_code}")
                    time.sleep(1)
            except Exception as e:
                last_err = str(e)
                print(f"[GEMINI WARN] Request exception: {e}")
                time.sleep(1)

    print(f"[GEMINI WARN] All Gemini requests exhausted ({last_err}). Falling back to archetype static fallback.")
    return static_fallback


if __name__ == "__main__":
    acc = sys.argv[1] if len(sys.argv) > 1 else "1"
    output = generate_lens_prompt(acc)
    print(json.dumps(output, indent=2))
