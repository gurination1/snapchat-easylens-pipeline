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
                "focus": "High-fashion Parisian couture 24k gold leaf baroque crown fitted to hairline with draped raw freshwater pearls and caustic crystal prisms. Warm Kodak Portra 400 film grain with halation bloom. Opening mouth parts golden gossamer veil with champagne spark motes; smiling cascades rich golden sparkle dust across cheekbones; eyebrow raise triggers luminous dewy skin sheen; head tilt catches prismatic diamond dispersion. Pure Parisian luxury, zero UI.",
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
                "name": "Art Nouveau Emerald Tiara & Shimmering Gossamer Veil",
                "signature_tokens": ['art nouveau', 'emerald cabochon', 'gossamer veil', 'paris couture'],
                "focus": "Art Nouveau floral tiara sculpted from antiqued yellow gold with deep emerald cabochon accents anchored securely to brow. Soft 35mm analog vignette with delicate warm highlights. Opening mouth floats semi-translucent golden silk shimmer veil across temples; smiling activates emerald light refraction flares across eye contours; eyebrow raise blooms golden floral petals; head tilt glints emerald cabochons. Parisian couture, zero UI.",
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
                "signature_tokens": ['rose gold tiara', 'astral starburst', 'morganite', 'starlight veil'],
                "focus": "Hand-forged 18k rose gold astral starburst tiara anchored along brow with inset morganite gemstones. Portra film warmth with soft halation. Opening mouth releases cascading micro-glitter starlight veil; smiling triggers dazzling rose-gold starburst flares across eyes; eyebrow raise pulses blushing astral starlight halo; head tilt cascades warm morganite gemstone reflections across temples. Pure vanity elegance, zero UI.",
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
    viral topics without repetition. Accounts 1 & 2 rotate dynamically across all 5 viral genres.
    Supports exclude_archetypes to prevent repeating a failed concept during retry attempts.
    Returns: (selected_archetype_dict, banned_recent_nouns)
    """
    aid = str(account_id)
    excluded = set(exclude_archetypes or [])

    # Aggregate master pool of all 50 archetypes across all 5 channels
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

    # Accounts 1 & 2 operate in Universal Rotating Fleet mode across all genres
    if aid in ["1", "2"]:
        candidates = [a for a in all_archetypes if a["channel_id"] != last_acc_channel and a["id"] not in excluded]
        if not candidates:
            candidates = [a for a in all_archetypes if a["id"] not in excluded]
        if not candidates:
            candidates = all_archetypes
    else:
        # Accounts 3, 4, 5 anchor to their specific specialized studio
        candidates = [a for a in all_archetypes if a["channel_id"] == aid and a["id"] not in excluded]
        if not candidates:
            candidates = [a for a in all_archetypes if a["id"] not in excluded]
        if not candidates:
            candidates = all_archetypes

    # Deterministic LRU selection:
    # 1. Least used across fleet
    # 2. Least used by this account
    # 3. Oldest timestamp ('' is never used, hence oldest)
    selected = min(
        candidates,
        key=lambda a: (
            fleet_counts[a["id"]],
            acc_counts[a["id"]],
            fleet_last_ts[a["id"]] != "",
            fleet_last_ts[a["id"]],
            a["id"]
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
        "   - MouthOpen: Explosive high-energy climax (particle torrent, geyser, glitch shockwave, veil parting, expanding shockwave rings).\n"
        "   - Smile: Harmonic positive payoff (golden sparkle dust, auroral eye glints, cheerful mascot reaction, rainbow confetti).\n"
        "   - EyebrowRaise / HeadTilt: Dynamic secondary reaction (spire extension, night-vision beam flare, scanline shift, fluid inertia drift).\n"
        "3. ZERO ON-SCREEN DEVELOPER UI, SLIDERS, OR BUTTONS: 100% immersive full-screen camera AR. NEVER generate touch sliders, debug menus, or controller UI widgets.\n"
        "4. ZERO ON-SCREEN TEXT, LABELS, HUD OVERLAYS, TELEMETRY, OR INDICATORS: Do NOT render any text, subtitles, numbers, percentages, badges, diagnostic telemetry, or status indicators. NEVER use words like 'telemetry', 'diagnostic', 'indicators', 'HUD readout', 'data stream', 'reticle grid', 'biometric lock'. All elements must be 100% pure wearable 3D geometry and volumetric 3D particle systems.\n"
        "5. 100% ANTI-SLOP ENFORCEMENT: Strictly ban generic purple gradients, floating disembodied blobs, rubbery plastic textures, and 2D canvas spinners. Enforce authentic physical materials (24k gold leaf, freshwater pearls, liquid mercury, brushed titanium, Portra 400 analog grain, Ghibli cel-shading).\n"
        "6. MANDATORY PBR CRAFT & 3-POINT CONTRAST LIGHTING: Key light + contrasting 6500K/2800K directional rim lighting + ray-traced contact shadows.\n"
        "7. MANDATORY FRONT-CAMERA SELFIE ANCHORING: Primary 3D asset MUST anchor directly to HEAD or FACE (forehead, hairline, temples, cheekbones, or brow). NEVER attach to shoulders or full-body. NEVER occlude mouth on mouth-trigger lenses.\n"
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
