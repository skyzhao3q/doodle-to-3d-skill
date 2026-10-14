"""Procedural sound effects for the flight scenes, synced to motion cues (scripts/sfx_cues.py).

Step 8b. python3 scripts/sfx.py WORK TAG [--whoosh]   WORK/out/TAG_cues.json -> WORK/out/TAG_sfx.wav
Layers: wind bed (louder with speed), a wing flap ("バサッ") on every downstroke, swoop whooshes when the dragon
enters / leaves the frame (--whoosh), and for fire scenes an inhale followed by the blue-fire roar with crackles.
Everything is synthesised from noise and sines, so there are no third-party samples to license.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
rng = np.random.default_rng(7)


def bandpass(x, lo, hi, order=2):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)


def lowpass(x, hi, order=2):
    return sosfilt(butter(order, hi, btype="low", fs=SR, output="sos"), x)


def sweep_bandpass(x, f_lo, f_hi, width=1.6, chunk=512):
    """Bandpass whose centre glides along the per-sample curves f_lo..f_hi (processed in short chunks)."""
    out = np.zeros_like(x)
    centre = np.sqrt(f_lo * f_hi)
    for i in range(0, len(x), chunk):
        c = float(np.clip(centre[min(i, len(x) - 1)], 80, SR / 2.5))
        seg = x[max(0, i - 2048):i + chunk]
        y = bandpass(seg, c / width, min(c * width, SR / 2.2))
        out[i:i + chunk] = y[-len(x[i:i + chunk]):]
    return out


def env_adsr(n, a, d, peak=1.0):
    t = np.arange(n) / SR
    return peak * np.minimum(t / a, 1.0) * np.exp(-np.maximum(t - a, 0) / d)


def place(track, clip, t, gain=1.0):
    i = int(t * SR)
    if i >= len(track):
        return
    j = min(len(track), i + len(clip))
    track[i:j] += gain * clip[:j - i]


def flap(strength=1.0):
    """'バサッ': a soft cloth-like burst plus a low thump."""
    n = int(0.22 * SR)
    noise = bandpass(rng.standard_normal(n), 180, 1400) * env_adsr(n, 0.012, 0.06)
    rustle = bandpass(rng.standard_normal(n), 1500, 4500) * env_adsr(n, 0.004, 0.025) * 0.25
    t = np.arange(n) / SR
    thump = np.sin(2 * np.pi * (95 - 40 * t) * t) * env_adsr(n, 0.004, 0.05) * 0.8
    return strength * (noise + rustle + thump)


def whoosh(dur=0.9, up=True):
    n = int(dur * SR)
    u = np.linspace(0, 1, n)
    bell = np.sin(np.pi * u) ** 2
    f = 350 + 1900 * (np.sin(np.pi * u) if up else 1 - np.sin(np.pi * u))
    return sweep_bandpass(rng.standard_normal(n), f / 1.3, f * 1.3) * bell


def inhale(dur=1.0):
    n = int(dur * SR)
    u = np.linspace(0, 1, n)
    f = 400 + 2400 * u ** 1.5
    amp = u ** 1.8 * (1 - np.clip((u - 0.92) / 0.08, 0, 1))
    return sweep_bandpass(rng.standard_normal(n), f / 1.4, f * 1.4) * amp * 1.4


def fire_roar(env):
    """Roar driven by a per-sample envelope 0..1: rumble + breathy roar + crackles, with an ignition burst."""
    n = len(env)
    rumble = lowpass(np.cumsum(rng.standard_normal(n)) * 0.02, 160)
    rumble /= np.abs(rumble).max() + 1e-9
    jitter = 1 + 0.35 * lowpass(rng.standard_normal(n), 18) / 0.1
    roar = bandpass(rng.standard_normal(n), 250, 2600) * np.clip(jitter, 0.3, 2.0)
    hiss = bandpass(rng.standard_normal(n), 3000, 9000) * 0.25
    crackle = np.zeros(n)
    on = np.nonzero(env > 0.2)[0]
    if len(on):
        for _ in range(int(len(on) / SR * 22)):
            i = rng.choice(on)
            k = int(0.012 * SR)
            crackle[i:i + k] += rng.uniform(0.3, 1.0) * rng.choice([-1, 1]) * np.exp(-np.arange(min(k, n - i)) / (0.002 * SR))
        crackle = bandpass(crackle, 1200, 7000)
    # Ignition: a fast upward whoosh at the first rise of the envelope.
    out = (0.9 * rumble + 0.8 * roar + hiss + 0.6 * crackle) * env
    rise = np.nonzero(env > 0.05)[0]
    if len(rise):
        place(out, whoosh(0.5), rise[0] / SR, 0.9)
    return out


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from common import Work
    work, tag = Work(sys.argv[1]), sys.argv[2]
    cues_path, out_path = work.out / f"{tag}_cues.json", work.out / f"{tag}_sfx.wav"
    use_whoosh = "--whoosh" in sys.argv
    cues = json.load(open(cues_path))
    fps, fr = cues["fps"], cues["frames"]
    dur = len(fr) / fps + 0.6
    n = int(dur * SR)
    t_fr = np.arange(len(fr)) / fps
    t = np.arange(n) / SR

    def per_sample(vals):
        return np.interp(t, t_fr, vals)

    # Motion speed from the root path (units / s).
    x, z = np.array([f["x"] for f in fr]), np.array([f["z"] for f in fr])
    speed = np.hypot(np.gradient(x) * fps, np.gradient(z) * fps)
    speed_s = per_sample(np.convolve(speed, np.ones(9) / 9, mode="same"))

    # Wind bed: two noise bands, slow gusts, swelling with speed.
    gust = 0.6 + 0.4 * lowpass(rng.standard_normal(n), 0.4) / 0.02
    wind = (bandpass(rng.standard_normal(n), 180, 900) + 0.35 * bandpass(rng.standard_normal(n), 1500, 3200))
    wind *= np.clip(gust, 0.2, 1.4) * (0.18 + 0.22 * np.clip(speed_s / 2.0, 0, 1.5))

    # Wing flaps: a downstroke starts where the wing angle (about Z) peaks and starts to fall.
    wing = np.array([f["wing"] for f in fr])
    flaps = np.zeros(n)
    for i in range(1, len(wing) - 1):
        if wing[i] >= wing[i - 1] and wing[i] > wing[i + 1] and wing[i] - wing.min() > 10:
            depth = (wing[i] - wing[i + 1]) * fps / 400  # faster stroke, louder flap
            place(flaps, flap(np.clip(0.6 + depth, 0.6, 1.3)), (i + 1.5) / fps, 0.55)

    # Swoop whooshes: when the dragon crosses into / out of the frame vertically.
    fx = np.zeros(n)
    if use_whoosh:
        inside = np.abs(z) < 2.4
        for i in range(1, len(inside)):
            if inside[i] != inside[i - 1]:
                place(fx, whoosh(1.0, up=True), max(0.0, i / fps - 0.45), 0.8)

    # Fire: inhale before the blast, then the roar following the card size.
    fire = np.array([f["fire"] for f in fr])
    if fire.max() > 0.05:
        start = np.nonzero(fire > 0.05)[0][0] / fps
        place(fx, inhale(1.0), start - 1.0, 0.7)
        fx += 0.9 * fire_roar(np.clip(per_sample(fire), 0, 1.2))
        wind *= 1 - 0.5 * np.clip(per_sample(fire), 0, 1)  # let the roar through

    mix = wind + flaps + fx
    fade = np.minimum(1, np.minimum(t / 0.4, (dur - t) / 0.6))
    mix *= np.clip(fade, 0, 1)
    mix = np.tanh(1.4 * mix / (np.abs(mix).max() + 1e-9)) * 0.89  # soft limit, ~-1 dBFS peak
    # Light stereo: flaps a touch wider than the bed.
    left = mix + 0.03 * np.roll(flaps, 120)
    right = mix - 0.03 * np.roll(flaps, 120)
    st = np.stack([left, right], 1)
    st /= max(1.0, np.abs(st).max() / 0.89)
    wavfile.write(out_path, SR, (st * 32767).astype(np.int16))
    print("sfx", out_path, f"{dur:.1f}s", "flaps", int((np.abs(np.diff((flaps != 0).astype(int))) > 0).sum() / 2))


if __name__ == "__main__":
    main()
