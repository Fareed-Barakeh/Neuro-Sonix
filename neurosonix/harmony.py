"""Harmony generation: a Markov-chain chord progression, biased by the melody.

This is deliberately not a trained neural network -- there's no model file,
no corpus of MIDI to train on in this repo, and claiming otherwise would be
dishonest. What it is: a hand-authored transition matrix over the seven
diatonic triads of a key, encoding ordinary functional-harmony tendencies
(V resolves to I, ii favors V, IV can go almost anywhere...), sampled at
each harmonic step and *reweighted by how well each candidate chord fits
the melody note sounding at that moment*. The text still drives the
harmony; the Markov chain just keeps the choices idiomatic.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

PITCH_CLASS_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

MAJOR_SCALE_STEPS = [0, 2, 4, 5, 7, 9, 11]
MINOR_SCALE_STEPS = [0, 2, 3, 5, 7, 8, 10]

ROMAN_MAJOR = ['I', 'ii', 'iii', 'IV', 'V', 'vi', 'vii°']
ROMAN_MINOR = ['i', 'ii°', 'III', 'iv', 'v', 'VI', 'VII']

# Row i = current scale-degree chord (0-indexed I..vii), values = relative
# likelihood of moving to each of the 7 diatonic chords next. Encodes
# textbook tendencies: V->I strong, ii->V strong, IV free-roaming,
# vii°->I (leading tone resolution), tonic can go almost anywhere.
TRANSITION_WEIGHTS = [
    [0.10, 0.16, 0.08, 0.22, 0.20, 0.18, 0.06],  # I    ->
    [0.06, 0.06, 0.04, 0.10, 0.55, 0.10, 0.09],  # ii   ->
    [0.14, 0.10, 0.06, 0.28, 0.10, 0.26, 0.06],  # iii  ->
    [0.24, 0.12, 0.06, 0.08, 0.34, 0.10, 0.06],  # IV   ->
    [0.50, 0.04, 0.06, 0.06, 0.08, 0.20, 0.06],  # V    ->
    [0.10, 0.28, 0.04, 0.28, 0.16, 0.06, 0.08],  # vi   ->
    [0.55, 0.05, 0.05, 0.05, 0.15, 0.10, 0.05],  # vii° ->
]


@dataclass
class Key:
    tonic_pc: int  # 0-11, pitch class
    mode: str      # 'major' or 'minor'

    @property
    def steps(self) -> list[int]:
        return MAJOR_SCALE_STEPS if self.mode == 'major' else MINOR_SCALE_STEPS

    @property
    def roman_numerals(self) -> list[str]:
        return ROMAN_MAJOR if self.mode == 'major' else ROMAN_MINOR

    def scale_pitch_classes(self) -> list[int]:
        return [(self.tonic_pc + s) % 12 for s in self.steps]

    def diatonic_triad(self, degree: int) -> tuple[int, int, int]:
        """Root/third/fifth pitch classes for the triad built on `degree` (0-6)."""
        scale = self.scale_pitch_classes()
        root = scale[degree % 7]
        third = scale[(degree + 2) % 7]
        fifth = scale[(degree + 4) % 7]
        return (root, third, fifth)

    def name(self) -> str:
        return f"{PITCH_CLASS_NAMES[self.tonic_pc]} {self.mode}"


def _consonance(chord_tones: tuple[int, int, int], melody_pc: int) -> float:
    """1.0 if the melody note is a chord tone, tapering off for near misses."""
    if melody_pc in chord_tones:
        return 1.0
    dists = [min((melody_pc - t) % 12, (t - melody_pc) % 12) for t in chord_tones]
    return max(0.15, 1.0 - min(dists) / 6)


def generate_progression(key: Key, melody_pitch_classes: list[int], seed: int | None = None) -> list[int]:
    """One chord-degree (0-6) per entry in melody_pitch_classes, Markov-sampled
    and reweighted toward chords that contain (or sit close to) that step's
    melody note."""
    rng = random.Random(seed)
    progression: list[int] = []
    current = 0  # start on the tonic
    for melody_pc in melody_pitch_classes:
        weights = list(TRANSITION_WEIGHTS[current])
        for degree in range(7):
            tones = key.diatonic_triad(degree)
            weights[degree] *= _consonance(tones, melody_pc)
        total = sum(weights) or 1.0
        weights = [w / total for w in weights]
        current = rng.choices(range(7), weights=weights, k=1)[0]
        progression.append(current)
    return progression


def chord_midi_notes(key: Key, degree: int, octave: int = 3) -> tuple[int, int, int]:
    """Root/third/fifth as absolute MIDI notes in the given octave."""
    root_pc, third_pc, fifth_pc = key.diatonic_triad(degree)
    base = 12 * (octave + 1)  # MIDI note 0 = C-1, so C(octave) = 12*(octave+1)

    def place(pc: int, near: int) -> int:
        n = base + pc
        while n < near - 6:
            n += 12
        while n > near + 6:
            n -= 12
        return n

    root = place(root_pc, base + 0)
    third = place(third_pc, root)
    fifth = place(fifth_pc, root)
    return (root, third, fifth)
