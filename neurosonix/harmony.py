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

# the seven diatonic modes -- all seven rotations of the same major-scale
# interval pattern, starting from a different degree each time. 'major' and
# 'minor' are the familiar names for ionian and aeolian.
MODE_STEPS = {
    'ionian':     [0, 2, 4, 5, 7, 9, 11],
    'dorian':     [0, 2, 3, 5, 7, 9, 10],
    'phrygian':   [0, 1, 3, 5, 7, 8, 10],
    'lydian':     [0, 2, 4, 6, 7, 9, 11],
    'mixolydian': [0, 2, 4, 5, 7, 9, 10],
    'aeolian':    [0, 2, 3, 5, 7, 8, 10],
    'locrian':    [0, 1, 3, 5, 6, 8, 10],
}
MODE_ALIASES = {'major': 'ionian', 'minor': 'aeolian'}
MODE_NAMES = list(MODE_STEPS)  # canonical order, for cycling through all seven
MODE_DISPLAY_NAMES = {'ionian': 'major', 'aeolian': 'minor'}  # for Key.name()

ROMAN_BASE = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII']

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
    mode: str      # any of MODE_STEPS, or the aliases 'major'/'minor'

    def __post_init__(self):
        self.mode = MODE_ALIASES.get(self.mode, self.mode)
        if self.mode not in MODE_STEPS:
            raise ValueError(f"unknown mode: {self.mode!r} (try one of {MODE_NAMES})")

    @property
    def steps(self) -> list[int]:
        return MODE_STEPS[self.mode]

    def scale_pitch_classes(self) -> list[int]:
        return [(self.tonic_pc + s) % 12 for s in self.steps]

    def diatonic_triad(self, degree: int) -> tuple[int, int, int]:
        """Root/third/fifth pitch classes for the triad built on `degree` (0-6)."""
        scale = self.scale_pitch_classes()
        root = scale[degree % 7]
        third = scale[(degree + 2) % 7]
        fifth = scale[(degree + 4) % 7]
        return (root, third, fifth)

    def chord_label(self, degree: int) -> str:
        """Roman numeral for the triad on `degree`, quality computed from its
        actual intervals rather than looked up from a major/minor table --
        so it's correct for any of the seven modes automatically. A major
        third above the root capitalizes the numeral, a diminished fifth
        adds '°', an augmented fifth adds '+'."""
        root, third, fifth = self.diatonic_triad(degree)
        third_interval = (third - root) % 12
        fifth_interval = (fifth - root) % 12
        numeral = ROMAN_BASE[degree % 7]
        label = numeral if third_interval == 4 else numeral.lower()
        if fifth_interval == 6:
            label += '°'
        elif fifth_interval == 8:
            label += '+'
        return label

    def name(self) -> str:
        # 'ionian'/'aeolian' are technically correct but 'major'/'minor' is
        # what everyone actually reads for the two everyday modes
        display_mode = MODE_DISPLAY_NAMES.get(self.mode, self.mode)
        return f"{PITCH_CLASS_NAMES[self.tonic_pc]} {display_mode}"


def snap_to_scale(midi_note: int, key: Key) -> int:
    """Move a chromatic note to the nearest pitch class in the key's scale.

    The default melody is fully chromatic on purpose -- letters run across
    all 12 semitones, the harmony sits on 7 -- and that friction is part of
    the original piece's character, not a bug to fix. This is the opt-in
    alternative for text that should read as more consonant: every letter
    still keeps its relative contour (rarer/higher letters still sit higher
    within an octave), it's just pulled onto the same 7 notes as the chords
    under it.
    """
    scale = key.scale_pitch_classes()
    pc = midi_note % 12
    nearest_pc = min(scale, key=lambda s: min((pc - s) % 12, (s - pc) % 12))
    candidates = [midi_note + d for d in range(-6, 7) if (midi_note + d) % 12 == nearest_pc]
    return min(candidates, key=lambda n: abs(n - midi_note))


