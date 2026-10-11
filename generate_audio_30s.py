import numpy as np
import soundfile as sf
from scipy import signal

SR = 44100
DURATION = 30.0
N_SAMPLES = int(SR * DURATION)
BPM = 96.0
BEAT_SEC = 60.0 / BPM  # 0.625s per beat (48 beats in 30.0s — smooth, unhurried pace!)

def midi_to_freq(m):
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))

def add_stereo(mix, sig_l, sig_r, start_sec):
    idx = int(start_sec * SR)
    if idx >= N_SAMPLES or idx < 0:
        return
    n = min(len(sig_l), N_SAMPLES - idx)
    if n <= 0:
        return
    mix[idx:idx+n, 0] += sig_l[:n]
    mix[idx:idx+n, 1] += sig_r[:n]

def add_mono(mix, sig, start_sec, pan=0.0):
    angle = (pan + 1.0) * 0.25 * np.pi
    gl = np.cos(angle)
    gr = np.sin(angle)
    add_stereo(mix, sig * gl, sig * gr, start_sec)

def make_kick(duration=0.45, punch=1.0):
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    f_env = 41.0 + 115.0 * np.exp(-t * 34.0) + 150.0 * np.exp(-t * 130.0)
    phase = 2.0 * np.pi * np.cumsum(f_env) / SR
    amp_env = np.exp(-t * 7.2) * (1.0 - np.exp(-t * 800.0))
    body = np.sin(phase) * amp_env
    click = np.sin(2.0 * np.pi * 1600.0 * t) * np.exp(-t * 170.0) * 0.22
    return np.tanh((body + click) * 1.7 * punch) * 0.72

def make_snare(duration=0.28, snappy=1.0):
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    f_env = 170.0 + 80.0 * np.exp(-t * 50.0)
    phase = 2.0 * np.pi * np.cumsum(f_env) / SR
    body = np.sin(phase) * np.exp(-t * 22.0) * 0.50
    rng = np.random.default_rng(int(snappy * 1000) + 42)
    noise = rng.standard_normal(len(t))
    b, a = signal.butter(2, [850 / (SR/2), 9000 / (SR/2)], btype='band')
    filtered_noise = signal.lfilter(b, a, noise)
    noise_env = np.exp(-t * 14.0) * (1.0 - np.exp(-t * 450.0))
    return np.tanh((body + filtered_noise * noise_env * 0.60 * snappy) * 1.35) * 0.50

def make_hihat(duration=0.09, open_hat=False):
    dur = 0.32 if open_hat else duration
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    rng = np.random.default_rng(101)
    noise = rng.standard_normal(len(t))
    metallic = (np.sin(2*np.pi*3420*t) + np.sin(2*np.pi*5180*t) + np.sin(2*np.pi*7810*t)) * 0.18
    b, a = signal.butter(3, 6500 / (SR/2), btype='high')
    hp = signal.lfilter(b, a, noise + metallic)
    decay = 9.5 if open_hat else 48.0
    env = np.exp(-t * decay) * (1.0 - np.exp(-t * 800.0))
    return hp * env * 0.20

def make_gps_ping(freq=1320.0, duration=0.42):
    """Crystalline sonar/GPS location pin lock sound effect."""
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    env = (1.0 - np.exp(-t * 350.0)) * np.exp(-t * 8.5)
    sig = (np.sin(2 * np.pi * freq * t) +
           0.45 * np.sin(2 * np.pi * (freq * 1.5) * t) * np.exp(-t * 14.0) +
           0.25 * np.sin(2 * np.pi * (freq * 2.0) * t) * np.exp(-t * 20.0)) * env
    return sig * 0.24

def make_whoosh(duration=0.48, f_start=260.0, f_end=2200.0):
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    rng = np.random.default_rng(777)
    noise = rng.standard_normal(n)
    out = np.zeros(n)
    n_seg = 16
    seg_len = n // n_seg
    for i in range(n_seg):
        frac = i / max(1, n_seg - 1)
        fc = f_start * ((f_end / f_start) ** frac)
        low = max(80.0, fc * 0.6) / (SR / 2)
        high = min(0.95, (fc * 1.6) / (SR / 2))
        b, a = signal.butter(2, [low, high], btype='band')
        s0 = i * seg_len
        s1 = n if i == n_seg - 1 else (i + 1) * seg_len
        out[s0:s1] = signal.lfilter(b, a, noise[s0:s1])
    env = np.sin(np.pi * (t / duration)) ** 1.6
    f_sub = np.linspace(f_start * 0.35, f_end * 0.15, n)
    sub = np.sin(2 * np.pi * np.cumsum(f_sub) / SR) * env * 0.22
    return (out * env * 0.42 + sub) * 0.50

