"""Score -> a rendered .wav, with no DAW, plugin, or soundfont required.

What separates this from "a MIDI file converted to sine waves":

  - LEGATO / PORTAMENTO: when melody, countermelody, or bass notes land
    back-to-back with almost no gap, the second note glides up from the
    first note's pitch instead of re-attacking from silence -- a phrase
    played on one breath (or one walking bass line), not a string of
    separate blips.
  - BREATH onset noise on a fresh (non-legato) melody/countermelody
    attack -- the small hiss of an embouchure starting a note.
  - VIBRATO, fading in ~150ms after the attack rather than present from
    note one, with its own rate and phase wobbling slightly per note
    (real vibrato isn't a perfect oscillator).
  - BRIGHTNESS follows velocity: a loud note's upper harmonics come
    through more; a quiet one is rounder. Real instruments do this;
    a fixed harmonic mix at every dynamic doesn't.
  - TREMOLO: a slow, small amplitude drift on sustained voices (pad,
    bass) so a long note breathes instead of sitting dead flat.
  - UNISON DETUNE (a few voices a handful of cents apart) on the
    harmony pad and arpeggio -- the classic synth-pad chorus trick.
  - DRIVE (soft saturation) on the bass for warmth.
  - HUMANIZATION: every note's start time and velocity get a small
    random nudge at render time only (the MIDI file stays exactly
    quantized), seeded per note for reproducibility.
  - REVERB: an 8-comb/4-allpass algorithmic reverb (Freeverb design)
    gluing the six voices into one shared space.
  - MASTER BUS glue: a soft-knee compressor ahead of the final
    peak-safe normalize.
"""
from __future__ import annotations

import wave

import numpy as np
from scipy.signal import lfilter

from .compose import Score

SAMPLE_RATE = 44100

TIMBRES = {
    'melody':        dict(harmonics=[1.0, 0.55, 0.30, 0.18, 0.08], attack=0.008, decay=0.06,
                            sustain=0.75, release=0.09, vibrato_rate=5.4, vibrato_depth=0.0035,
                            vibrato_onset=0.14, unison_cents=[0], drive=0, breath=0.05,
                            tremolo_depth=0.015, tremolo_rate=4.6),
    'harmony':       dict(harmonics=[1.0, 0.28, 0.12, 0.05], attack=0.09, decay=0.25,
                            sustain=0.65, release=0.55, vibrato_rate=0, vibrato_depth=0,
                            vibrato_onset=0, unison_cents=[-7, 0, 7], drive=0, breath=0,
                            tremolo_depth=0.035, tremolo_rate=3.1),
    'bass':          dict(harmonics=[1.0, 0.18, 0.05], attack=0.005, decay=0.08,
                            sustain=0.85, release=0.12, vibrato_rate=0, vibrato_depth=0,
                            vibrato_onset=0, unison_cents=[0], drive=1.8, breath=0,
                            tremolo_depth=0.02, tremolo_rate=4.0),
    'countermelody': dict(harmonics=[1.0, 0.20, 0.35, 0.05], attack=0.02, decay=0.10,
                            sustain=0.55, release=0.18, vibrato_rate=4.8, vibrato_depth=0.003,
                            vibrato_onset=0.16, unison_cents=[0], drive=0, breath=0.04,
                            tremolo_depth=0.015, tremolo_rate=4.2),
    'arpeggio':      dict(harmonics=[1.0, 0.65, 0.45, 0.30, 0.18], attack=0.002, decay=0.35,
                            sustain=0.0, release=0.05, vibrato_rate=0, vibrato_depth=0,
                            vibrato_onset=0, unison_cents=[-4, 4], drive=0, breath=0,
                            tremolo_depth=0, tremolo_rate=0),
}

# voices that can slur into the next note instead of re-attacking, when the
# gap to the next note in that voice is small enough
LEGATO_VOICES = {'melody', 'countermelody', 'bass'}
LEGATO_GAP_S = 0.045