def _consonance(chord_tones: tuple[int, int, int], melody_pc: int) -> float:
    """1.0 if the melody note is a chord tone, tapering off for near misses."""
    if melody_pc in chord_tones:
        return 1.0
    dists = [min((melody_pc - t) % 12, (t - melody_pc) % 12) for t in chord_tones]
    return max(0.15, 1.0 - min(dists) / 6)


def generate_progression(steps: list[tuple[int, Key]], seed: int | None = None) -> list[int]:
    """One chord-degree (0-6) per (melody_pitch_class, key) entry in `steps`,
    Markov-sampled and reweighted toward chords that contain (or sit close
    to) that step's melody note in *that step's own key*.

    Each step's key can differ from the last -- that's what lets a piece
    modulate between scales mid-progression (see compose(modulate=...)).
    The Markov state (`current`, a scale-degree index 0-6) carries straight
    across a key change: finishing on "V" of the old key and landing on
    "V" of the new one reads as a pivot-chord-like modulation rather than
    a hard cut, since scale-degree function is preserved even though the
    actual pitches underneath it just shifted.
    """
    rng = random.Random(seed)
    progression: list[int] = []
    current = 0  # start on the tonic
    for melody_pc, key in steps:
        weights = list(TRANSITION_WEIGHTS[current])
        for degree in range(7):
            tones = key.diatonic_triad(degree)
            weights[degree] *= _consonance(tones, melody_pc)
        total = sum(weights) or 1.0
        weights = [w / total for w in weights]
        current = rng.choices(range(7), weights=weights, k=1)[0]
        progression.append(current)
    return progression


def nearest_pitch(pitch_class: int, near: int) -> int:
    """The MIDI note with the given pitch class closest to `near` -- the
    building block of voice leading: move each voice the shortest distance
    to its next note, instead of resetting every chord to a fixed octave."""
    n = near - ((near - pitch_class) % 12)
    if n - near > 6:
        n -= 12
    elif near - n > 6:
        n += 12
    return n


def bounded_nearest_pitch(pitch_class: int, near: int, anchor: int, max_drift: int = 9) -> int:
    """nearest_pitch(), but pulled back by octaves if it would stray more
    than `max_drift` semitones from `anchor`.

    Chaining nearest_pitch() chord after chord gives smooth *local* motion,
    but with nothing pulling a voice back toward its home register, a long
    piece can drift a voice steadily downward (or upward) over dozens of
    chords with no bound -- audibly, a bass line sinking into the
    sub-basement by the end of a piece. Anchoring each step to that voice's
    fixed home-octave position keeps the smooth step-to-step motion while
    capping how far it's allowed to wander from home.
    """
    n = nearest_pitch(pitch_class, near)
    while n - anchor > max_drift:
        n -= 12
    while anchor - n > max_drift:
        n += 12
    return n


def chord_midi_notes(key: Key, degree: int, octave: int = 3,
                       prev: tuple[int, int, int] | None = None) -> tuple[int, int, int]:
    """Root/third/fifth as absolute MIDI notes.

    Without `prev`, the triad is built fresh in the given octave -- that
    placement also serves as each voice's "home" anchor. With `prev` (the
    previous chord's root/third/fifth), each voice instead moves to the
    nearest instance of its new pitch class -- real voice leading, so
    consecutive chords glide by a few semitones per voice -- but bounded
    back toward its home anchor so a long piece can't drift a voice
    steadily out of register (see bounded_nearest_pitch).
    """
    root_pc, third_pc, fifth_pc = key.diatonic_triad(degree)
    base = 12 * (octave + 1)  # MIDI note 0 = C-1, so C(octave) = 12*(octave+1)
    anchor_root = nearest_pitch(root_pc, base)
    anchor_third = nearest_pitch(third_pc, anchor_root)
    anchor_fifth = nearest_pitch(fifth_pc, anchor_root)

    if prev is None:
        return (anchor_root, anchor_third, anchor_fifth)

    prev_root, prev_third, prev_fifth = prev
    root = bounded_nearest_pitch(root_pc, prev_root, anchor_root)
    third = bounded_nearest_pitch(third_pc, prev_third, anchor_third)
    fifth = bounded_nearest_pitch(fifth_pc, prev_fifth, anchor_fifth)
    return (root, third, fifth)
