"""Score -> a rendered .wav, with no DAW, plugin, or soundfont required.

A small additive synthesizer: each note is a stack of sine harmonics under
an ADSR envelope, timbre varying by voice (melody reads bright and reedy,
harmony is a slow soft pad, bass is close to a pure sine). This is what
lets NeuroSonix produce something you can actually listen to straight out
of the pipeline -- the original version needed a DAW for that step.
"""
from __future__ import annotations

import wave

import numpy as np

from .compose import Score

SAMPLE_RATE = 44100

# (harmonic amplitudes, attack_s, decay_s, sustain_level, release_s)
TIMBRES = {
    'melody':        ([1.0, 0.55, 0.30, 0.18, 0.08], 0.008, 0.06, 0.75, 0.09),
    'harmony':       ([1.0, 0.28, 0.12, 0.05],       0.09,  0.25, 0.65, 0.55),
    'bass':          ([1.0, 0.18, 0.05],             0.005, 0.08, 0.85, 0.12),
    'countermelody': ([1.0, 0.20, 0.35, 0.05],       0.02,  0.10, 0.55, 0.18),  # reedy, sits under the lead
    'arpeggio':      ([1.0, 0.65, 0.45, 0.30, 0.18], 0.002, 0.35, 0.0,  0.05),  # bell-like: fast attack, no sustain
}

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


def _render_note(midi_note: int, velocity: int, duration_s: float, voice: str) -> np.ndarray:
    harmonics, attack, decay, sustain_level, release = TIMBRES.get(voice, TIMBRES['melody'])
    freq = _midi_to_freq(midi_note)
    n = max(1, int(duration_s * SAMPLE_RATE))
    env = _adsr(n, SAMPLE_RATE, attack, decay, sustain_level, release)
    t = np.arange(len(env)) / SAMPLE_RATE
    wave_sum = np.zeros_like(t)
    for h, amp in enumerate(harmonics, start=1):
        wave_sum += amp * np.sin(2 * np.pi * freq * h * t)
    wave_sum /= sum(harmonics)
    gain = (velocity / 127) ** 1.2
    return wave_sum * env * gain


_RNG = np.random.default_rng(0)


def _render_drum(note: int, velocity: int) -> np.ndarray:
    """Percussion is noise/pitch-envelope synthesis, not tonal harmonics --
    a kick, hi-hat, and crash need transient shape, not a sustained pitch."""
    gain = (velocity / 127) ** 1.1
    if note == GM_KICK:
        dur, n = 0.16, int(0.16 * SAMPLE_RATE)
        t = np.arange(n) / SAMPLE_RATE
        freq = 150 * np.exp(-t * 28) + 45
        phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
        env = np.exp(-t * 18)
        return np.sin(phase) * env * gain
    if note == GM_HIHAT:
        n = int(0.05 * SAMPLE_RATE)
        noise = _RNG.standard_normal(n)
        noise = np.diff(noise, prepend=0)  # crude high-pass: emphasize the hiss
        env = np.exp(-np.arange(n) / SAMPLE_RATE * 90)
        return noise * env * gain * 0.5
    if note == GM_CRASH:
        n = int(1.1 * SAMPLE_RATE)
        noise = _RNG.standard_normal(n)
        noise = np.diff(noise, prepend=0)
        env = np.exp(-np.arange(n) / SAMPLE_RATE * 3.2)
        return noise * env * gain * 0.35
    return np.zeros(1)


def render(score: Score, pan_spread: bool = True) -> np.ndarray:
    """Returns a (n_samples, 2) float array in [-1, 1]."""
    total_s = score.length_seconds + 1.2  # tail room for the last note's release
    n_total = int(total_s * SAMPLE_RATE) + 1
    left = np.zeros(n_total)
    right = np.zeros(n_total)

    for voice, events in score.tracks.items():
        pan = 0.0
        # give harmony's three chord tones a gentle spread instead of pure center
        chord_pan_cycle = [-0.35, 0.0, 0.35] if voice == 'harmony' else [0.0]
        for i, ev in enumerate(events):
            start_s = ev.start_beat * 60.0 / score.tempo_bpm
            dur_s = ev.duration_beat * 60.0 / score.tempo_bpm
            if voice == 'percussion':
                samples = _render_drum(ev.midi_note, ev.velocity)
            else:
                samples = _render_note(ev.midi_note, ev.velocity, dur_s, voice)
            start_idx = int(start_s * SAMPLE_RATE)
            end_idx = start_idx + len(samples)
            if end_idx > n_total:
                samples = samples[: n_total - start_idx]
                end_idx = n_total
            p = chord_pan_cycle[i % len(chord_pan_cycle)] if pan_spread else 0.0
            left[start_idx:end_idx] += samples * (1 - max(0, p))
            right[start_idx:end_idx] += samples * (1 + min(0, p))

    stereo = np.stack([left, right], axis=1)
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
