import os
import subprocess
import numpy as np
from scipy.io import wavfile

SAMPLE_RATE = 44100
DURATION = 3.60  # Exact match for test_portrait.mp4
NUM_SAMPLES = int(SAMPLE_RATE * DURATION)
T = np.linspace(0, DURATION, NUM_SAMPLES, endpoint=False)

def export_to_mp3(wav_path, mp3_path):
    cmd = [
        "ffmpeg", "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        mp3_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if os.path.exists(wav_path):
        os.remove(wav_path)

def create_mythic_roar():
    # 1. Low sub-bass drone with slow modulation (40-48Hz)
    sub = np.sin(2 * np.pi * (44 + 4 * np.sin(2 * np.pi * 0.8 * T)) * T) * 0.4
    
    # 2. Taiko drum hits at t = 0.15s, 1.2s, 2.4s
    drums = np.zeros(NUM_SAMPLES)
    hit_times = [0.15, 1.20, 2.40]
    for ht in hit_times:
        idx = int(ht * SAMPLE_RATE)
        hit_len = int(0.6 * SAMPLE_RATE)
        t_hit = np.linspace(0, 0.6, hit_len, endpoint=False)
        pitch_drop = 120 * np.exp(-t_hit * 12) + 55
        body = np.sin(2 * np.pi * pitch_drop * t_hit) * np.exp(-t_hit * 5.5)
        noise = np.random.uniform(-0.3, 0.3, hit_len) * np.exp(-t_hit * 25)
        hit = (body + noise) * 0.7
        end_idx = min(NUM_SAMPLES, idx + hit_len)
        drums[idx:end_idx] += hit[:end_idx - idx]

    # 3. Mythic dragon brass/roar harmonic swell (t = 1.3s to 2.8s)
    roar = np.zeros(NUM_SAMPLES)
    r_start = int(1.3 * SAMPLE_RATE)
    r_end = int(2.9 * SAMPLE_RATE)
    r_len = r_end - r_start
    t_r = np.linspace(0, 1.6, r_len, endpoint=False)
    env_r = np.sin(np.pi * (t_r / 1.6)) ** 2
    f_base = 75 + 30 * np.sin(2 * np.pi * 1.5 * t_r)
    h1 = np.sin(2 * np.pi * f_base * t_r)
    h2 = 0.6 * np.sin(2 * np.pi * (f_base * 2.01) * t_r)
    h3 = 0.4 * np.sin(2 * np.pi * (f_base * 3.02) * t_r)
    h4 = 0.25 * np.sin(2 * np.pi * (f_base * 4.05) * t_r)
    growl_mod = 1.0 + 0.35 * np.sin(2 * np.pi * 35 * t_r)
    r_audio = (h1 + h2 + h3 + h4) * env_r * growl_mod * 0.55
    roar[r_start:r_end] = r_audio

    # Mix & panning (stereo)
    left = sub * 0.8 + drums * 0.9 + roar * 0.85
    right = sub * 0.8 + drums * 0.9 + roar * 0.95
    
    # Fade in/out
    fade_in = np.minimum(1.0, np.linspace(0, 1, int(SAMPLE_RATE * 0.08)))
    fade_out = np.minimum(1.0, np.linspace(1, 0, int(SAMPLE_RATE * 0.15)))
    env = np.ones(NUM_SAMPLES)
    env[:len(fade_in)] = fade_in
    env[-len(fade_out):] = fade_out

    audio_stereo = np.column_stack([left * env, right * env])
    audio_stereo = audio_stereo / (np.max(np.abs(audio_stereo)) + 1e-6) * 0.92
    return (audio_stereo * 32767).astype(np.int16)

def create_cyber_pulse():
    # 1. 130 BPM Electro kick (interval = 60 / 130 = 0.4615s)
    kick = np.zeros(NUM_SAMPLES)
    kick_times = np.arange(0.1, DURATION - 0.2, 0.4615)
    for kt in kick_times:
        idx = int(kt * SAMPLE_RATE)
        k_len = int(0.25 * SAMPLE_RATE)
        t_k = np.linspace(0, 0.25, k_len, endpoint=False)
        pitch = 160 * np.exp(-t_k * 22) + 50
        click = np.sin(2 * np.pi * 900 * t_k) * np.exp(-t_k * 80) * 0.4
        thump = np.sin(2 * np.pi * pitch * t_k) * np.exp(-t_k * 10)
        hit = (click + thump) * 0.6
        end_idx = min(NUM_SAMPLES, idx + k_len)
        kick[idx:end_idx] += hit[:end_idx - idx]

    # 2. 16th-note sawtooth bassline
    bass = np.zeros(NUM_SAMPLES)
    step = 0.4615 / 4.0
    notes = [55, 55, 65.4, 55, 73.4, 55, 82.4, 73.4, 55, 55, 65.4, 55, 87.3, 82.4, 73.4, 65.4]
    for i in range(int(DURATION / step)):
        bt = i * step
        idx = int(bt * SAMPLE_RATE)
        n_len = int(step * 0.85 * SAMPLE_RATE)
        t_b = np.linspace(0, step * 0.85, n_len, endpoint=False)
        freq = notes[i % len(notes)]
        saw = 2 * (t_b * freq - np.floor(t_b * freq + 0.5))
        env_b = np.exp(-t_b * 12)
        end_idx = min(NUM_SAMPLES, idx + n_len)
        bass[idx:end_idx] += saw[:end_idx - idx] * env_b[:end_idx - idx] * 0.25

    # 3. Riser + Laser discharge at t = 1.3s to 2.2s
    laser = np.zeros(NUM_SAMPLES)
    l_idx = int(1.4 * SAMPLE_RATE)
    l_len = int(0.8 * SAMPLE_RATE)
    t_l = np.linspace(0, 0.8, l_len, endpoint=False)
    # Riser
    riser = np.sin(2 * np.pi * (200 + 1600 * (t_l / 0.8) ** 2) * t_l) * (t_l / 0.8) * 0.35
    # Zap discharge
    zap_start = int(0.4 * SAMPLE_RATE)
    t_z = t_l[zap_start:] - t_l[zap_start]
    zap = np.sin(2 * np.pi * (2800 * np.exp(-t_z * 18)) * t_z) * np.exp(-t_z * 8) * 0.6
    riser[zap_start:] += zap
    end_idx = min(NUM_SAMPLES, l_idx + l_len)
    laser[l_idx:end_idx] = riser[:end_idx - l_idx]

    left = kick * 0.9 + bass * 0.8 + laser * 0.85
    right = kick * 0.9 + bass * 0.8 + laser * 0.95
    audio = np.column_stack([left, right])
    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.92
    return (audio * 32767).astype(np.int16)

def create_comedy_pop():
    # 1. Bouncy spring wobble
    t_sp = np.linspace(0, DURATION, NUM_SAMPLES, endpoint=False)
    wobble_freq = 220 + 70 * np.sin(2 * np.pi * 6.0 * t_sp)
    spring = np.sin(2 * np.pi * wobble_freq * t_sp) * 0.25 * (0.8 + 0.2 * np.sin(2 * np.pi * 1.5 * t_sp))

    # 2. Slide whistle upward glide (t = 0.5s to 1.3s)
    whistle = np.zeros(NUM_SAMPLES)
    w_start = int(0.5 * SAMPLE_RATE)
    w_len = int(0.8 * SAMPLE_RATE)
    t_w = np.linspace(0, 0.8, w_len, endpoint=False)
    freq_w = 400 + 800 * (t_w / 0.8) ** 1.5
    w_snd = np.sin(2 * np.pi * freq_w * t_w) * np.sin(np.pi * t_w / 0.8) * 0.45
    whistle[w_start:w_start + w_len] = w_snd

    # 3. Comic cork pop (t = 1.35s)
    pop = np.zeros(NUM_SAMPLES)
    p_idx = int(1.35 * SAMPLE_RATE)
    p_len = int(0.12 * SAMPLE_RATE)
    t_p = np.linspace(0, 0.12, p_len, endpoint=False)
    p_freq = 600 * np.exp(-t_p * 35) + 120
    pop_snd = np.sin(2 * np.pi * p_freq * t_p) * np.exp(-t_p * 25) * 0.8
    pop[p_idx:p_idx + p_len] = pop_snd

    # 4. Gold coins / crystal drops cascading (t = 1.45s to 3.2s)
    coins = np.zeros(NUM_SAMPLES)
    coin_times = [1.45, 1.62, 1.78, 1.96, 2.15, 2.38, 2.65, 2.95]
    coin_freqs = [2400, 3100, 2650, 3450, 2800, 3600, 2900, 4200]
    for ct, cf in zip(coin_times, coin_freqs):
        c_idx = int(ct * SAMPLE_RATE)
        c_len = int(0.35 * SAMPLE_RATE)
        t_c = np.linspace(0, 0.35, c_len, endpoint=False)
        c_snd = (np.sin(2 * np.pi * cf * t_c) + 0.4 * np.sin(2 * np.pi * (cf * 2.02) * t_c)) * np.exp(-t_c * 12) * 0.35
        end_idx = min(NUM_SAMPLES, c_idx + c_len)
        coins[c_idx:end_idx] += c_snd[:end_idx - c_idx]

    left = spring * 0.6 + whistle * 0.8 + pop * 0.9 + coins * 0.85
    right = spring * 0.6 + whistle * 0.8 + pop * 0.9 + coins * 0.95
    audio = np.column_stack([left, right])
    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.92
    return (audio * 32767).astype(np.int16)

def create_luxury_shimmer():
    # 1. Warm analog electric piano chord (C maj 9: C3, G3, B3, D4, E4)
    chord_freqs = [130.81, 196.00, 246.94, 293.66, 329.63]
    chords = np.zeros(NUM_SAMPLES)
    for cf in chord_freqs:
        chords += np.sin(2 * np.pi * cf * T) * np.exp(-T * 0.4) * 0.15
        chords += np.sin(2 * np.pi * (cf * 2) * T) * np.exp(-T * 0.8) * 0.05

    # 2. Harp glissando upward arpeggio
    harp = np.zeros(NUM_SAMPLES)
    harp_notes = [261.63, 329.63, 392.00, 493.88, 587.33, 659.25, 783.99, 987.77, 1046.50]
    for i, hn in enumerate(harp_notes):
        h_t = 0.3 + i * 0.14
        h_idx = int(h_t * SAMPLE_RATE)
        h_len = int(1.2 * SAMPLE_RATE)
        t_h = np.linspace(0, 1.2, h_len, endpoint=False)
        h_snd = (np.sin(2 * np.pi * hn * t_h) + 0.3 * np.sin(2 * np.pi * hn * 2 * t_h)) * np.exp(-t_h * 4.0) * 0.22
        end_idx = min(NUM_SAMPLES, h_idx + h_len)
        harp[h_idx:end_idx] += h_snd[:end_idx - h_idx]

    # 3. Crystal bell shimmer / sparkle dust (t = 1.4s to 2.9s)
    shimmer = np.zeros(NUM_SAMPLES)
    shim_start = int(1.4 * SAMPLE_RATE)
    shim_len = int(1.5 * SAMPLE_RATE)
    t_s = np.linspace(0, 1.5, shim_len, endpoint=False)
    s_env = np.sin(np.pi * (t_s / 1.5)) ** 2
    f_high = [3520, 4186, 5274, 6300, 7040]
    for fh in f_high:
        shimmer[shim_start:shim_start + shim_len] += np.sin(2 * np.pi * fh * t_s) * s_env * 0.06

    left = chords * 0.8 + harp * 0.85 + shimmer * 0.7
    right = chords * 0.8 + harp * 0.95 + shimmer * 0.85
    audio = np.column_stack([left, right])
    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.92
    return (audio * 32767).astype(np.int16)

def create_mercury_drift():
    # 1. Hypnotic detuned ambient pad (110Hz, 165Hz, 221Hz)
    pad = (
        np.sin(2 * np.pi * 110.0 * T) * 0.25 +
        np.sin(2 * np.pi * 110.6 * T) * 0.25 +
        np.sin(2 * np.pi * 164.8 * T) * 0.20 +
        np.sin(2 * np.pi * 220.0 * T + np.sin(2 * np.pi * 0.5 * T)) * 0.20
    )
    
    # 2. Resonant fluid mercury drops (t = 0.6s, 1.5s, 2.4s)
    drops = np.zeros(NUM_SAMPLES)
    d_times = [0.60, 1.50, 2.40]
    for dt in d_times:
        d_idx = int(dt * SAMPLE_RATE)
        d_len = int(0.7 * SAMPLE_RATE)
        t_d = np.linspace(0, 0.7, d_len, endpoint=False)
        pitch = 850 * np.exp(-t_d * 8) + 240
        drop_snd = np.sin(2 * np.pi * pitch * t_d) * np.exp(-t_d * 6.5) * 0.45
        end_idx = min(NUM_SAMPLES, d_idx + d_len)
        drops[d_idx:end_idx] += drop_snd[:end_idx - d_idx]

    # 3. Singing glass bowl harmonic (t = 1.2s to 3.4s)
    glass = np.zeros(NUM_SAMPLES)
    g_start = int(1.2 * SAMPLE_RATE)
    g_len = int(2.2 * SAMPLE_RATE)
    t_g = np.linspace(0, 2.2, g_len, endpoint=False)
    g_env = np.sin(np.pi * (t_g / 2.2)) ** 2
    glass[g_start:g_start + g_len] = (
        np.sin(2 * np.pi * 1760.0 * t_g) * 0.25 +
        np.sin(2 * np.pi * 3520.0 * t_g) * 0.12
    ) * g_env

    left = pad * 0.75 + drops * 0.85 + glass * 0.7
    right = pad * 0.75 + drops * 0.95 + glass * 0.8
    audio = np.column_stack([left, right])
    audio = audio / (np.max(np.abs(audio)) + 1e-6) * 0.92
    return (audio * 32767).astype(np.int16)

def main():
    out_dir = "/root/snapchat-lens/assets/audio"
    os.makedirs(out_dir, exist_ok=True)
    
    generators = [
        ("mythic_roar", create_mythic_roar),
        ("cyber_pulse", create_cyber_pulse),
        ("comedy_pop", create_comedy_pop),
        ("luxury_shimmer", create_luxury_shimmer),
        ("mercury_drift", create_mercury_drift)
    ]
    
    for name, gen_fn in generators:
        wav_path = os.path.join(out_dir, f"{name}.wav")
        mp3_path = os.path.join(out_dir, f"{name}.mp3")
        print(f"Synthesizing {name}...")
        audio = gen_fn()
        wavfile.write(wav_path, SAMPLE_RATE, audio)
        export_to_mp3(wav_path, mp3_path)
        size = os.path.getsize(mp3_path)
        print(f"Generated {mp3_path} ({size} bytes)")

if __name__ == "__main__":
    main()