GM_KICK, GM_HIHAT, GM_CRASH = 36, 42, 49


def _midi_to_freq(note: int) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def _adsr(n_samples: int, sr: int, attack: float, decay: float, sustain: float, release: float) -> np.ndarray:
    a = max(1, int(attack * sr))
    d = max(1, int(decay * sr))
    r = max(1, int(release * sr))
    sustain_len = max(0, n_samples - a - d)
    env = np.concatenate([
        np.linspace(0, 1, a, endpoint=False),
        np.linspace(1, sustain, d, endpoint=False),
        np.full(sustain_len, sustain),
    ])
    tail = np.linspace(sustain, 0, r)
    return np.concatenate([env, tail])


def _render_note(midi_note: int, velocity: int, duration_s: float, voice: str,
                   rng: np.random.Generator, glide_from_freq: float | None = None) -> np.ndarray:
    cfg = TIMBRES.get(voice, TIMBRES['melody'])
    freq = _midi_to_freq(midi_note)
    n = max(1, int(duration_s * SAMPLE_RATE))

    attack = min(cfg['attack'], 0.004) if glide_from_freq is not None else cfg['attack']
    env = _adsr(n, SAMPLE_RATE, attack, cfg['decay'], cfg['sustain'], cfg['release'])
    t = np.arange(len(env)) / SAMPLE_RATE

    # portamento: glide up/down from the previous note's pitch instead of
    # jumping straight to this note's, when the two are close to legato
    if glide_from_freq is not None:
        glide_s = min(0.045, duration_s * 0.35)
        n_glide = min(max(1, int(glide_s * SAMPLE_RATE)), len(t))
        freq_curve = np.full(len(t), freq)
        freq_curve[:n_glide] = np.linspace(glide_from_freq, freq, n_glide)
    else:
        freq_curve = np.full(len(t), freq)

    # vibrato: rate and phase wobble a little per note -- a real vibrato
    # isn't a perfectly periodic oscillator
    if cfg['vibrato_depth'] > 0:
        vib_rate = cfg['vibrato_rate'] * (1 + rng.normal(0, 0.05))
        vib_phase = rng.uniform(0, 2 * np.pi)
        vibrato_env = np.clip((t - cfg['vibrato_onset']) / 0.15, 0, 1)
        vibrato = cfg['vibrato_depth'] * vibrato_env * np.sin(2 * np.pi * vib_rate * t + vib_phase)
    else:
        vibrato = 0.0

    # brightness follows loudness: a loud note's upper harmonics carry more
    # relative energy, a quiet one is rounder/darker -- fixed spectral tilt
    # at every dynamic is one of the more obvious "sequenced" tells
    brightness = 0.62 + 0.58 * (velocity / 127)
    harmonics = cfg['harmonics']
    tilts = [brightness ** h for h in range(len(harmonics))]

    unison = cfg['unison_cents']
    wave_sum = np.zeros_like(t)
    for cents in unison:
        detune = 2 ** (cents / 1200)
        inst_freq = freq_curve * detune * (1 + vibrato)
        phase = 2 * np.pi * np.cumsum(inst_freq) / SAMPLE_RATE
        for h, (amp, tilt) in enumerate(zip(harmonics, tilts), start=1):
            wave_sum += amp * tilt * np.sin(phase * h)
    norm = sum(a * w for a, w in zip(harmonics, tilts)) * len(unison)
    wave_sum /= norm

    # tremolo: a slow, small amplitude drift so a sustained note breathes
    # instead of sitting at a dead-flat level
    if cfg.get('tremolo_depth', 0) > 0:
        trem_rate = cfg['tremolo_rate'] * (1 + rng.normal(0, 0.04))
        trem_phase = rng.uniform(0, 2 * np.pi)
        wave_sum *= 1 + cfg['tremolo_depth'] * np.sin(2 * np.pi * trem_rate * t + trem_phase)

    if cfg['drive'] > 0:
        d = cfg['drive']
        wave_sum = np.tanh(wave_sum * d) / np.tanh(d)

    out = wave_sum * env

    # breath: a short burst of airy noise under a fresh (non-legato) attack
    if cfg.get('breath', 0) > 0 and glide_from_freq is None:
        bn = min(len(out), int(0.025 * SAMPLE_RATE))
        breath_env = np.exp(-np.arange(bn) / SAMPLE_RATE * 80)
        breath_noise = np.diff(rng.standard_normal(bn), prepend=0)
        out[:bn] += breath_noise * breath_env * cfg['breath']

    gain = (velocity / 127) ** 1.2
    return out * gain


