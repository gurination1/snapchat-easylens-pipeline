import os
import sys
import json
import time
import re
import requests

CANDIDATE_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
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
        "genre": "Mythological Beasts, Celestial Crowns, Ghibli Spirit Realms & Elemental Breath",
        "craft_dials": {
            "design_variance": 0.88,
            "visual_density": 0.92,
            "motion_intensity": 0.90
        },
        "forbidden_cross_contamination": ['cyberpunk HUD', 'neon visors', 'crying memes', 'cartoon stormcloud', 'modern sunglasses', 'cheap 2D stickers', 'canvas spinners', 'developer UI sliders'],
        "tag_pool": ['dragon', 'phoenix', 'mythology', 'ghibli', 'headpiece', 'crown', 'fantasy', 'pbr'],
        "archetypes": [
            {
                "id": "dragon_pyrodrake",
                "name": "Obsidian Dragon Crown & Emerald Pyro-Torrent",
                "signature_tokens": ['dragon', 'wyvern', 'pyrodrake', 'dragon horn'],
                "focus": "Sculpted obsidian dragon horn crown anchored to temples with liquid 24k gold filigree and caustic ruby gems, PBR anisotropic metallic reflections, 3-point contrast 6500K/2800K lighting. Opening mouth erupts turbulent emerald flame torrent with floating amber sparks; smiling ignites golden runic eye halos; eyebrow raise summons swirling dragon ember corona; head tilt flares ruby horns. Zero strobing, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Obsidian Dragon Crown frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "phoenix_solar",
                "name": "Phoenix Solar Diadem & Blinding Plumage Shockwave",
                "signature_tokens": ['phoenix', 'firebird', 'solar diadem', 'solar plasma'],
                "focus": "Sculpted molten 24k rose-gold phoenix diadem fitted to hairline with radiant solar ember crest. PBR feathered iridescent wings contouring temples with subsurface scattering and 3-point contrast rim lighting. Opening mouth unleashes blinding solar plasma plumage burst; smiling triggers brilliant sun-flare corona around brow; eyebrow raise ignites blazing golden crest feathers; head tilt showers golden ash motes. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Phoenix Solar Diadem frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "valkyrie_aurora",
                "name": "Valkyrie Winged Helm & Frosted Aurora Mist",
                "signature_tokens": ['valkyrie', 'winged circlet', 'aurora borealis', 'frosted arctic'],
                "focus": "Brushed silver and iridescent mother-of-pearl Valkyrie winged circlet fitted firmly to forehead. Photorealistic PBR metal reflections with frosted runic engravings and cool 6500K Nordic key lighting. Opening mouth summons ethereal soaring spectral raven aura and frosted arctic mist; smiling ignites crystalline glacial eye glints; eyebrow raise activates radiant aurora borealis crown; head tilt ripples frosted mist. Zero strobing.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Valkyrie Winged Helm frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "celestial_kitsune",
                "name": "Celestial Kitsune Mask & Azure Spirit Foxfire",
                "signature_tokens": ['kitsune', 'foxfire', 'spirit fox', 'vermilion lacquer'],
                "focus": "Carved porcelain and vermilion lacquer kitsune forehead crest anchored strictly to brow, leaving eyes and mouth clear. Shimmering spirit bells and twin floating foxfire tails contouring jawline. Opening mouth erupts swirling azure spirit flame orbs with dynamic volumetric embers; smiling reveals ethereal golden fox spirit eye reflections; eyebrow raise flashes crimson fox spirit runes; head tilt sways foxfire tails. Pure PBR craft, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Celestial Kitsune Mask frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "anubis_eclipse",
                "name": "Anubis Jackal Coronet & Swirling Sandstorm Vortex",
                "signature_tokens": ['anubis', 'jackal coronet', 'sandstorm vortex', 'hieroglyphic'],
                "focus": "Anubis matte black basalt and electrum jackal coronet fitted securely to crown and temples with glowing lapis lazuli inlays. 3-point contrast 2800K desert key light with ray-traced contact shadows. Opening mouth triggers swirling golden sandstorm vortex; smiling aligns glowing solar eclipse halo behind crown; eyebrow raise ignites piercing lapis lazuli gaze; head tilt sways desert hieroglyphic embers. Pure PBR craft, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Anubis Jackal Coronet frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "leviathan_frost",
                "name": "Leviathan Abyssal Coronet & Glacial Geyser",
                "signature_tokens": ['leviathan', 'abyssal coronet', 'frost serpent', 'cryo-crystals'],
                "focus": "Deep ocean Leviathan serpent horns sculpted from anisotropic sapphire ice and electrum filigree anchored to brow. PBR metallic reflections with ray-traced contact shadows. Opening mouth unleashes pressurized sub-zero frost geyser with floating cryo-crystals; smiling ignites piercing runic blue gaze flares; eyebrow raise expands frost geyser shockwave; head tilt ripples abyssal ice caustics. Depth occlusion enabled, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Leviathan Abyssal Coronet frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "ghibli_spirit_cloud",
                "name": "Ghibli Studio Anime Watercolor Cloud Crown & Floating Spirit Dust",
                "signature_tokens": ['ghibli', 'watercolor', 'anime cloud', 'spirit dust', 'spirit serpent', 'serpent'],
                "focus": "Hand-painted Ghibli-inspired watercolor cloud crown resting above hairline with floating soot spirit dust and celestial spirit serpent coils. Soft gouache textures with warm 2800K highlights. Opening mouth erupts swirling sakura petal cyclone; smiling spawns cheerful soot sprites around temples; eyebrow raise flashes golden sky halo; head tilt sways floating spirit dust. Pure 3D PBR fantasy craft, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Ghibli Studio Anime Watercolor Cloud Crown frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "gorgon_aegis",
                "name": "Obsidian Gorgon Viper Crest & Petrifying Gaze",
                "signature_tokens": ['gorgon', 'viper crest', 'petrifying mist', 'bronze serpents'],
                "focus": "Regal basalt and bronze Gorgon viper tiara fitted across forehead, micro-scaled serpents undulating with ray-traced shadows. PBR metallic luster and warm rim light. Opening mouth summons swirling emerald petrification mist with floating basalt dust; smiling flashes brilliant golden serpentine eye glints; eyebrow raise awakens glowing emerald viper fangs; head tilt ripples serpentine crown. Seamless head tracking, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Obsidian Gorgon Viper Crest frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "chimera_infernal",
                "name": "Infernal Chimera Horned Helm & Magma Sparks",
                "signature_tokens": ['chimera', 'infernal helm', 'magma sparks', 'meteoric iron'],
                "focus": "Polished meteoric iron and electrum Chimera horned circlet fitted to head and temples with smoldering obsidian plates. 3-point contrast lighting with ray-traced shadows. Opening mouth erupts volcanic magma sparks and billowing crimson embers; smiling awakens radiant molten gold fissure lines running along cheekbones; eyebrow raise ignites smoldering horned crest; head tilt showers molten sparks. Pure PBR fantasy craft, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Infernal Chimera Horned Helm frames the face with rich PBR luster in 0.2s."
            },
            {
                "id": "garuda_celestial",
                "name": "Celestial Garuda Feathered Crown & Divine Gale",
                "signature_tokens": ['garuda', 'feathered crown', 'divine gale', 'sacred lotus'],
                "focus": "Sculpted 24k beaten gold Garuda crest with iridescent feathered plumes contouring brow and temples. Soft celestial rim lighting and subsurface scattering. Opening mouth unleashes swirling divine gale vortex with floating golden sacred lotus petals; smiling triggers blinding golden solar beam flares from brow; eyebrow raise flares radiant golden wingtips; head tilt sways sacred lotus petals. Pure PBR craft, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Massive visual impact: bold 3D Celestial Garuda Feathered Crown frames the face with rich PBR luster in 0.2s."
            }
        ]
    },
    "2": {
        "channel_name": "SciFi_Optics",
        "genre": "Cyberpunk HUD Eyewear, 90s Cyber Camcorder VHS Glitch & Kinetic Retinal Scanners",
        "craft_dials": {
            "design_variance": 0.85,
            "visual_density": 0.90,
            "motion_intensity": 0.85
        },
        "forbidden_cross_contamination": ['2D canvas spinners', 'flat screen overlays', 'dragons', 'mythical beasts', 'cartoon crying clouds', 'gold baroque filigree', 'medieval helmets', 'crying memes', 'developer UI sliders'],
        "tag_pool": ['cyberpunk', 'visor', 'camcorder', 'vhs', 'optics', 'hud', 'scifi', 'pbr'],
        "archetypes": [
            {
                "id": "titanium_holo_visor",
                "name": "Brushed Titanium Holo-Visor & Radial Shockwave",
                "signature_tokens": ['visor', 'holo-visor', 'laser shockwave'],
                "focus": "Ergonomic cyberpunk holo-visor resting strictly across eyes leaving cheeks and mouth clear for tracking. Brushed titanium frame with pulsing cyan neon edge emission, PBR anisotropic reflections, and ray-traced shadows. Opening mouth triggers radial laser particle shockwave; smiling illuminates glowing neon visor frame rim; eyebrow raise activates high-intensity laser focus ring; head tilt shifts cyan neon edge glow. Zero UI. Pure 3D assets only.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Brushed Titanium Holo-Visor locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "cybernetic_ocular_scanner",
                "name": "Cybernetic Ocular Scanner & Holographic Wireframe",
                "signature_tokens": ['ocular scanner', 'scanner', 'monocle', 'ocular', 'optics'],
                "focus": "Asymmetrical carbon fiber and tungsten ocular optic anchored over left eye orbital bone and brow, leaving face and mouth unobstructed. Multi-layered refractive cyan glass lenses with micro-servo details. Opening mouth projects floating 3D wireframe mesh orb; smiling pulses glowing emerald light through lenses; eyebrow raise projects prismatic targeting ring; head tilt rotates ocular lenses. PBR materials, zero text.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Cybernetic Ocular Scanner locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "neon_speed_goggles",
                "name": "Neon Speed-Optic Goggles & Chromatic Hyperdrive",
                "signature_tokens": ['goggles', 'speed-optic', 'hyperdrive', 'racer'],
                "focus": "Ultra-lightweight matte-black alloy speed-optic goggles fitted across brow and nose bridge. Features illuminated amber and electric blue neon optical rings with refractive glass prism elements. PBR metallic shaders with ray-traced shadows. Opening mouth triggers hyperdrive chromatic warp streak particle bursts; smiling pulses warm amber glow across frame; eyebrow raise flashes dual neon prism beam; head tilt shifts blue optic rings. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Neon Speed-Optic Goggles locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "cyber_camcorder_vhs",
                "name": "90s Cyber Camcorder Visor & VHS Glitch Tracking HUD",
                "signature_tokens": ['camcorder', 'vhs glitch', 'cyber visor', 'tracking static', 'timestamp optic'],
                "focus": "Retro-futuristic 90s cyber camcorder visor frame contoured across brow and temples with holographic rec timestamp and magnetic phosphor glass. PBR brushed titanium, cathode-ray scanline reflections. Opening mouth discharges magnetic tape-rip glitch shockwave and RGB chromatic particle split; smiling pulses neon REC battery flare; eyebrow raise flashes amber night-vision beam; head tilt shifts scanlines. Pure 3D AR craft, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech 90s Cyber Camcorder Visor locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "quantum_neural_monocular",
                "name": "Quantum Neural Monocular & Volumetric Hologram",
                "signature_tokens": ['quantum', 'neural monocle', 'monocular', 'planetary hologram'],
                "focus": "Sleek chrome-plated neural monocular optic docked along right temple and cheek with floating quantum focal rings. Anisotropic PBR reflections with deep purple laser prism optics. Opening mouth projects spinning volumetric planetary hologram between eyebrows; smiling triggers high-energy neural pulse wave; eyebrow raise expands quantum focal rings; head tilt sways floating purple prism sparks. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Quantum Neural Monocular locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "tactical_orbital_monocle",
                "name": "Tactical Orbital Monocle & Prismatic Beam",
                "signature_tokens": ['orbital monocle', 'ballistic monocle', 'prismatic beam', 'tactical optic'],
                "focus": "Matte carbon-fiber ballistic monocle anchored over right eye and brow with micro-aperture ring. Anisotropic PBR reflections, ray-traced shadows. Opening mouth projects 3D floating volumetric wireframe ring expanding into space; smiling pulses glowing red optic beam flare across lens; eyebrow raise projects rotating micro-aperture rings; head tilt shifts ballistic carbon reflections. Pure 3D assets, zero screen text.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Tactical Orbital Monocle locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "apex_spectre_visor",
                "name": "Stealth Spectre Prismatic Visor & Sonic Burst",
                "signature_tokens": ['spectre visor', 'stealth visor', 'prismatic glass', 'sonic burst'],
                "focus": "Faceted obsidian and dichroic glass stealth visor contoured across brow and temples. PBR metallic luster with 3-point contrast violet rim highlights and ray-traced contact shadows. Opening mouth emits radial sonic particle shockwave with refractive edge displacement; smiling pulses violet prismatic reflections across glass; eyebrow raise flashes violet stealth edge halo; head tilt shifts dichroic prism colors. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Stealth Spectre Prismatic Visor locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "neural_synapse_cortex",
                "name": "Cybernetic Synapse Brow Frame & Kinetic Pulse",
                "signature_tokens": ['synapse frame', 'brow frame', 'optical conduits', 'kinetic pulse'],
                "focus": "Brushed aerospace aluminum neural bracket fitted firmly to brow with glowing micro-fiber optical conduits. Anisotropic PBR reflections and baked contact shadows. Opening mouth releases kinetic spark wave surging across temples; smiling surges electric blue volumetric particle pulses through optical conduits; eyebrow raise flares glowing brow synapse nodes; head tilt sends pulse waves across conduits. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Cybernetic Synapse Brow Frame locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "subzero_cryo_optics",
                "name": "Cryo-Tactical Ballistic Visor & Frost Vent",
                "signature_tokens": ['cryo optics', 'ballistic visor', 'subzero vent', 'frost jet'],
                "focus": "Cryogenic frosted polymer and tungsten tactical visor resting across eyes leaving mouth clear. PBR materials, subsurface refraction with cool 6500K rim light and ray-traced shadows. Opening mouth vents pressurized volumetric sub-zero cryo particle jets sideways from temples; smiling activates cyan optic lens glow; eyebrow raise crystallizes frost lattice across brow; head tilt swirls sub-zero mist. Zero text.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Cryo-Tactical Ballistic Visor locks onto brow with micro-servo precision in 0.2s."
            },
            {
                "id": "matrix_kinetic_spectacles",
                "name": "Kinetic Titanium Smart Spectacles & Holographic Geometry",
                "signature_tokens": ['smart spectacles', 'titanium spectacles', 'wireframe cubes', 'holographic geometry'],
                "focus": "Precision titanium wireframe smart spectacles docked to face, nose and brow with transparent optical prisms. Anisotropic reflections and ray-traced shadows. Opening mouth discharges floating 3D volumetric wireframe cubes expanding forward; smiling pulses high-speed emerald photon glints through lenses; eyebrow raise projects geometric laser matrix across brow; head tilt rotates floating wireframe cubes. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Futuristic silhouette: high-tech Kinetic Titanium Smart Spectacles locks onto brow with micro-servo precision in 0.2s."
            }
        ]
    },
    "3": {
        "channel_name": "WarpShock_Comedy",
        "genre": "Viral Memes, Meme Melodrama Reactions & Kinetic Karaoke Headpieces",
        "craft_dials": {
            "design_variance": 0.95,
            "visual_density": 0.85,
            "motion_intensity": 0.95
        },
        "forbidden_cross_contamination": ['serious dark fantasy', 'solemn mythic armor', 'luxury haute couture', 'serious tactical military HUD', 'plain static items', 'developer UI sliders'],
        "tag_pool": ['meme', 'crying', 'karaoke', 'funny', 'cartoon', 'comedy', 'viral', 'reaction'],
        "archetypes": [
            {
                "id": "gigachad_jawline_morph",
                "name": "Gigachad Sculpted Jawline Morph & Crimson Laser Gaze",
                "signature_tokens": ['gigachad', 'sculpted jawline', 'laser gaze', 'sigma', 'marble cheekbones'],
                "focus": "Comedic classical Grecian chiseled marble jawline and high cheekbone morph anchoring seamlessly to face. PBR micro-sculpted stone with dramatic chiaroscuro side lighting. Opening mouth triggers hilarious ultra-chiseled chin flex with flashing red laser beam eye glints; smiling triggers gleaming white tooth-twinkle starburst; eyebrow raise sharpens hyper-defined jaw contours; head tilt catches dramatic rim shadows. Viral meme powerhouse, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: instant Gigachad Sculpted Jawline morph detonates hilarious sigma transformation on mouth open."
            },
            {
                "id": "fluffy_crying_stormcloud",
                "name": "Volumetric Cartoon Stormcloud & Liquid Teardrop Geyser",
                "signature_tokens": ['stormcloud', 'cloud', 'mercury teardrop', 'gold coins bouncing'],
                "focus": "Fluffy PBR volumetric cartoon stormcloud anchored directly above head, casting soft contact shadows with 6500K/2800K rim lighting and thunder glow. Opening mouth triggers exaggerated liquid mercury teardrop geyser and spinning 24k gold coins bouncing off camera frame; smiling triggers warm comical lightning flash; eyebrow raise rumbles cartoon thundercloud; head tilt drops gentle rain shower. Zero strobe, safe performance.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Volumetric Cartoon Stormcloud detonates comical chaos on mouth open."
            },
            {
                "id": "soap_opera_melodrama",
                "name": "Meme Melodrama Waterfall Tears & Gold Coin Shower",
                "signature_tokens": ['soap-opera', 'melodrama', 'waterfall tears', 'broken-heart', 'theatre crown', 'coins'],
                "focus": "Wearable comedic 3D dramatic weeping theatre crown with physical crystalline tear waterfalls cascading comically from eyes across cheeks. PBR water caustics with soft romantic halo lighting. Opening mouth erupts torrential twin weeping waterfalls, broken-heart shards, and spinning 24k gold coin shower; smiling shatters drama into cheerful rainbow confetti; eyebrow raise bulges comic heart eyes; head tilt curves tear streams. Pure comedy AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Meme Melodrama Waterfall Tears detonates comical chaos on mouth open."
            },
            {
                "id": "steam_rage_valve",
                "name": "Cartoon Steam-Whistle Pressure Valve & Rainbow Exhaust",
                "signature_tokens": ['steam-whistle', 'steam plumes', 'boiler valve', 'rage whistle'],
                "focus": "Comic stylized PBR polished brass steam boiler pressure valve mounted securely to forehead with vibrating needle gauge. 3-point warm lighting with baked shadows. Opening mouth releases explosive pressurized cartoon steam clouds blasting from ears with comic red face flush; smiling vents gentle harmless rainbow bubble streams; eyebrow raise pops valve cap with fiery sparks; head tilt rattles valve vigorously. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Cartoon Steam-Whistle Pressure Valve detonates comical chaos on mouth open."
            },
            {
                "id": "laughing_gold_skull",
                "name": "Mini Laughing Golden Skull & Mega Confetti Cannon",
                "signature_tokens": ['laughing skull', 'confetti cannon', 'skull mascot'],
                "focus": "Stylized 3D polished 24k gold cartoon skull mascot hovering cheerfully above right shoulder and tilting with head movements. Opening mouth activates giant comic gold confetti cannon blasting party streamers and laughing emoji sparks; smiling triggers comical golden tooth-twinkle starburst; eyebrow raise makes skull mascot do backflips; head tilt synchronizes skull bobbing. Pure infectious joy, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Mini Laughing Golden Skull detonates comical chaos on mouth open."
            },
            {
                "id": "hypno_spiral_shockwave",
                "name": "Pop-Out Spiral Hypno-Goggles & Cartoon Exclamation Sparks",
                "signature_tokens": ['spiral hypno', 'hypno-goggles', 'pop-out', 'exclamation marks'],
                "focus": "Exaggerated 3D glowing cartoon spiral hypno-goggles anchored over eyes that comical stretch and pop forward 10cm on face trigger. PBR stylized materials with ray-traced contact shadows. Opening mouth triggers shockwave rings with floating animated comic exclamation marks and question stars; smiling snaps goggles back with kaleidoscope optic swirl; eyebrow raise expands spiral rings; head tilt wiggles spring frames. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Pop-Out Spiral Hypno-Goggles detonates comical chaos on mouth open."
            },
            {
                "id": "jawdrop_coin_cascade",
                "name": "Cartoon Jaw-Drop Spring & Gold Coin Cascade",
                "signature_tokens": ['jaw-drop', 'spring chin', 'coin cascade', 'bulging eyes'],
                "focus": "Exaggerated 3D mechanical cartoon spring chin and bulging cartoon eyes anchored to face. 3-point comic lighting with ray-traced shadows. Opening mouth triggers hilarious jaw-drop extension unleashing cascading fountain of spinning 24k gold coins and comic exclamation sparks; smiling pops eyes back with comical starburst glints; eyebrow raise springs eyes forward 20cm; head tilt bounces spring chin. Pure viral comedy AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Cartoon Jaw-Drop Spring detonates comical chaos on mouth open."
            },
            {
                "id": "dramatic_anime_tears",
                "name": "Anime Torrential Weeping Jets & Rainbow Arc",
                "signature_tokens": ['anime tears', 'weeping jets', 'water torrents', 'rainbow arc'],
                "focus": "Stylized oversized crystalline anime tear jets anchored to lower eye contours. PBR liquid reflections and ambient room lighting. Opening mouth unleashes twin high-pressure horizontal water torrents blasting outward with floating broken comic hearts; smiling instantly clears tears into arching 3D rainbow halo over head; eyebrow raise widens tear torrent spray; head tilt bends water stream arcs. Pure comedy AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Anime Torrential Weeping Jets detonates comical chaos on mouth open."
            },
            {
                "id": "mindblown_cosmic_pop",
                "name": "Mind-Blown Pop-Top Head & Galaxy Fireworks",
                "signature_tokens": ['mind-blown', 'pop-top', 'cosmic fireworks', 'lightbulb crown'],
                "focus": "Stylized cartoon skull top-hatch fitted to hairline with bouncing miniature antenna. Anisotropic metallic reflections and baked shadows. Opening mouth pops hatch open with dramatic cartoon mushroom cloud of glowing rainbow star particles and floating comic UFOs; smiling triggers comical golden lightbulb illumination above crown; eyebrow raise wiggles antenna with electric sparks; head tilt tips open hatch. Pure comedy AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Mind-Blown Pop-Top Head detonates comical chaos on mouth open."
            },
            {
                "id": "pepper_fire_breath",
                "name": "Flaming Red Hot Pepper Crown & Comic Fire Jet",
                "signature_tokens": ['hot pepper', 'fire breath', 'chili horns', 'cartoon flame'],
                "focus": "Cartoony glowing red chili pepper horns mounted to temples with sizzling PBR smoke embers. 3-point contrast lighting. Opening mouth blasts giant comic cartoon flame geyser forward with bouncing sweating teardrops; smiling cools face into icy cartoon frost with soothing blue halo sparkles; eyebrow raise ignites sizzling chili pepper tips; head tilt wafts spicy smoke puffs. High-impact viral reaction AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Flaming Red Hot Pepper Crown detonates comical chaos on mouth open."
            },
            {
                "id": "karaoke_lyric_headpiece",
                "name": "Viral Karaoke Kinetic Lyric Headpiece & Bouncing Rhythm Orbs",
                "signature_tokens": ['karaoke', 'lyric headpiece', 'neon notes', 'bouncing balls', 'rhythm orbs'],
                "focus": "Pulsing 3D neon karaoke musical staff headpiece contoured around brow with orbiting treble clef notes and bouncing rhythm sphere balls. PBR emissive neon shaders with 3-point contrast lighting. Opening mouth unleashes explosive pulsing neon musical note shockwave and basswave rings; smiling makes rhythm spheres bounce in tempo across brow; eyebrow raise triggers golden laser chord burst; head tilt sways musical staff. High virality, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral meme reaction: exaggerated 3D Viral Karaoke Kinetic Lyric Headpiece detonates comical chaos on mouth open."
            }
        ]
    },
    "4": {
        "channel_name": "Lumiere_Atelier",
        "genre": "35mm Analog Luxury, High-Fashion Parisian Couture & Golden Hour Aesthetics",
        "craft_dials": {
            "design_variance": 0.82,
            "visual_density": 0.95,
            "motion_intensity": 0.70
        },
        "forbidden_cross_contamination": ['cartoon memes', 'crying coins', 'cyberpunk neon HUDs', 'monster horns', 'cheap plastic stickers', 'grotesque elements', 'developer UI sliders'],
        "tag_pool": ['film', '35mm', 'parisian', 'couture', 'crown', 'gold', 'pearls', 'luxury'],
        "archetypes": [
            {
                "id": "haute_baroque_gold",
                "name": "High-Fashion Parisian Couture 24k Gold Leaf Crown & Freshwater Pearls",
                "signature_tokens": ['baroque', '24k gold leaf', 'freshwater pearl', 'crystal prisms', 'parisian couture', 'portra 400'],
                "focus": "High-fashion Parisian couture 24k gold leaf baroque crown fitted to hairline with draped raw freshwater pearls and caustic crystal prisms. Warm Kodak Portra 400 film grain with halation bloom. Opening mouth triggers radiant champagne spark motes orbiting crown; smiling cascades rich golden sparkle dust across cheekbones; eyebrow raise triggers luminous dewy skin sheen; head tilt catches prismatic diamond dispersion. Pure Parisian luxury, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent High-Fashion Parisian Couture 24k Gold Leaf Crown elevates portrait with 35mm film halation."
            },
            {
                "id": "pearl_celestial_diadem",
                "name": "Freshwater Pearl Celestial Diadem & Golden Hour Sheen",
                "signature_tokens": ['freshwater pearl', 'pearl diadem', 'champagne light motes'],
                "focus": "Floating halo diadem of baroque freshwater pearls and hand-twisted 18k champagne gold wire resting above hairline. Subtle Portra 400 golden-hour film bloom with warm 2800K key light. Opening mouth summons gentle floating champagne light motes around face; smiling illuminates an ethereal high-fashion skin sheen; eyebrow raise flares caustic pearl luster corona; head tilt shifts golden-hour sunbeams across pearls. Ultra-luxury vanity.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Freshwater Pearl Celestial Diadem elevates portrait with 35mm film halation."
            },
            {
                "id": "art_nouveau_tiara",
                "name": "Art Nouveau Emerald Tiara & Prismatic Crystals",
                "signature_tokens": ['art nouveau', 'emerald cabochon', 'prismatic crystal', 'paris couture'],
                "focus": "Art Nouveau floral tiara sculpted from antiqued yellow gold with deep emerald cabochon accents anchored securely to brow. Soft 35mm analog vignette with delicate warm highlights. Opening mouth pulses radiant emerald crystal prism halo above crown; smiling activates emerald light refraction flares across eye contours; eyebrow raise blooms golden floral petals; head tilt glints emerald cabochons. Parisian couture, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Art Nouveau Emerald Tiara elevates portrait with 35mm film halation."
            },
            {
                "id": "champagne_diamond_coronal",
                "name": "Champagne Micro-Faceted Diamond Coronal & Starburst Glints",
                "signature_tokens": ['champagne diamond', 'diamond coronal', 'faceted diamond'],
                "focus": "PBR precision micro-faceted champagne diamond coronal resting tightly along hairline. Anisotropic micro-surface roughness maps catching golden sunlight with realistic chromatic dispersion. Opening mouth emits delicate suspended diamond dust particles orbiting crown; smiling triggers radiant starburst glints across cheekbone highlights; eyebrow raise flares brilliant champagne diamond prism corona; head tilt shifts chromatic dispersion. Zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Champagne Micro-Faceted Diamond Coronal elevates portrait with 35mm film halation."
            },
            {
                "id": "florentine_laurel_wreath",
                "name": "Gilded Florentine Laurel Leaf Wreath & Soft Sunbeams",
                "signature_tokens": ['florentine laurel', 'laurel leaf wreath', 'marble jasmine'],
                "focus": "Hand-hammered 24k gold Florentine laurel leaf wreath contoured to head with miniature carved marble jasmine blossoms. 3-point contrast lighting with golden volumetric god-rays framing silhouette. Opening mouth triggers gentle cascade of golden falling laurel petals; smiling illuminates soft golden-hour cheek glints and warm skin bloom; eyebrow raise flares gilded leaf tips; head tilt sways marble blossoms. Timeless luxury.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Gilded Florentine Laurel Leaf Wreath elevates portrait with 35mm film halation."
            },
            {
                "id": "venetian_gold_filigree",
                "name": "Hand-Crafted Venetian 24k Gold Filigree Mask & Amber Glow",
                "signature_tokens": ['venetian mask', 'gold filigree', 'amber glow', 'diamond prism'],
                "focus": "Hand-crafted Venetian 24k gold filigree half-mask contouring upper brow and cheekbones, leaving mouth completely free. Kodak Portra 400 film grain and warm 2800K halation. Opening mouth releases drifting amber gossamer specks; smiling triggers brilliant caustic diamond prism glints across cheekbones; eyebrow raise awakens intricate golden filigree lace sheen; head tilt cascades warm amber glints across temples. High fashion luxury AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Hand-Crafted Venetian 24k Gold Filigree Mask elevates portrait with 35mm film halation."
            },
            {
                "id": "celestial_moonstone_halo",
                "name": "Iridescent Moonstone Platinum Circlet & Portra 400 Halation",
                "signature_tokens": ['moonstone circlet', 'platinum circlet', 'pearl dust', 'dewy skin'],
                "focus": "Delicate platinum circlet set with shimmering rainbow moonstone cabochons resting at hairline. Subtle 35mm analog lens flare with golden-hour warmth and ray-traced shadows. Opening mouth summons ethereal floating celestial pearl dust around face; smiling illuminates radiant dewy skin sheen with caustic moonstone flares; eyebrow raise expands rainbow moonstone corona; head tilt shifts opalescent blue sheen. Timeless couture.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Iridescent Moonstone Platinum Circlet elevates portrait with 35mm film halation."
            },
            {
                "id": "gilded_butterfly_coronet",
                "name": "Gilded Gold Leaf Butterfly Coronet & Sunlit Petals",
                "signature_tokens": ['butterfly coronet', 'gold leaf butterflies', 'sunlit petals', 'wing flutter'],
                "focus": "Sculpted 24k beaten gold filigree butterflies resting lightly across forehead and hair. Ray-traced contact shadows and warm golden lighting. Opening mouth awakens gentle wing flutter releasing drifting golden shimmer motes; smiling illuminates sparkling sunlight glints on cheekbone peaks; eyebrow raise awakens miniature golden butterfly flight; head tilt catches shimmering wing luster. Fine-art couture, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Gilded Gold Leaf Butterfly Coronet elevates portrait with 35mm film halation."
            },
            {
                "id": "rose_gold_astral_tiara",
                "name": "Rose Gold Astral Starburst Tiara & Starlight Glints",
                "signature_tokens": ['rose gold tiara', 'astral starburst', 'morganite', 'starlight aura'],
                "focus": "Hand-forged 18k rose gold astral starburst tiara anchored along brow with inset morganite gemstones. Portra film warmth with soft halation. Opening mouth releases cascading micro-glitter starlight aura; smiling triggers dazzling rose-gold starburst flares across eyes; eyebrow raise pulses blushing astral starlight halo; head tilt cascades warm morganite gemstone reflections across temples. Pure vanity elegance, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Rose Gold Astral Starburst Tiara elevates portrait with 35mm film halation."
            },
            {
                "id": "opal_sunburst_diadem",
                "name": "Australian Opal Sunburst Diadem & Golden Shimmer",
                "signature_tokens": ['opal diadem', 'sunburst crown', 'fire opal', 'chromatic shimmer'],
                "focus": "Radiant sunburst diadem of fiery Australian opals and twisted yellow gold wire fitted securely above forehead. 3-point lighting with cinematic analog bloom. Opening mouth floats warm golden sun-dust motes across temples; smiling creates exquisite chromatic rainbow shimmer across cheekbone highlights; eyebrow raise flares fiery opal sunburst beams; head tilt shifts prismatic fire play across opals. Editorial beauty.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Parisian haute couture glamour: opulent Australian Opal Sunburst Diadem elevates portrait with 35mm film halation."
            }
        ]
    },
    "5": {
        "channel_name": "Chrono_Mirage",
        "genre": "Y3K Liquid Mercury Surrealism, Zero-G Chrome & Hypnotic Aesthetics",
        "craft_dials": {
            "design_variance": 0.92,
            "visual_density": 0.94,
            "motion_intensity": 0.88
        },
        "forbidden_cross_contamination": ['cartoon stormclouds', 'traditional historical filigree', 'retro cyan text HUDs', 'meme gags', 'medieval fantasy crowns', 'developer UI sliders'],
        "tag_pool": ['surreal', 'chrome', 'liquid_mercury', 'y3k', 'zerog', 'halo', 'fluid', 'pbr'],
        "archetypes": [
            {
                "id": "liquid_mercury_halo",
                "name": "Y3K Zero-G Liquid Mercury Morphing Halo & Chrome Armor",
                "signature_tokens": ['liquid mercury halo', 'chrome cheek plates', 'y3k', 'zero-g chrome', 'surface tension'],
                "focus": "Weightless Y3K zero-G liquid mercury halo crown morphing above head with sculpted chrome cheekbone armor. Anisotropic mirror PBR reflections with fluid surface tension and ray-traced shadows. Opening mouth erupts orbiting liquid chrome spheres into expanding toroidal shockwave; smiling ripples fluid normal maps across armor; eyebrow raise sharpens liquid mercury spikes; head tilt shifts mercury droplets. Zero strobing, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Y3K Zero-G Liquid Mercury Morphing Halo ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "mobius_chrome_ribbon",
                "name": "Hypnotic Chrome Mobius Ribbon & Kaleidoscopic Mirror Shards",
                "signature_tokens": ['mobius', 'liquid platinum ribbon', 'kaleidoscopic mirror'],
                "focus": "Interlocking liquid platinum Mobius strip ribbon undulating continuously in zero-g around upper crown. Hyper-reflective chrome shader reflecting ambient environment with fluid refraction. Opening mouth sends floating chrome ribbon tendrils surging forward; smiling shatters ambient reflection into kaleidoscopic mirror prism facet display; eyebrow raise twists Mobius ribbon curvature; head tilt ripples chrome liquid flow. Surreal Y3K aesthetic.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Hypnotic Chrome Mobius Ribbon ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "ferrofluid_biomorphic_horns",
                "name": "Glossy Black Ferrofluid Horns & Orbiting Mercury Droplets",
                "signature_tokens": ['ferrofluid', 'magnetic spikes', 'liquid mercury droplets'],
                "focus": "Glossy obsidian ferrofluid horn sculptures rising organically from temples, dynamically morphing between fluid blobs and magnetic spikes. 3-point contrast lighting with cool 6500K rim. Opening mouth suspends dozens of zero-g liquid mercury droplets floating across face; smiling pulses electromagnetic ripple wave through ferrofluid; eyebrow raise elongates magnetic spikes; head tilt wavers fluid droplet constellation. Pure surrealism.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Glossy Black Ferrofluid Horns ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "liquid_platinum_tears",
                "name": "Mirrored Liquid Platinum Tear-Tracks & Surreal Toroidal Halo",
                "signature_tokens": ['liquid platinum tear', 'toroid halo', 'molten mirrors'],
                "focus": "Mirrored liquid platinum teardrop sculptures frozen weightlessly along cheekbones with floating surreal chrome toroid halo above head. Anisotropic fluid reflections with ray-traced shadows. Opening mouth releases liquid metal ripple shockwave radiating across cheek sculptures; smiling inverts chrome surface reflections with chromatic prism sheen; eyebrow raise lifts platinum droplets; head tilt sways chrome toroid. Zero strobing.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Mirrored Liquid Platinum Tear-Tracks ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "iridescent_chrome_chrysalis",
                "name": "Reflective Liquid Bismuth Chrysalis & Chromatic Dispersion",
                "signature_tokens": ['bismuth chrysalis', 'chromatic dispersion', 'bubble ring'],
                "focus": "Ultra-reflective liquid bismuth and molten chrome chrysalis crest morphing over forehead with fluid tendrils framing temples. Shimmering prismatic surface iridescence with HDR environment reflections. Opening mouth expands liquid chrome bubble ring floating forward; smiling triggers fluid chromatic surface dispersion waves across face; eyebrow raise blooms metallic chrysalis wings; head tilt shifts rainbow bismuth sheen. Zero-g AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Reflective Liquid Bismuth Chrysalis ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "hypercube_tesseract_halo",
                "name": "Zero-G Chrome Tesseract Halo & Gravitational Ripples",
                "signature_tokens": ['tesseract', 'hypercube halo', 'gravitational ripple', 'liquid chrome vertices'],
                "focus": "Weightless 4D liquid chrome tesseract frame rotating smoothly above head with mirrored vertices. Anisotropic reflections, ray-traced contact shadows. Opening mouth triggers gravitational shockwave ripple warping ambient reflections; smiling flashes prismatic chromatic aberration rings along cheek contours; eyebrow raise accelerates tesseract 4D rotation; head tilt distorts liquid chrome vertices. Y3K surrealism, zero strobing.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Zero-G Chrome Tesseract Halo ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "liquid_titanium_spikes",
                "name": "Liquid Titanium Spire Horns & Molten Droplets",
                "signature_tokens": ['titanium spires', 'molten droplets', 'surface tension', 'liquid horns'],
                "focus": "Sculpted liquid titanium spires rising weightlessly from head and temples, undulating with fluid surface tension. PBR metallic reflections with 3-point contrast 6500K rim lighting. Opening mouth releases floating orbit of reflective molten titanium spheres; smiling pulses fluid magnetic ripple waves through horn geometry; eyebrow raise extends sharp titanium spires outward; head tilt drifts molten titanium droplets. Pure zero-G aesthetics.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Liquid Titanium Spire Horns ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "cyber_chitin_exoshell",
                "name": "Iridescent Chrome Chitin Brow & Prismatic Sheen",
                "signature_tokens": ['chitin brow', 'exoshell', 'toroidal ring', 'beetle-wing'],
                "focus": "Organic bio-surreal polished chrome brow shell with fluid beetle-wing iridescence fitted to forehead. PBR ray-traced shadows. Opening mouth releases expanding toroidal liquid mercury ring surging forward; smiling triggers radiant rainbow chromatic dispersion wave across face contours; eyebrow raise flares chrome chitin armor plates outward; head tilt reflects dynamic iridescent sheen highlights across temples. High-concept Y3K.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Iridescent Chrome Chitin Brow ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "vortex_singularity_halo",
                "name": "Liquid Platinum Vortex Halo & Event Horizon Sheen",
                "signature_tokens": ['vortex halo', 'singularity halo', 'platinum accretion', 'event horizon'],
                "focus": "Swirling zero-G liquid platinum accretion disc floating above hairline with dark mirrored core. Anisotropic mirror shaders catching studio lighting. Opening mouth emits miniature orbiting mercury droplets spiraling inward; smiling triggers fluid chrome surface wave expanding outward across cheeks; eyebrow raise intensifies gravitational lens distortion halo; head tilt spirals accretion disc streamlines smoothly. Surreal kinetic art.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Liquid Platinum Vortex Halo ripples with warped environmental reflections in 0.2s."
            },
            {
                "id": "quantum_mercury_droplets",
                "name": "Floating Zero-G Mercury Orb Field & Chrome Spikes",
                "signature_tokens": ['quantum mercury', 'orb field', 'droplet field', 'mercury constellation'],
                "focus": "Suspended constellation of zero-G liquid mercury droplets hovering around temples and brow with fluid surface tension. Opening mouth surges droplets together into undulating chrome headpiece; smiling shatters geometry into shimmering cloud of mirror-finish micro-spheres; eyebrow raise freezes mercury droplets into floating sharp crystals; head tilt sends fluid droplet wave dancing around brow. Seamless physics AR.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Hypnotic Y3K surrealism: zero-G Floating Zero-G Mercury Orb Field ripples with warped environmental reflections in 0.2s."
            }
        ]
    },
    "6": {
        "channel_name": "Interactive_Games",
        "genre": "Gamified AR Challenges, Head-Tilt Racers, Mouth-Catch Food/Coins & Reflex Skill Challenges",
        "craft_dials": {
            "design_variance": 0.95,
            "visual_density": 0.88,
            "motion_intensity": 0.96
        },
        "forbidden_cross_contamination": ['traditional historical filigree', 'dark fantasy monsters', 'slow cinematic luxury', 'confusing multi-step tutorials', 'touchscreen buttons', 'developer UI sliders'],
        "tag_pool": ['game', 'arcade', 'challenge', 'interactive', 'racer', 'catcher', 'reflex', 'pbr'],
        "archetypes": [
            {
                "id": "arcade_neon_coin_catcher",
                "name": "Arcade Neon Coin Catcher & Floating Score Multiplier",
                "signature_tokens": ['coin catcher', 'arcade coins', 'score multiplier', 'combo burst'],
                "focus": "Retro-futuristic 3D neon arcade crown with tumbling golden arcade coins descending towards mouth. PBR metallic coin luster with emissive neon rim lighting. Opening mouth chomps coins triggering explosive floating +100 COMBO point bursts and golden spark showers; smiling activates rainbow jackpot starburst flare; eyebrow raise triggers double-coin frenzy; head tilt catches angled coins. Pure 3D gamified AR, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: high-energy Arcade Neon Coin Catcher challenges reflexes with explosive score bursts in 0.2s."
            },
            {
                "id": "tilt_speed_racer",
                "name": "Head-Tilt Neon Speeder & Obstacle Dodge Runner",
                "signature_tokens": ['tilt speeder', 'neon racer', 'obstacle dodge', 'hyper-boost'],
                "focus": "Sleek aerodynamic 3D neon cyber speeder hovercraft anchored above brow navigating floating neon obstacle gates. Head tilt left or right banks and steers the speeder smoothly with kinetic thruster trails; opening mouth triggers hyper-boost nitro warp with chromatic speed lines; smiling clears obstacle gates with sonic blast ring; eyebrow raise flares dual ion engine exhausts. High-velocity AR gameplay, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: high-velocity Head-Tilt Neon Speeder puts players in the cockpit with instant responsive steering."
            },
            {
                "id": "reaction_timing_meter",
                "name": "Reaction Reflex Timing Bar & Jackpot Green Zone",
                "signature_tokens": ['timing bar', 'reaction meter', 'green zone', 'jackpot bullseye'],
                "focus": "Curved holographic precision reflex timing bar floating across forehead with rapidly oscillating neon laser needle. 3-point contrast lighting. Smiling freezes needle instantly; head tilt nails the center green zone to detonate giant celebratory golden confetti; opening mouth resets needle with spark shockwave; eyebrow raise speeds up needle oscillation. Viral reflex challenge, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: high-stakes Reaction Reflex Timing Bar hooks competitive players to hit the bullseye in 0.2s."
            },
            {
                "id": "bunny_cloud_jumper",
                "name": "Flappy Bunny Cloud Jumper & Pastel Rainbow Trails",
                "signature_tokens": ['bunny jumper', 'cloud jumper', 'flappy game', 'rainbow trail'],
                "focus": "Floating pastel cloud platform game anchored across brow with hopping 3D animated bunny. Head tilt left or right steers bunny between cloud platforms; opening mouth triggers super-jump spring with rainbow sparkles; smiling collects floating golden stars with melodic chime cascades; eyebrow raise changes cloud theme. Addictive retro platformer, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: Flappy Bunny Cloud Jumper delivers addictive infinite-jumper mechanics with head-tilt steering."
            },
            {
                "id": "oracle_balance_scales",
                "name": "Gold Celestial Balance Scales & This-or-That Fortune",
                "signature_tokens": ['balance scales', 'this or that', 'oracle fortune', 'celestial scale'],
                "focus": "Ornate beaten 24k gold celestial balance scales resting regally on brow with glowing sun and moon platters. Head tilt left or right tips the scales to choose comedic viral dilemmas, unleashing bursting celestial auras and floating ancient scrolls on the winning side; opening mouth rebalances scales with radiant solar ray burst; smiling rings harmonic brass chimes; eyebrow raise levels scales evenly. Interactive choice game.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: Gold Celestial Balance Scales turns head tilts into interactive viral decision-making gameplay."
            },
            {
                "id": "chomp_fruit_frenzy",
                "name": "Mouth-Chomp Tropical Fruit Frenzy & Splash Waves",
                "signature_tokens": ['fruit frenzy', 'chomp fruit', 'watermelon splash', 'fruit catch'],
                "focus": "Tumbling 3D cartoon watermelons, pineapples, and strawberries descending toward mouth. PBR glossy fruit shaders with dynamic lighting. Opening mouth chomps fruit with juicy cartoon splash droplets and floating score popups; smiling triggers giant golden pineapple crown bonus; eyebrow raise launches fruit toss frenzy; head tilt catches angled falling fruit. High-engagement mouth challenge AR, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: Mouth-Chomp Tropical Fruit Frenzy drives massive replay value with juicy cartoon splash rewards."
            },
            {
                "id": "laser_dodge_matrix",
                "name": "Kinetic Laser Dodge Obstacle Grid & Cyber Shield",
                "signature_tokens": ['laser dodge', 'obstacle grid', 'cyber shield', 'matrix dodge'],
                "focus": "Floating neon obstacle grid approaching face. Head tilt ducks and weaves left or right around incoming neon laser barriers; opening mouth deploys hexagonal kinetic energy shield deflecting lasers in brilliant spark showers; smiling triggers matrix green victory pulse wave; eyebrow raise activates slow-motion chrono-drift dodging. Pure 3D physics challenge, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: Kinetic Laser Dodge Obstacle Grid tests head agility with high-octane laser deflection."
            },
            {
                "id": "pizza_slice_catcher",
                "name": "Speed Pizza Chomp & Floating Neon Chef Toque",
                "signature_tokens": ['pizza chomp', 'pizza catcher', 'neon chef toque', 'cheese pull'],
                "focus": "Stylized 3D neon chef toque hat resting on crown with tumbling cartoon pepperoni pizza slices descending toward mouth. Opening mouth chomps pizza with hilarious bubbling cheese-pull strands and floating +250 SCORE badges; smiling triggers pepperoni party confetti; eyebrow raise tosses spinning pizza dough into the air; head tilt catches slices at wild angles. Viral comedy food game, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Addictive gamified AR: Speed Pizza Chomp captures instant viral appetite with mouth-watering cartoon cheese physics."
            }
        ]
    },
    "7": {
        "channel_name": "Retro_Decades",
        "genre": "70s Studio 54 Disco, 80s Synthwave Neon Grid, 90s Hi-8 VHS Camcorder & Y2K Cyber Nostalgia",
        "craft_dials": {
            "design_variance": 0.90,
            "visual_density": 0.93,
            "motion_intensity": 0.85
        },
        "forbidden_cross_contamination": ['modern minimalist flat art', 'grotesque horror gore', 'corporate stock photography', 'developer UI sliders', 'cheap 2D stickers'],
        "tag_pool": ['retro', '80s', '90s', '70s', 'synthwave', 'vhs', 'camcorder', 'disco', 'y2k', 'nostalgia'],
        "archetypes": [
            {
                "id": "synthwave_80s_grid",
                "name": "80s Outrun Synthwave Horizon Grid & Chrome Cassette Crown",
                "signature_tokens": ['synthwave grid', 'outrun', 'chrome cassette', 'neon horizon'],
                "focus": "Sculpted neon-magenta wireframe perspective grid extending behind brow with floating 80s chrome cassette diadem. Warm analog CRT scanline halation with cyan rim lighting. Opening mouth accelerates wireframe grid into hyperspace speed warp with neon laser beams; smiling triggers warm neon sunset flare; eyebrow raise pulses synthwave bass-rings; head tilt shifts grid perspective. Pure 80s nostalgia, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: 80s Outrun Synthwave Horizon Grid transports users directly into iconic retro arcade aesthetic in 0.2s."
            },
            {
                "id": "vhs_camcorder_90s",
                "name": "90s Hi-8 VHS Camcorder OSD & Tape-Rip Static Glitch",
                "signature_tokens": ['vhs camcorder', 'tape-rip glitch', 'hi-8', 'tracking static', 'phosphor scanline'],
                "focus": "Authentic 90s Hi-8 camcorder visor frame with floating green PLAY OSD timestamp and magnetic phosphor scanlines. Opening mouth triggers nostalgic magnetic tape-rip glitch shockwave with RGB color split and tracking static; smiling pulses battery REC indicator flare; eyebrow raise flashes amber night-vision beam; head tilt shifts cathode interlacing. Pure 90s camcorder nostalgia, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: authentic 90s Hi-8 VHS Camcorder tape glitch captures the unmistakable warmth of analogue memories."
            },
            {
                "id": "disco_70s_studio54",
                "name": "70s Studio 54 Disco Ball Headpiece & Golden Roller Glitter",
                "signature_tokens": ['studio 54', 'disco ball', 'roller glitter', '70s disco'],
                "focus": "Spinning multifaceted mirror disco ball crown anchored to hairline with golden starburst flares and warm sunset halation. Opening mouth showers cascading golden glitter dust and spinning roller-disco sparkles; smiling flashes multi-colored prism lightbeams across face; eyebrow raise ignites 70s funk disco aura; head tilt sweeps mirror facets. Pure 70s dancefloor glamour, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: 70s Studio 54 Disco Ball Headpiece radiates irresistible retro party energy in 0.2s."
            },
            {
                "id": "y2k_cyber_butterfly",
                "name": "Y2K Holographic Cyber Butterfly Diadem & Gloss Sheen",
                "signature_tokens": ['y2k butterfly', 'holographic butterfly', 'gloss sheen', 'cyber butterfly'],
                "focus": "Iridescent chrome and holographic translucent butterfly diadem fluttering above brow with frosted lip-gloss sheen and baby-blue Y2K aesthetic. Opening mouth flutters holographic wings releasing glowing glitter sparkles; smiling illuminates dewy cyber gloss sheen across cheekbones; eyebrow raise expands holographic wireframe wings; head tilt catches rainbow chrome reflection. Authentic Y2K cyber revival.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: Y2K Holographic Cyber Butterfly Diadem taps the surging viral Millennium aesthetic."
            },
            {
                "id": "grunge_90s_analog",
                "name": "90s Grunge 35mm Polaroid Frame & Film Burn Bloom",
                "signature_tokens": ['grunge 90s', 'polaroid frame', 'film burn', 'light leaks'],
                "focus": "Vintage weathered Polaroid camera frame floating around face with nostalgic sepia color grading and authentic light leaks. Opening mouth ignites brilliant orange film burn flare and floating amber dust motes; smiling softens portrait into warm 90s indie cinema grain; eyebrow raise flashes vintage camera xenon strobe; head tilt shifts light leak hues. Raw 90s grunge film aesthetic, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: 90s Grunge 35mm Polaroid Frame wraps selfies in authentic lo-fi indie nostalgia."
            },
            {
                "id": "arcade_80s_pixel",
                "name": "80s Arcade Pixel CRT Visor & Retro Power-Up Sparks",
                "signature_tokens": ['pixel visor', '80s arcade', 'crt visor', 'power-up sparks'],
                "focus": "Chunky 8-bit neon arcade visor contoured across brow with pixelated glowing coin insets and cathode-tube bloom. Opening mouth triggers explosive 8-bit pixel level-up burst with floating retro arcade stars; smiling pulses 1UP emerald glow; eyebrow raise charges pixel laser cannon; head tilt sweeps phosphor scanlines. Retro gaming gold, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: 80s Arcade Pixel CRT Visor sparks retro gaming euphoria with authentic 8-bit level-up bursts."
            },
            {
                "id": "psychedelic_70s_groove",
                "name": "70s Psychedelic Woodstock Flower Crown & Liquid Groovy Waves",
                "signature_tokens": ['psychedelic 70s', 'woodstock flower', 'groovy waves', 'liquid lava'],
                "focus": "Undulating liquid-lava flow flower crown with warm psychedelic orange, mustard, and magenta swirls. Opening mouth releases floating kaleidoscope groovy flower petals and liquid light ripple waves; smiling warms complexion with retro Woodstock sunset halation; eyebrow raise blooms psychedelic petals; head tilt ripples lava patterns. Trippy 70s bohemian aesthetic.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: 70s Psychedelic Woodstock Flower Crown delivers mesmerizing bohemian liquid light waves."
            },
            {
                "id": "matrix_y2k_cyberspace",
                "name": "Y2K Cyberspace Liquid Wireframe Visor & Digital Rain",
                "signature_tokens": ['cyberspace visor', 'digital rain', 'y2k cyberspace', 'phosphor code'],
                "focus": "Sleek minimalist matrix wireframe shades with cascading emerald phosphor digital code particles floating around temples. Opening mouth triggers shockwave pulse that freezes digital code into geometric cubes; smiling glints neon green laser beams through lenses; eyebrow raise accelerates matrix rain streams; head tilt angles code trajectory. Legendary late-90s cyberspace chic.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Decades nostalgia hit: Y2K Cyberspace Liquid Wireframe Visor commands instant attention with iconic falling digital code."
            }
        ]
    },
    "8": {
        "channel_name": "Greek_Pantheon",
        "genre": "Greek & Ancient Mythology Transformations, Olympian Thunder Laurels, Medusa Serpents & Celestial Deities",
        "craft_dials": {
            "design_variance": 0.89,
            "visual_density": 0.95,
            "motion_intensity": 0.88
        },
        "forbidden_cross_contamination": ['cyberpunk optics', 'cartoon weeping memes', 'sci-fi HUD telemetry', 'modern plastic glasses', 'developer UI sliders'],
        "tag_pool": ['greek', 'mythology', 'olympus', 'zeus', 'medusa', 'aphrodite', 'apollo', 'hades', 'gods', 'deity'],
        "archetypes": [
            {
                "id": "zeus_olympian_thunder",
                "name": "Zeus Olympian Thunderbolt Laurel & Electric Arc Corona",
                "signature_tokens": ['zeus', 'olympian thunder', 'lightning laurel', 'electric arc'],
                "focus": "Sculpted beaten 24k gold lightning-bolt laurel wreath resting on brow with crackling electric blue plasma arcs. Opening mouth summons blinding celestial thunderbolt shockwave with booming lightning bolts arcing across temples; smiling illuminates glowing electric blue gaze; eyebrow raise sparks crackling plasma crown; head tilt discharges golden lightning sparks. Supreme deity power, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Zeus Olympian Thunderbolt Laurel crowns user with crackling divine authority in 0.2s."
            },
            {
                "id": "medusa_gorgon_serpents",
                "name": "Medusa Coiling Bronze Serpents & Petrifying Stone Gaze",
                "signature_tokens": ['medusa', 'bronze serpents', 'petrifying gaze', 'stone gaze', 'emerald fangs'],
                "focus": "Intricately sculpted living bronze serpents coiling and writhing around hairline with glowing emerald gemstone venom eyes. Opening mouth turns background into cracked ancient marble with swirling petrification mist; smiling flashes brilliant emerald venom glints from serpent fangs; eyebrow raise makes bronze serpents hiss and flare hooded crests; head tilt ripples serpentine coils. Mythic transformation, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Medusa Coiling Bronze Serpents commands supreme viral intrigue with live writhing serpents."
            },
            {
                "id": "aphrodite_seafoam_pearl",
                "name": "Aphrodite Seafoam Scallop Pearl Tiara & Oceanic Mist",
                "signature_tokens": ['aphrodite', 'seafoam pearl', 'scallop tiara', 'oceanic mist'],
                "focus": "Iridescent mother-of-pearl scallop seashell tiara adorned with floating baroque freshwater pearls and crystalline seafoam bubbles. Opening mouth releases swirling oceanic sea-mist with floating luminescent pearl bubbles; smiling illuminates high-glamour pearlescent skin sheen and warm Aegean sunlight; eyebrow raise expands seashell crest; head tilt sways floating pearls. Celestial goddess beauty.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Aphrodite Seafoam Scallop Pearl Tiara elevates user to mythical Olympian beauty."
            },
            {
                "id": "apollo_solar_chariot",
                "name": "Apollo Radiant Solar Chariot Crown & Blinding Sunburst",
                "signature_tokens": ['apollo', 'solar chariot', 'sunburst crown', 'god-rays'],
                "focus": "Molten electrum and rose-gold solar ray crown radiating sunbeams from hairline with warm 2800K god-rays. Opening mouth unleashes blinding golden solar flare burst and floating solar ember motes; smiling triggers radiant sun-halo eye flares; eyebrow raise expands blazing golden ray spires; head tilt showers molten sun-sparks. Solar deity majesty, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Apollo Radiant Solar Chariot Crown bathes the creator in blinding celestial radiance."
            },
            {
                "id": "hades_stygian_soulfire",
                "name": "Hades Stygian Obsidian Coronet & Necrotic Cyan Flames",
                "signature_tokens": ['hades', 'stygian coronet', 'soulfire flames', 'underworld ash'],
                "focus": "Chiseled black volcanic obsidian coronet with glowing stygian rune inlays resting across brow. Opening mouth erupts ethereal spectral cyan soulfire flames surging upward with floating ghostly embers; smiling awakens piercing stygian blue eye glare; eyebrow raise ignites crown spires in cold cyan plasma; head tilt wafts underworld smoke. Dark mythic majesty, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Hades Stygian Obsidian Coronet summons dark underworld sovereign majesty in 0.2s."
            },
            {
                "id": "athena_aegis_wisdom",
                "name": "Athena Aegis Bronze War Helmet & Golden Owl Sigil",
                "signature_tokens": ['athena', 'aegis helm', 'bronze helmet', 'owl sigil'],
                "focus": "Polished Spartan bronze battle helm with sculpted golden owl crest and horsehair plume contouring forehead. Opening mouth releases shimmering golden tactical shockwave with floating runic glyphs; smiling pulses warm bronze rim light across cheekbones; eyebrow raise flares owl sigil wings; head tilt catches brilliant metallic sun-glint. Classical goddess of war and wisdom.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Athena Aegis Bronze War Helmet frames facial features with timeless Spartan warrior dignity."
            },
            {
                "id": "poseidon_ocean_trident",
                "name": "Poseidon Oceanic Trident Crown & Abyssal Tidal Surge",
                "signature_tokens": ['poseidon', 'ocean trident', 'abyssal surge', 'tidal vortex'],
                "focus": "Deep turquoise sea-glass and encrusted barnacle-gold trident circlet with floating bioluminescent deep-sea motes. Opening mouth unleashes surging abyssal tidal wave vortex with floating glowing jellyfish particles; smiling illuminates piercing aquamarine eye glints; eyebrow raise activates tidal storm crest; head tilt ripples underwater caustics. Sovereign ocean ruler.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Poseidon Oceanic Trident Crown submerges the viewer into an epic deep-ocean realm."
            },
            {
                "id": "artemis_lunar_huntress",
                "name": "Artemis Silver Crescent Moon Diadem & Ethereal Starlight",
                "signature_tokens": ['artemis', 'crescent moon diadem', 'silver birch', 'moon-dust'],
                "focus": "Hand-carved sterling silver crescent moon diadem resting on brow with delicate silver birch leaves and starlight motes. Opening mouth releases swirling silver arrow light trails and floating celestial moon-dust; smiling illuminates luminous cool moonlight skin glow; eyebrow raise flares brilliant crescent silver tips; head tilt catches starlight gleams. Pure lunar huntress majesty.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Godly transformation: Artemis Silver Crescent Moon Diadem enchants selfies with ethereal lunar starlight magic."
            }
        ]
    },
    "9": {
        "channel_name": "Aesthetic_Beauty",
        "genre": "Viral Beautifying, Glass Skin Glow, Golden Hour Sunset, Natural Dewy Glow & Euphoria Rhinestones",
        "craft_dials": {
            "design_variance": 0.84,
            "visual_density": 0.96,
            "motion_intensity": 0.72
        },
        "forbidden_cross_contamination": ['grotesque cartoon memes', 'heavy sci-fi military HUD', 'dark horror fangs', 'monster horns', 'developer UI sliders'],
        "tag_pool": ['beauty', 'glow', 'glass_skin', 'golden_hour', 'freckles', 'glam', 'aesthetic', 'pbr'],
        "archetypes": [
            {
                "id": "glass_skin_dewy",
                "name": "Glass Skin Luminous Dewy Glow & Soft Peach Freckles",
                "signature_tokens": ['glass skin', 'dewy glow', 'peach freckles', 'soft glam', 'ring-light'],
                "focus": "Ultra-refined soft-focus porcelain skin smoothing with dewy high-fashion cheekbone highlight and subtle micro-freckles across nose bridge. Opening mouth cascades delicate suspended champagne micro-glitter dust; smiling illuminates warm pearlescent facial sheen and glossy lip shine; eyebrow raise sharpens feline winged liner; head tilt reflects realistic studio ring-light eye catches. Pure viral vanity, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Irresistible beauty glow-up: Glass Skin Luminous Dewy Glow delivers flawless studio lighting and dewy highlights in 0.2s."
            },
            {
                "id": "golden_hour_sunset",
                "name": "Golden Hour Sunset Halation & Amber Sunbeam Flare",
                "signature_tokens": ['golden hour', 'sunset halation', 'amber sunbeam', 'sun-kissed', 'warm glow'],
                "focus": "Warm 2800K golden-hour sunset lighting with cinematic lens halation, gentle cheek contour, and warm golden skin tint. Opening mouth releases soft floating golden sunlight specks around temples; smiling ignites brilliant warm sunbeam flare across cheekbones; eyebrow raise enhances dewy golden skin luster; head tilt cascades prismatic sunlight caustics. Timeless beauty aesthetic, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Irresistible beauty glow-up: Golden Hour Sunset Halation bathes facial contours in authentic warm sunset magic."
            },
            {
                "id": "euphoria_crystal_rhinestones",
                "name": "Euphoria Faceted Crystal Rhinestones & Iridescent Cat-Eye",
                "signature_tokens": ['rhinestones', 'euphoria crystals', 'faceted gems', 'cat-eye', 'face jewelry'],
                "focus": "3D precision-cut faceted Swarovski rhinestones contoured along eyebrow arches and upper cheekbones. PBR caustic diamond refractions. Opening mouth sparks dazzling rainbow prismatic starburst glints from crystals; smiling enhances dewy lavender cheek shimmer; eyebrow raise flares crystal brow tips; head tilt catches brilliant diamond fire reflections. Editorial red-carpet glam, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Irresistible beauty glow-up: Euphoria Faceted Crystal Rhinestones turns brow lines into sparkling high-fashion jewelry."
            },
            {
                "id": "angel_aura_ethereal",
                "name": "Angel Aura Iridescent Dew & Luminous Halo Glow",
                "signature_tokens": ['angel aura', 'ethereal dew', 'halo glow', 'pastel blush', 'angel wings'],
                "focus": "Ethereal pearlescent skin filter with pastel cloud blush and floating celestial micro-sparkles. Opening mouth summons gentle floating iridescent pearl orbs orbiting hair; smiling creates luminous high-fashion skin radiance and winged lash lift; eyebrow raise flares delicate pastel rainbow brow corona; head tilt shifts opalescent pink-to-gold cheek sheen. Dreamy aesthetic, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Irresistible beauty glow-up: Angel Aura Iridescent Dew enchants selfies with ethereal heavenly glow."
            },
            {
                "id": "clean_girl_soft_glam",
                "name": "Clean Girl Minimalist Velvet Skin & Laminated Brow Lift",
                "signature_tokens": ['clean girl', 'velvet skin', 'laminated brow', 'lip glaze', 'natural glow'],
                "focus": "Natural no-makeup velvet skin texture with fluffy laminated brow lift and dewy honey lip glaze. Opening mouth floats warm golden shimmer dust; smiling activates soft natural ring-light reflections in pupils; eyebrow raise sharpens defined brow arches; head tilt catches subtle high-point cheekbone glints. Clean minimalist viral luxury, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Irresistible beauty glow-up: Clean Girl Minimalist Velvet Skin perfects natural beauty with effortless elegance."
            },
            {
                "id": "cherry_blossom_blush",
                "name": "Sakura Petal Blush & Floating Cherry Blossom Motes",
                "signature_tokens": ['sakura blush', 'cherry blossom', 'floating petals', 'anime blush', 'petal glow'],
                "focus": "Delicate soft-pink watercolor sakura blush on cheeks and nose tip with floating 3D cherry blossom petals drifting around brow. Opening mouth releases gentle swirl of fluttering sakura petals; smiling deepens soft rosy glow with glass-skin cheek sheen; eyebrow raise lifts petal crown; head tilt sways floating blossoms. Romantic Japanese anime beauty, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Irresistible beauty glow-up: Sakura Petal Blush cascades dreamy cherry blossoms across cheekbones in 0.2s."
            }
        ]
    },
    "10": {
        "channel_name": "Cosmic_Astronaut",
        "genre": "Apollo Gold-Visor Astronaut Helmets, Interstellar Orbiting Planetarium & Deep Space Nebulas",
        "craft_dials": {
            "design_variance": 0.92,
            "visual_density": 0.95,
            "motion_intensity": 0.90
        },
        "forbidden_cross_contamination": ['cartoon crying memes', 'medieval filigree tiaras', 'cheap 2D stickers', 'developer UI sliders'],
        "tag_pool": ['space', 'astronaut', 'helmet', 'orbiting', 'planetarium', 'nebula', 'cosmic', 'pbr'],
        "archetypes": [
            {
                "id": "apollo_astronaut_helmet",
                "name": "Apollo Gold-Visor Astronaut Helmet & Lunar Earthrise Reflection",
                "signature_tokens": ['astronaut helmet', 'gold visor', 'apollo', 'lunar reflection', 'earthrise', 'space helmet'],
                "focus": "Realistic 3D Apollo astronaut helmet contoured over head with curved reflective 24k gold-coated sun-visor mirroring the Earth and lunar horizon. PBR brushed aerospace composite with micro-thrusters. Opening mouth vents pressurized white nitrogen gas plumes from helmet valves; smiling pulses blue HUD status ring on collar; eyebrow raise flares lunar sunburst off visor; head tilt reflects rotating Earth. Epic space exploration, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Epic cosmic journey: Apollo Gold-Visor Astronaut Helmet locks user into full-fidelity space exploration in 0.2s."
            },
            {
                "id": "interstellar_orbiting_planetarium",
                "name": "Orbiting Solar Planetarium Crown & Saturn Ice Rings",
                "signature_tokens": ['planetarium crown', 'orbiting planets', 'saturn rings', 'solar system', 'celestial sphere'],
                "focus": "Photorealistic 3D celestial planetarium orbiting user head with glowing Sun at crown, ringed Saturn, swirling Jupiter, and Earth traversing smooth elliptical orbits with floating stardust. Opening mouth triggers mini supernova starburst with expanding asteroid ring shockwave; smiling illuminates golden solar flare from brow; eyebrow raise expands planetary orbits; head tilt tilts Saturn ring plane. Kinetic space wonder, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Epic cosmic journey: Orbiting Solar Planetarium Crown turns user into center of the universe with spinning celestial bodies."
            },
            {
                "id": "deep_space_nebula_helmet",
                "name": "Deep Space Cosmic Nebula Glass Dome & Supernova Sparks",
                "signature_tokens": ['nebula helmet', 'cosmic dome', 'glass helmet', 'supernova sparks', 'auroral plasma'],
                "focus": "Transparent spherical astronaut pressure dome filled with swirling violet, cyan, and magenta cosmic nebula gas and twinkling distant star clusters. Opening mouth detonates glowing stellar supernova flash inside helmet releasing star sparks; smiling surges auroral plasma waves through nebula; eyebrow raise flares stellar eye glints; head tilt swirls cosmic gas vortex. Deep space majesty, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Epic cosmic journey: Deep Space Cosmic Nebula Glass Dome captures the swirling majesty of deep interstellar space."
            },
            {
                "id": "zero_g_spacewalk_satellite",
                "name": "Zero-G Spacewalk Orbital Satellite & Solar Array Wings",
                "signature_tokens": ['spacewalk satellite', 'zero-g satellite', 'solar arrays', 'space station', 'docking ring'],
                "focus": "Miniature detailed 3D space station satellite hovering weightlessly over right shoulder with rotating gold photovoltaic solar panels and docking ring. Opening mouth fires blue ion engine thruster pulse with floating space dust motes; smiling pulses solar panel telemetry glints; eyebrow raise activates laser navigation beam; head tilt drifts satellite smoothly in zero-G orbit. Authentic space hardware, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Epic cosmic journey: Zero-G Spacewalk Orbital Satellite orbits head with micro-gravity physics and satellite maneuvers."
            },
            {
                "id": "black_hole_accretion_halo",
                "name": "Gargantua Black Hole Gravitational Accretion Halo & Relativistic Jets",
                "signature_tokens": ['black hole', 'accretion halo', 'gravitational lensing', 'event horizon', 'relativistic jets'],
                "focus": "Curved gravitational light-bending black hole with swirling molten orange accretion disc floating above head. Opening mouth unleashes dual vertical relativistic blue plasma jets shooting upward; smiling bends background stars in gravitational lensing swirl; eyebrow raise accelerates accretion vortex; head tilt distorts event horizon ring. Cosmic astrophysics spectacle, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Epic cosmic journey: Gargantua Black Hole Gravitational Accretion Halo bends light and reality around the creator."
            },
            {
                "id": "mars_rover_explorer_visor",
                "name": "Mars Perseverance Explorer Helmet & Martian Dust Halo",
                "signature_tokens": ['mars explorer', 'rover helmet', 'martian dust', 'amber visor', 'searchlights'],
                "focus": "Rugged carbon-kevlar planetary exploration helmet with polarized amber optic shield and micro-geological scanner. Opening mouth triggers swirling red Martian dust storm vortex with floating basalt particles; smiling activates twin LED searchlights on temples; eyebrow raise flashes terrain telemetry grid; head tilt sways atmospheric dust plumes. Red planet exploration, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Epic cosmic journey: Mars Perseverance Explorer Helmet straps creator into rugged planetary expedition gear."
            }
        ]
    },
    "11": {
        "channel_name": "Viral_Randomizer",
        "genre": "Rotating Tarot Wheels, Which Vibe Are You? Head-Tilt Decision Pickers & Energy Aura Scanners",
        "craft_dials": {
            "design_variance": 0.96,
            "visual_density": 0.90,
            "motion_intensity": 0.95
        },
        "forbidden_cross_contamination": ['solemn historical armor', 'heavy military hardware', 'boring static filters', 'developer UI sliders'],
        "tag_pool": ['randomizer', 'wheel', 'decision', 'tarot', 'vibe', 'which_are_you', 'interactive', 'viral'],
        "archetypes": [
            {
                "id": "celestial_tarot_wheel",
                "name": "Rotating Celestial Tarot Wheel & Golden Fortune Reveal",
                "signature_tokens": ['tarot wheel', 'fortune wheel', 'rotating wheel', 'zodiac cards', 'fortune reveal'],
                "focus": "Ornate 3D gilded celestial fortune wheel spinning rapidly above forehead with spinning zodiac cards. Head tilt or smiling decisively stops the spinning ticker on the winning card—unleashing giant golden trumpet fanfare confetti and glowing celestial aura; opening mouth re-spins wheel at high speed; eyebrow raise flashes cosmic fortune runes. Highly addictive viral decision game, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral interactive game: Rotating Celestial Tarot Wheel hooks viewers with suspenseful spinning fortune reveal in 0.2s."
            },
            {
                "id": "which_vibe_picker",
                "name": "Which Vibe Are You? Neon Floating Card Carousel",
                "signature_tokens": ['which vibe', 'card carousel', 'mood cards', 'vibe picker', 'spinning cards'],
                "focus": "High-energy floating neon cards flipping rapidly above brow with viral mood titles. Blinking or smiling locks the winner in a burst of sparkling neon confetti and celebratory sound chimes; opening mouth spins cards into hyper-speed blur; eyebrow raise resets the shuffle; head tilt tilts cards toward camera. Viral social challenge magnet, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral interactive game: Which Vibe Are You? drives massive comment debates and social share velocity."
            },
            {
                "id": "aura_energy_scanner",
                "name": "Cosmic Energy Aura Scanner & Chromatic Mood Halo",
                "signature_tokens": ['aura scanner', 'energy scanner', 'mood halo', 'biometric aura', 'chromatic aura'],
                "focus": "Futuristic holographic biometric scanning bar oscillating across face reading emotional wavelength. Smiling snaps scanner to reveal user's authentic aura color with billowing energy clouds; head tilt cycles chromatic energy frequencies; opening mouth discharges rainbow energy shockwave; eyebrow raise re-scans aura. Viral personality predictor, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral interactive game: Cosmic Energy Aura Scanner visualizes personality in dynamic radiant color."
            },
            {
                "id": "this_or_that_decision_spinner",
                "name": "This or That Dual Neon Decision Pillars & Ticker Arrow",
                "signature_tokens": ['this or that', 'decision spinner', 'neon pillars', 'ticker arrow', 'choice cards'],
                "focus": "Floating twin neon decision cards anchored to left and right temples with oscillating center compass needle. Head tilt left or right decisively slams needle into chosen option, detonating winner particle explosions; opening mouth clears choice for next round; smiling triggers jackpot; eyebrow raise flips options. Social decision game, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral interactive game: This or That Decision Pillars turns everyday dilemmas into high-stakes head-tilt choices."
            },
            {
                "id": "spirit_animal_totem_wheel",
                "name": "Spinning Spirit Animal Totem Wheel & Mythic Avatar",
                "signature_tokens": ['totem wheel', 'spirit animal', 'totem disc', 'animal avatar', 'spinning totem'],
                "focus": "Carved gilded totem disc spinning above hairline showing mythical spirit avatars. Smiling halts spinner on user's spirit animal, morphing brow with matching 3D ears and sparkles; head tilt rotates camera perspective; opening mouth unleashes animal spirit roar aura; eyebrow raise spins totem again. High viral replayability, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Viral interactive game: Spinning Spirit Animal Totem Wheel reveals user spirit animal with instant 3D metamorphosis."
            }
        ]
    },
    "12": {
        "channel_name": "Gothic_DarkFantasy",
        "genre": "Vampire Sovereign Fangs, Blood Moon Coronets, Phantom Wraiths & Dark Archangel Wings",
        "craft_dials": {
            "design_variance": 0.91,
            "visual_density": 0.95,
            "motion_intensity": 0.89
        },
        "forbidden_cross_contamination": ['cute pastel stickers', 'bubblegum pop', 'neon corporate tech', 'developer UI sliders'],
        "tag_pool": ['gothic', 'vampire', 'fangs', 'dark_fantasy', 'blood_moon', 'wraith', 'phantom', 'pbr'],
        "archetypes": [
            {
                "id": "vampire_sovereign_fangs",
                "name": "Vampire Sovereign Bat-Wing Coronet & Blood Moon Fangs",
                "signature_tokens": ['vampire fangs', 'bat-wing coronet', 'blood moon', 'vampire', 'gothic coronet', 'ruby tears'],
                "focus": "Sculpted matte obsidian bat-wing gothic coronet set with dripping ruby teardrop gems anchored to brow. Opening mouth reveals gleaming elongated 3D ivory vampire fangs with swirling crimson blood-mist and dark gothic smoke; smiling ignites piercing crimson blood-moon eye glints; eyebrow raise flares gothic bat wings; head tilt catches ruby caustics. Peak dark royalty, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Dark fantasy power: Vampire Sovereign Bat-Wing Coronet transforms selfies into regal gothic royalty in 0.2s."
            },
            {
                "id": "phantom_wraith_shroud",
                "name": "Phantom Wraith Spectral Shroud & Stygian Blue Flame",
                "signature_tokens": ['phantom wraith', 'spectral shroud', 'stygian blue', 'soulfire geyser', 'ghostly embers'],
                "focus": "Translucent tattered ethereal silk shroud floating weightlessly around head with dancing ghostly cyan spirit flames. Opening mouth erupts cryogenic soulfire geyser swirling forward with floating spectral embers; smiling illuminates piercing supernatural white eye glare; eyebrow raise billows ghost shroud; head tilt ripples ectoplasm mist. Haunting supernatural presence, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Dark fantasy power: Phantom Wraith Spectral Shroud creates eerie translucent ghost presence with chilling soulfire."
            },
            {
                "id": "fallen_archangel_halo",
                "name": "Fallen Archangel Barbed Obsidian Halo & Raven Feather Torrent",
                "signature_tokens": ['fallen archangel', 'barbed halo', 'raven feathers', 'feather torrent', 'violet lightning'],
                "focus": "Barbed blackened iron thorn halo hovering weightlessly above head with floating iridescent black raven feathers. Opening mouth unleashes explosive dark feathered shockwave vortex with violet lightning arcs; smiling pulses cold violet rim lighting across cheekbones; eyebrow raise extends thorn spires; head tilt sways floating black feathers. Dramatic dark angel aesthetic, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Dark fantasy power: Fallen Archangel Barbed Obsidian Halo commands solemn gothic majesty with fluttering raven feathers."
            },
            {
                "id": "gargoyle_stone_cursed",
                "name": "Cursed Gothic Cathedral Gargoyle Crest & Living Marble",
                "signature_tokens": ['gargoyle crest', 'cathedral gargoyle', 'stone cursed', 'living marble', 'fissures'],
                "focus": "Chiseled ancient cathedral gargoyle stone crest anchored to brow with living glowing crimson eye fissures. Opening mouth cracks skin into ancient stone texture with billowing gothic incense smoke; smiling restores smooth alabaster marble sheen; eyebrow raise flares stone gargoyle wings; head tilt sways cathedral dust. Monumental stone metamorphosis, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Dark fantasy power: Cursed Gothic Cathedral Gargoyle Crest transforms human features into living mythological stone."
            },
            {
                "id": "necromancer_soul_reaper",
                "name": "Necromancer Stygian Skull Crown & Swirling Soulfire Orbs",
                "signature_tokens": ['necromancer', 'skull crown', 'soulfire orbs', 'soul reaper', 'stygian skulls'],
                "focus": "Intricately carved miniature electrum skulls linked into regal gothic coronet with floating cyan soulfire wisps orbiting temples. Opening mouth commands swirling orbit of ghostly soulfire orbs surging outward; smiling flashes piercing cyan eye luminescence; eyebrow raise flares crown spires in necrotic flame; head tilt trails ghostly soul smoke. Sovereign underworld conjurer, zero UI.",
                "primary_trigger": "MouthOpen / Smile / EyebrowRaise / HeadTilt",
                "visual_hook": "Dark fantasy power: Necromancer Stygian Skull Crown unleashes swirling necrotic soulfire under creator command."
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


def select_channel_archetype(account_id: str, history: list, exclude_archetypes: list = None) -> tuple:
    """
    Analyzes publication history across the entire fleet and deterministically selects
    the least-recently-used archetype to guarantee 100% rotating diversity across all
    viral topics without repetition. ALL accounts (1, 2, 3, 4, 5+) have full access to
    all 12 viral omni-niche categories (Beauty, Astronaut/Space, Games, Retro, Greek, Gothic, etc.).
    Supports exclude_archetypes to prevent repeating a failed concept during retry attempts.
    Returns: (selected_archetype_dict, banned_recent_nouns)
    """
    aid = str(account_id)
    excluded = set(exclude_archetypes or [])

    # Aggregate master pool of all archetypes across all 12 channels
    all_archetypes = []
    for cid, spec in CHANNEL_PROMPT_MATRICES.items():
        for arch in spec["archetypes"]:
            a = dict(arch)
            a["channel_id"] = cid
            a["channel_name"] = spec["channel_name"]
            a["genre"] = spec["genre"]
            all_archetypes.append(a)

    acc_lenses = [x for x in history if str(x.get("account_id")) == aid]

    # Track usage counts and timestamps across entire fleet and this account
    fleet_counts = {a["id"]: 0 for a in all_archetypes}
    fleet_last_ts = {a["id"]: "" for a in all_archetypes}
    acc_counts = {a["id"]: 0 for a in all_archetypes}

    for lens in history:
        full_text = (lens.get("lens_name", "") + " " + lens.get("prompt", "")).lower()
        ts = lens.get("timestamp", "")
        for a in all_archetypes:
            if any(tok in full_text for tok in a["signature_tokens"]):
                fleet_counts[a["id"]] += 1
                if ts > fleet_last_ts[a["id"]]:
                    fleet_last_ts[a["id"]] = ts

    for lens in acc_lenses:
        full_text = (lens.get("lens_name", "") + " " + lens.get("prompt", "")).lower()
        for a in all_archetypes:
            if any(tok in full_text for tok in a["signature_tokens"]):
                acc_counts[a["id"]] += 1

    # Detect channel of the account's most recent published lens to enforce cross-genre alternation
    last_acc_channel = None
    if acc_lenses:
        last_lens_text = (acc_lenses[-1].get("lens_name", "") + " " + acc_lenses[-1].get("prompt", "")).lower()
        for a in all_archetypes:
            if any(tok in last_lens_text for tok in a["signature_tokens"]):
                last_acc_channel = a["channel_id"]
                break

    # Universal Omni-Niche Fleet: ALL accounts cater to ALL 12 top viral genres:
    # 1. Mythic Beasts & Celestial Crowns (Channel 1)
    # 2. Cyberpunk HUD & 90s Camcorder VHS Glitch Optics (Channel 2)
    # 3. Viral Memes & Kinetic Morphs (Channel 3: Gigachad, crying stormclouds, melodrama waterfall)
    # 4. Haute Couture & 35mm Analog Luxury (Channel 4: 24k gold leaf, freshwater pearls, Portra 400 grain)
    # 5. Y3K Zero-G Liquid Chrome & Morphing Mercury (Channel 5: Mercury halos, ferrofluid, fluid ripples)
    # 6. Interactive AR Games & Challenges (Channel 6: Head-tilt speeder, coin-catcher, reaction timing meter)
    # 7. Decades Nostalgia & Retro (Channel 7: 70s Disco, 80s Synthwave grid, 90s Hi-8 VHS, Y2K butterflies)
    # 8. Greek & Ancient Mythology (Channel 8: Zeus thunder laurel, Medusa bronze serpents, Aphrodite pearls)
    # 9. Aesthetic Beauty & Glow (Channel 9: Glass skin, golden hour sunset, euphoria rhinestones, angel aura)
    # 10. Cosmic Space & Astronaut (Channel 10: Apollo gold-visor helmet, orbiting planetarium, nebula dome)
    # 11. Viral Randomizer Wheels (Channel 11: Celestial tarot wheel, which vibe picker, aura scanner)
    # 12. Gothic Dark Fantasy (Channel 12: Vampire fangs, blood moon coronet, phantom wraith shroud)
    # Enforces strict cross-genre rotation so the same account never publishes the same genre back-to-back,
    # and diversifies away from the fleet's most recently published topic.
    most_recent_other_channel = None
    for other_x in reversed(history):
        if str(other_x.get("account_id")) != aid:
            other_text = (other_x.get("lens_name", "") + " " + other_x.get("prompt", "")).lower()
            for a in all_archetypes:
                if any(tok in other_text for tok in a["signature_tokens"]):
                    most_recent_other_channel = a["channel_id"]
                    break
            if most_recent_other_channel:
                break

    candidates = [a for a in all_archetypes if a["channel_id"] != last_acc_channel and a["id"] not in excluded]
    if most_recent_other_channel:
        distinct_candidates = [a for a in candidates if a["channel_id"] != most_recent_other_channel]
        if distinct_candidates:
            candidates = distinct_candidates
    if not candidates:
        candidates = [a for a in all_archetypes if a["id"] not in excluded] or all_archetypes

    # Calculate category publication counts for account and entire fleet
    cat_acc_counts = {cid: 0 for cid in CHANNEL_PROMPT_MATRICES}
    cat_fleet_counts = {cid: 0 for cid in CHANNEL_PROMPT_MATRICES}
    for a in all_archetypes:
        cat_acc_counts[a["channel_id"]] += acc_counts[a["id"]]
        cat_fleet_counts[a["channel_id"]] += fleet_counts[a["id"]]

    # Category-First Deterministic LRU Selection:
    # 1. Least used CATEGORY by this account (ensures every account rotates through all 12 categories equally)
    # 2. Least used CATEGORY across entire fleet
    # 3. Least used archetype across fleet
    # 4. Least used archetype on this account
    # 5. Oldest publication timestamp
    # 6. Uniform hash distribution across remaining candidates
    import hashlib
    selected = min(
        candidates,
        key=lambda a: (
            cat_acc_counts[a["channel_id"]],
            cat_fleet_counts[a["channel_id"]],
            fleet_counts[a["id"]],
            acc_counts[a["id"]],
            fleet_last_ts[a["id"]] != "",
            fleet_last_ts[a["id"]],
            int(hashlib.md5((aid + str(len(history)) + a["id"]).encode()).hexdigest()[:8], 16)
        )
    )

    # Extract nouns from the most recent 6 lenses across the ENTIRE fleet to dynamically ban
    banned_nouns = set()
    for lens in history[-6:]:
        title = lens.get("lens_name", "")
        for word in re.findall(r'[A-Za-z]{4,}', title):
            w_lower = word.lower()
            if w_lower not in ["halo", "lens", "crown", "face", "gold", "light", "filter", "35mm", "pulse", "echo"]:
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

        # Toxic HUD & Telemetry tokens (trigger AILC 2D UI text and TWEEN.now crashes)
        (r'\b(?:biometric\s+)?(?:lock\s+|telemetry\s+)?indicators?\b', 'particle glints'),
        (r'\b(?:biometric|flight|tactical|orbital|laser)\s+telemetry\b', 'holographic beam flare'),
        (r'\btelemetry\s+(?:glyphs?|readouts?|cascade)\b', 'volumetric light motes'),
        (r'\btelemetry\b', 'prismatic light flare'),
        (r'\b(?:optic\s+|laser\s+)?diagnostic(?:\s+data\s+stream|\s+glow|\s+flare|\s+pulse)?\b', 'neon frame glow'),
        (r'\b(?:hud\s+)?readouts?\b', 'prism glass flare'),
        (r'\bdata\s+stream\b', 'photon stream'),
        (r'\btarget(?:ing)?\s+reticles?\b', 'holographic focus ring'),
        (r'\btarget-lock\s+brackets?\b', 'optical prism highlights'),
        (r'\boverdrive\b', 'kinetic surge'),
        (r'\bcooldowns?\b', 'instant reaction'),

        # Facial obstruction & veil/mist patterns (strictly scrubbed to protect Gate 7 & Vision Judge)
        (r'\b(?:delicate\s+|golden\s+|gossamer\s+|silk\s+|starlight\s+)?veils?\b', 'particle aura'),
        (r'\b(?:arctic\s+|frosted\s+|dense\s+|thick\s+)?mists?\b', 'auroral sparkles'),
        (r'\b(?:dense\s+|thick\s+)?fogs?\b', 'ambient lighting'),
        (r'\b(?:dense\s+|toxic\s+)?hazes?\b', 'subtle bloom'),
        (r'\b(?:face\s+)?masks?\b', 'forehead crest'),
        (r'\bface\s+paint\b', 'forehead jewel'),
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
    Validates candidate lens concept against 8 strict quality and anti-repetition rules.
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

    # Rule 8: Zero HUD Text, Telemetry, Diagnostic, Indicators (Anti-UI text slop)
    banned_ui_tokens = [
        "telemetry", "diagnostic", "indicator", "indicators", "readout",
        "data stream", "reticle grid", "biometric lock", "overdrive"
    ]
    if any(tok in prompt.lower() for tok in banned_ui_tokens):
        return False, "Contains forbidden HUD/telemetry/diagnostic terminology causing 2D UI slop"

    # Rule 9: Zero Facial Obstruction / Veils / Mist (Anti-Gate-7-reject)
    banned_face_obstruction_tokens = [
        "veil", "gossamer veil", "silk veil", "face mask", "full mask",
        "frosted mist", "arctic mist", "dense fog", "face paint"
    ]
    if any(tok in prompt.lower() for tok in banned_face_obstruction_tokens):
        return False, "Contains forbidden facial obstruction terminology (veil/mist/mask) causing Gate 7 failure"

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
def generate_lens_prompt(account_id: str = "1", custom_instructions: str = "", exclude_archetypes: list = None) -> dict:
    aid = str(account_id)
    history = load_published_history("published_lenses.json")
    selected_archetype, banned_nouns = select_channel_archetype(aid, history, exclude_archetypes=exclude_archetypes)
    arch_channel_id = selected_archetype.get("channel_id", aid)
    spec = CHANNEL_PROMPT_MATRICES.get(arch_channel_id, CHANNEL_PROMPT_MATRICES.get(aid, CHANNEL_PROMPT_MATRICES["1"]))

    api_keys = get_gemini_api_keys()

    dials = spec["craft_dials"]
    dials_str = (
        f"DESIGN_VARIANCE: {dials['design_variance']:.2f} (High architectural novelty)\n"
        f"VISUAL_DENSITY: {dials['visual_density']:.2f} (Rich PBR textures, caustic shaders, 3-point contrast lighting)\n"
        f"MOTION_INTENSITY: {dials['motion_intensity']:.2f} (Kinetic face-event responses)"
    )

    system_prompt = (
        "You are an Elite Snapchat AR Director and Principal Prompt Engineer for Snapchat EasyLens (Lens Studio Web SnapML/AILC).\n"
        "Your mission is to engineer an insanely high-converting, viral, anti-slop, compliance-verified Lens prompt for the top <1% of Snapchat creators.\n\n"
        "STRICT PRODUCTION QUALITY, VIRALITY & COMPLIANCE RULES:\n"
        "1. MASSIVE VISUAL IMPACT & BOLD SILHOUETTE DEFINITION: Instantaneous 0.2s silhouette read on Snapchat carousel. Primary 3D asset must have bold, recognizable structural geometry framing the face (sculpted crowns, retro cyber visors, weightless zero-g halos, hand-painted cloud crowns). High contrast lighting, unmistakable visual hook that compels users to tap, favorite, and subscribe.\n"
        "2. MULTI-ACTION INTERACTIVE TRIGGER MATRIX: Prompts MUST specify dynamic payoffs for multiple face events:\n"
        "   - MouthOpen: Explosive high-energy climax (particle torrent, geyser, glitch shockwave, crystal prism burst, expanding shockwave rings).\n"
        "   - Smile: Harmonic positive payoff (golden sparkle dust, auroral eye glints, cheerful mascot reaction, rainbow confetti).\n"
        "   - EyebrowRaise / HeadTilt: Dynamic secondary reaction (spire extension, night-vision beam flare, scanline shift, fluid inertia drift).\n"
        "3. ZERO ON-SCREEN DEVELOPER UI, SLIDERS, OR BUTTONS: 100% immersive full-screen camera AR. NEVER generate touch sliders, debug menus, or controller UI widgets.\n"
        "4. ZERO ON-SCREEN TEXT, LABELS, HUD OVERLAYS, TELEMETRY, OR INDICATORS: Do NOT render any text, subtitles, numbers, percentages, badges, diagnostic telemetry, or status indicators. NEVER use words like 'telemetry', 'diagnostic', 'indicators', 'HUD readout', 'data stream', 'reticle grid', 'biometric lock'. All elements must be 100% pure wearable 3D geometry and volumetric 3D particle systems.\n"
        "5. 100% ANTI-SLOP ENFORCEMENT: Strictly ban generic purple gradients, floating disembodied blobs, rubbery plastic textures, and 2D canvas spinners. Enforce authentic physical materials (24k gold leaf, freshwater pearls, liquid mercury, brushed titanium, Portra 400 analog grain, Ghibli cel-shading).\n"
        "6. MANDATORY PBR CRAFT & 3-POINT CONTRAST LIGHTING: Key light + contrasting 6500K/2800K directional rim lighting + ray-traced contact shadows.\n"
        "7. MANDATORY FRONT-CAMERA SELFIE ANCHORING: Primary 3D asset MUST anchor directly to HEAD or FOREHEAD (sculpted crown, halo, visor, helmet, or horns spanning temple-to-temple). NEVER cover, obstruct, or place veils, masks, mists, or cloth over the nose, mouth, or central face. Keep nose, mouth, and eyes completely unobscured so facial tracking and expression remain 100% visible.\n"
        "8. STRICT JAVASCRIPT ENGINE COMPATIBILITY (ZERO TWEEN / ZERO EASING CURVES):\n"
        "   - NEVER use the words 'smooth tween', 'bezier curve', 'ease-in', 'ease-out', or 'easing curve'. Use discrete visual triggers and particle streams only.\n"
        "9. STRICT PROMPT LENGTH CONSTRAINT: The 'prompt' field MUST be between 300 and 460 characters (hard backend limit is 480).\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "lens_name": "Unique 2-4 word Title without trademarked terms",\n'
        '  "prompt": "Dense, single-paragraph EasyLens prompt between 300 and 460 characters",\n'
        '  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],\n'
        '  "visual_hook": "1-line explanation of the 0.2s psychological hook",\n'
        '  "trigger_sequence": "1-line explanation of the multi-action trigger payoffs (mouth open, smile, eyebrow raise, head tilt)"\n'
        "}"
    )
    recent_fleet_lines = [
        f"- '{item.get('lens_name')}' (Acc #{item.get('account_id')}): {item.get('visual_hook', '')}"
        for item in history[-12:]
    ]

    user_prompt = (
        f"TARGET ACCOUNT: Account #{aid} (Universal Multi-Niche Rotation via {spec['channel_name']})\n"
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
            "in the title or prompt, as they were used in recent lenses across the fleet. Synthesize fresh nomenclature!\n\n"
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
        "account_id": aid,
        "channel_id": arch_channel_id,
        "genre": spec["genre"],
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
                        result["account_id"] = aid
                        result["channel_id"] = arch_channel_id
                        result["genre"] = spec["genre"]
                        result["craft_dials"] = dials
                        if not result.get("visual_hook"):
                            result["visual_hook"] = selected_archetype.get("visual_hook", f"Massive visual impact: bold 3D {result.get('lens_name', 'crown')} frames the face in 0.2s.")
                        if not result.get("trigger_sequence"):
                            result["trigger_sequence"] = selected_archetype.get("primary_trigger", "MouthOpen / Smile / EyebrowRaise / HeadTilt")
                        if not result.get("tags"):
                            result["tags"] = list(spec.get("tag_pool", ["3d", "pbr", "face"]))
                        print(f"[GEMINI OK] Model: {model_name}")
                        print(f"[GEMINI OK] Generated Lens: {result.get('lens_name')}")
                        print(f"[GEMINI OK] Archetype: {selected_archetype['id']}")
                        print(f"[GEMINI OK] Genre: {spec['genre']}")
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