def make_bass_note(midi_note, duration=0.30, cutoff_mult=3.8):
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    f0 = midi_to_freq(midi_note)
    sig = np.sin(2 * np.pi * f0 * t) * 0.78
    for k in range(2, 12):
        fk = f0 * k
        if fk > SR * 0.42:
            break
        harm_env = np.exp(-t * (3.5 + k * cutoff_mult))
        sig += ((-1)**k / k) * np.sin(2 * np.pi * fk * t) * harm_env * 0.58
    amp_env = (1.0 - np.exp(-t * 220.0)) * np.exp(-t * 4.5)
    return np.tanh(sig * amp_env * 1.8) * 0.34

def make_chord_pad(midi_notes, duration=3.5, bright=1.0):
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    sig_l = np.zeros(n)
    sig_r = np.zeros(n)
    for idx_n, m in enumerate(midi_notes):
        f0 = midi_to_freq(m)
        for detune, target in [(-0.0035, sig_l), (0.0035, sig_r), (0.0012 * ((-1)**idx_n), sig_l), (-0.0012 * ((-1)**idx_n), sig_r)]:
            f = f0 * (1.0 + detune)
            for k in range(1, 8):
                if f * k > SR * 0.4:
                    break
                h_env = np.exp(-t * (0.7 + k * (1.4 / bright)))
                target += (1.0 / (k ** 1.2)) * np.sin(2 * np.pi * f * k * t + idx_n) * h_env
    # Smooth swell attack and long warm release
    env = (1.0 - np.exp(-t * 12.0)) * np.exp(-t * 0.95)
    return np.tanh(sig_l * env * 0.20) * 0.30, np.tanh(sig_r * env * 0.20) * 0.30