def _render_drum(note: int, velocity: int) -> np.ndarray:
    """Percussion is noise/pitch-envelope synthesis, not tonal harmonics --
    a kick, hi-hat, and crash need transient shape, not a sustained pitch."""
    rng = np.random.default_rng(note * 97 + velocity)
    gain = (velocity / 127) ** 1.1
    if note == GM_KICK:
        n = int(0.16 * SAMPLE_RATE)
        t = np.arange(n) / SAMPLE_RATE
        freq = 150 * np.exp(-t * 28) + 45
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        env = np.exp(-t * 18)
        return np.sin(phase) * env * gain
    if note == GM_HIHAT:
        n = int(0.05 * SAMPLE_RATE)
        noise = rng.standard_normal(n)
        noise = np.diff(noise, prepend=0)  # crude high-pass: emphasize the hiss
        env = np.exp(-np.arange(n) / SAMPLE_RATE * 90)
        return noise * env * gain * 0.5
    if note == GM_CRASH:
        n = int(1.1 * SAMPLE_RATE)
        noise = rng.standard_normal(n)
        noise = np.diff(noise, prepend=0)
        env = np.exp(-np.arange(n) / SAMPLE_RATE * 3.2)
        return noise * env * gain * 0.35
    return np.zeros(1)


# --------------------------------------------------------------------- #
# reverb: Freeverb-style -- 8 parallel damped comb filters summed, then
# 4 series allpass filters for diffusion. Each filter is a true IIR
# recursion (a feedback tap `delay` samples back), implemented with
# scipy.signal.lfilter so the whole tail renders in one call instead of
# a Python loop over every sample.
_COMB_DELAYS = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
_ALLPASS_DELAYS = [556, 441, 341, 225]


def _comb(x: np.ndarray, delay: int, feedback: float, damping: float) -> np.ndarray:
    a = np.zeros(delay + 1)
    a[0] = 1.0
    a[delay] = -feedback
    y = lfilter([1.0], a, x)
    if damping > 0:
        y = lfilter([1 - damping], [1, -damping], y)  # one-pole darkening of the tail
    return y


def _allpass(x: np.ndarray, delay: int, g: float = 0.5) -> np.ndarray:
    b = np.zeros(delay + 1)
    b[0] = -g
    b[delay] = 1.0
    a = np.zeros(delay + 1)
    a[0] = 1.0
    a[delay] = -g
    return lfilter(b, a, x)


def _dc_block(x: np.ndarray) -> np.ndarray:
    """A comb filter's DC gain is 1/(1-feedback) -- at feedback=0.83 that's
    ~5.9x, so even the slight DC bias an additive synth mix picks up from
    finite-sample rounding gets amplified into an audible offset after the
    reverb. Standard one-pole DC blocker (y[n] = x[n] - x[n-1] + 0.995*y[n-1])
    removes it without touching anything above a few Hz."""
    return lfilter([1.0, -1.0], [1.0, -0.995], x)


def _reverb(mono: np.ndarray, room_size: float = 0.83, damping: float = 0.3) -> np.ndarray:
    out = np.zeros_like(mono)
    for d in _COMB_DELAYS:
        out += _comb(mono, d, room_size, damping)
    out /= len(_COMB_DELAYS)
    for d in _ALLPASS_DELAYS:
        out = _allpass(out, d)
    return _dc_block(out)


def _soft_compress(x: np.ndarray, threshold: float = 0.55, ratio: float = 3.0) -> np.ndarray:
    """Gentle peak glue: leaves anything under `threshold` untouched,
    compresses what's above it by `ratio` -- so the loudest moments don't
    dictate the volume of everything else the way plain peak-normalizing does."""
    mag = np.abs(x)
    over = np.maximum(mag - threshold, 0)
    target_mag = np.minimum(mag, threshold) + over / ratio
    scale = np.divide(target_mag, mag, out=np.ones_like(x), where=mag > 1e-9)
    return x * scale


def render(score: Score, pan_spread: bool = True, humanize: bool = True,
            reverb_wet: float = 0.16) -> np.ndarray:
    """Returns a (n_samples, 2) float array in [-1, 1]."""
    total_s = score.length_seconds + 1.2  # tail room for the last note's release
    n_total = int(total_s * SAMPLE_RATE) + 1
    left = np.zeros(n_total)
    right = np.zeros(n_total)

    voice_pan = {'melody': 0.0, 'bass': 0.0, 'countermelody': 0.22, 'arpeggio': 0.0, 'harmony': 0.0}

    for voice, events in score.tracks.items():
        chord_pan_cycle = [-0.35, 0.0, 0.35] if voice in ('harmony', 'arpeggio') else [voice_pan.get(voice, 0.0)]
        can_legato = voice in LEGATO_VOICES
        prev_end_s = None
        prev_freq = None
        for i, ev in enumerate(events):
            rng = np.random.default_rng(hash((voice, i, ev.start_beat, ev.midi_note)) & 0xFFFFFFFF)
            start_s = ev.start_beat * 60.0 / score.tempo_bpm
            dur_s = ev.duration_beat * 60.0 / score.tempo_bpm
            velocity = ev.velocity
            if humanize:
                start_s += rng.normal(0, 0.006)  # a few ms of timing looseness
                velocity = int(np.clip(velocity * rng.uniform(0.95, 1.03), 1, 127))

            if voice == 'percussion':
                samples = _render_drum(ev.midi_note, velocity)
            else:
                glide_from = None
                if can_legato and prev_end_s is not None and 0 <= start_s - prev_end_s < LEGATO_GAP_S:
                    glide_from = prev_freq
                samples = _render_note(ev.midi_note, velocity, dur_s, voice, rng, glide_from_freq=glide_from)
                prev_end_s = start_s + dur_s
                prev_freq = _midi_to_freq(ev.midi_note)

            start_idx = max(0, int(start_s * SAMPLE_RATE))
            end_idx = start_idx + len(samples)
            if end_idx > n_total:
                samples = samples[: n_total - start_idx]
                end_idx = n_total
            p = chord_pan_cycle[i % len(chord_pan_cycle)] if pan_spread else 0.0
            left[start_idx:end_idx] += samples * (1 - max(0, p))
            right[start_idx:end_idx] += samples * (1 + min(0, p))

    if reverb_wet > 0:
        wet = _reverb((left + right) * 0.5)
        offset = 11  # samples -- a hair of L/R stagger on the wet signal for width
        left = left + reverb_wet * wet
        right = right + reverb_wet * np.concatenate([np.zeros(offset), wet[:-offset]])

    # short, asymmetrically-windowed sine bursts (a note only a few cycles
    # long, especially low bass notes) don't average to exactly zero on
    # their own; summing dozens of them leaves a small residual DC bias.
    # One more DC-blocker on the full master bus catches that, on top of
    # the one already inside _reverb() for the comb filters' own DC gain.
    left = _dc_block(left)
    right = _dc_block(right)

    stereo = np.stack([left, right], axis=1)
    stereo = _soft_compress(stereo)
    peak = np.max(np.abs(stereo))
    if peak > 0:
        stereo = stereo / peak * 0.92
    return stereo


def save(score: Score, path: str) -> None:
    audio = render(score)
    pcm = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    with wave.open(path, 'wb') as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        f.writeframes(pcm.tobytes())