def make_sub_drop(duration=3.2):
    n = int(SR * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    f_env = 34.0 + 70.0 * np.exp(-t * 2.4) + 110.0 * np.exp(-t * 22.0)
    phase = 2.0 * np.pi * np.cumsum(f_env) / SR
    env = (1.0 - np.exp(-t * 350.0)) * np.exp(-t * 0.95)
    return np.tanh(np.sin(phase) * env * 1.8) * 0.65

def build_soundtrack_30s():
    mix = np.zeros((N_SAMPLES, 2), dtype=np.float64)

    # ---------------------------------------------------------
    # SCENE 1 (0.0s - 4.0s): SATELLITE LOCK & INITIALIZATION
    # ---------------------------------------------------------
    for i in range(4):
        t_b = i * 1.0
        add_mono(mix, make_gps_ping(880.0 if i < 3 else 1320.0, 0.35), t_b, pan=(-0.3 if i % 2 == 0 else 0.3))
        add_mono(mix, make_kick(0.35, punch=0.75), t_b)
    add_mono(mix, make_whoosh(1.2, 200.0, 1800.0), 2.8)

    # ---------------------------------------------------------
    # SMOOTH GROOVE: 4.0s to 25.0s (96 BPM = 0.625s per beat)
    # ---------------------------------------------------------
    total_beats = int((25.0 - 4.0) / BEAT_SEC)
    bass_notes_cycle = [29, 29, 32, 36, 37, 37, 36, 31]  # F1, Ab1, C2, Db2, C2, G1

    for b_i in range(total_beats):
        t_beat = 4.0 + b_i * BEAT_SEC
        # Kick on every beat
        add_mono(mix, make_kick(0.42, punch=1.0), t_beat)
        # Snare on odd beats
        if b_i % 2 == 1:
            add_mono(mix, make_snare(0.26, snappy=1.0), t_beat)
        # Smooth 8th-note hi-hats
        for sub in range(2):
            t_sub = t_beat + sub * (BEAT_SEC * 0.5)
            add_mono(mix, make_hihat(open_hat=(sub == 1)), t_sub, pan=(-0.2 if sub == 0 else 0.2))
        # Bass note on beat and off-beat
        m_note = bass_notes_cycle[b_i % len(bass_notes_cycle)]
        add_mono(mix, make_bass_note(m_note, duration=0.28), t_beat)
        add_mono(mix, make_bass_note(m_note + 12, duration=0.20, cutoff_mult=4.5) * 0.7, t_beat + BEAT_SEC * 0.5)

    # Lush Warm Chords on Scene Changes
    chord_events = [
        (4.0,  [53, 56, 60, 63, 67], 4.5),  # Scene 2: Manifesto (Fm9)
        (8.5,  [49, 56, 60, 65, 68], 6.0),  # Scene 3: Frontend Skill Map (Dbmaj9)
        (14.5, [46, 53, 58, 61, 65], 6.0),  # Scene 4: Backend Skill Map (Bbm9)
        (20.5, [48, 55, 60, 63, 67], 4.8),  # Scene 5: Global Master Skill Map (Cm9)
    ]
    for t_c, notes, dur_c in chord_events:
        cl, cr = make_chord_pad(notes, duration=dur_c, bright=1.15)
        add_stereo(mix, cl, cr, t_c)
        add_mono(mix, make_whoosh(0.55, 220.0, 2100.0), max(0.0, t_c - 0.25))

    # ---------------------------------------------------------
    # GPS LOCATION PIN LOCK PINGS (Scenes 3, 4 & 5: 8.5s - 25.0s)
    # ---------------------------------------------------------
    # Scene 3: 6 Frontend Skill Pins (8.5s to 14.5s -> one pin every 0.9s)
    fe_ping_notes = [72, 75, 77, 79, 80, 84]
    for idx_p, m_p in enumerate(fe_ping_notes):
        t_p = 8.8 + idx_p * 0.90
        pan_p = -0.6 + idx_p * 0.22
        add_mono(mix, make_gps_ping(midi_to_freq(m_p), 0.45), t_p, pan=pan_p)

    # Scene 4: 6 Backend Skill Pins (14.5s to 20.5s -> one pin every 0.9s)
    be_ping_notes = [70, 72, 75, 77, 80, 84]
    for idx_p, m_p in enumerate(be_ping_notes):
        t_p = 14.8 + idx_p * 0.90
        pan_p = -0.5 + idx_p * 0.20
        add_mono(mix, make_gps_ping(midi_to_freq(m_p), 0.45), t_p, pan=pan_p)

    # Scene 5 (20.5s - 25.5s): Global Map Data Highway Arpeggio + Pre-Finale Riser
    arp_notes = [60, 63, 67, 72, 75, 79, 84, 79, 75, 72, 68, 72, 75, 80, 84, 87]
    for i, m_a in enumerate(arp_notes):
        t_a = 20.6 + i * 0.27
        add_mono(mix, make_gps_ping(midi_to_freq(m_a), 0.28) * 0.65, t_a, pan=np.sin(i * 0.7) * 0.55)

    # Smooth Riser into Finale at 25.5s
    add_mono(mix, make_whoosh(1.6, 250.0, 3600.0), 23.8)

    # ---------------------------------------------------------
    # SCENE 6 (25.5s - 30.0s): GRAND FINALE LOGO REVEAL
    # ---------------------------------------------------------
    add_mono(mix, make_sub_drop(3.8), 25.5)
    add_mono(mix, make_kick(0.50, punch=1.35), 25.5)
    add_mono(mix, make_snare(0.35, snappy=1.25) * 0.85, 25.5)
    fin_l, fin_r = make_chord_pad([41, 53, 56, 60, 63, 67, 72, 75], duration=4.3, bright=1.4)
    add_stereo(mix, fin_l * 1.35, fin_r * 1.35, 25.5)
    for idx_c, (tc, m_chime) in enumerate([(25.5, 77), (25.9, 80), (26.3, 84)]):
        add_mono(mix, make_gps_ping(midi_to_freq(m_chime), 0.9) * 0.75, tc, pan=(idx_c - 1) * 0.4)

    # Stereo echo & master polish
    delay_samples = int(0.25 * SR)
    wet_l = np.zeros(N_SAMPLES)
    wet_r = np.zeros(N_SAMPLES)
    wet_l[delay_samples:] = mix[:-delay_samples, 1] * 0.18
    wet_r[delay_samples:] = mix[:-delay_samples, 0] * 0.18
    mix[:, 0] += wet_l
    mix[:, 1] += wet_r

    # Smooth fade out in last 1.2s (28.8s -> 30.0s)
    fade_len = int(1.2 * SR)
    fade_curve = np.linspace(1.0, 0.0, fade_len) ** 1.8
    mix[-fade_len:, :] *= fade_curve[:, None]

    mix = np.tanh(mix * 1.12)
    peak = np.max(np.abs(mix))
    if peak > 0:
        mix = mix / peak * 0.89

    sf.write("soundtrack_30s.wav", mix, SR, subtype='PCM_16')
    print(f"30s Soundtrack generated: {DURATION}s, {SR}Hz, peak={np.max(np.abs(mix)):.3f}")

if __name__ == "__main__":
    build_soundtrack_30s()
