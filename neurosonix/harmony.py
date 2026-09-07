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

    def chord_tones(self, degree: int, seventh: bool = False) -> tuple[int, ...]:
        """Root/third/fifth[/seventh] pitch classes for the chord on `degree`.
        Stacking one more third on top of the triad (the scale's 7th degree
        from the root) is what turns a plain triad into real functional
        harmony color -- a dominant seventh's pull toward the tonic is
        stronger than a bare V, which is most of what "sophisticated"
        harmony actually means in practice."""
        scale = self.scale_pitch_classes()
        offsets = (0, 2, 4, 6) if seventh else (0, 2, 4)
        return tuple(scale[(degree + o) % 7] for o in offsets)

    def chord_label(self, degree: int, seventh: bool = False) -> str:
        """Roman numeral for the chord on `degree`, quality computed from its
        actual intervals rather than looked up from a major/minor table --
        so it's correct for any of the seven modes automatically. A major
        third above the root capitalizes the numeral, a diminished fifth
        adds '°', an augmented fifth adds '+'; a seventh chord appends
        '7' (or 'maj7' for a major seventh above the root)."""
        tones = self.chord_tones(degree, seventh=seventh)
        root, third, fifth = tones[:3]
        third_interval = (third - root) % 12
        fifth_interval = (fifth - root) % 12
        numeral = ROMAN_BASE[degree % 7]
        label = numeral if third_interval == 4 else numeral.lower()
        if fifth_interval == 6:
            label += '°'
        elif fifth_interval == 8:
            label += '+'
        if seventh:
            seventh_interval = (tones[3] - root) % 12
            label += 'maj7' if seventh_interval == 11 else '7'
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


# how hard a phrase-ending chord gets pulled toward a cadence, keyed by the
# sentence's own terminator -- a full stop or exclamation resolves home
# (authentic cadence, V/vii°->I), a question mark deliberately doesn't
# (half cadence, landing on V instead: the harmony leaves the question
# hanging in the air the way the punctuation does)
CADENCE_TARGET = {'.': 0, '!': 0, '?': 4, '': 0}
CADENCE_BOOST = 14.0  # strong enough that a sentence reliably resolves;
                       # not absolute, so an occasional deceptive cadence
                       # can still happen, the way a real progression allows


def generate_progression(steps: list[tuple[int, Key]], seed: int | None = None,
                           cadences: list[str | None] | None = None) -> list[int]:
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

    `cadences[i]` is the phrase terminator ('.', '!', '?') if step i is the
    last chord of its sentence, else None -- see CADENCE_TARGET. Without
    this, a piece just wanders forever; with it, every sentence actually
    *lands* somewhere, which is most of what makes a chord progression
    read as composed instead of generated.
    """
    rng = random.Random(seed)
    progression: list[int] = []
    current = 0  # start on the tonic
    cadences = cadences or [None] * len(steps)
    for (melody_pc, key), cadence in zip(steps, cadences):
        weights = list(TRANSITION_WEIGHTS[current])
        for degree in range(7):
            tones = key.diatonic_triad(degree)
            weights[degree] *= _consonance(tones, melody_pc)
        if cadence is not None:
            # multiplying the target's own weight isn't reliable -- if that
            # degree's melody-consonance happened to floor out small, even
            # x5 can still lose to another degree with high consonance.
            # Set it relative to whatever the current max is instead, so
            # the cadence reliably wins regardless of that step's melody note.
            weights[CADENCE_TARGET.get(cadence, 0)] = (max(weights) + 1e-6) * CADENCE_BOOST
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
                       prev: tuple[int, ...] | None = None, seventh: bool = False) -> tuple[int, ...]:
    """Root/third/fifth[/seventh] as absolute MIDI notes -- 3 or 4 voices
    depending on `seventh`.

    Without `prev`, the chord is built fresh in the given octave, each
    voice stacked near the one below it -- that placement also serves as
    each voice's "home" anchor. With `prev` (the previous chord's voices,
    which may have been a different size), each voice instead moves to the
    nearest instance of its new pitch class -- real voice leading, so
    consecutive chords glide by a few semitones per voice -- but bounded
    back toward its home anchor so a long piece can't drift a voice
    steadily out of register (see bounded_nearest_pitch). A voice with no
    corresponding voice in `prev` (a 7th chord following a plain triad)
    just falls back to its home anchor.
    """
    pcs = key.chord_tones(degree, seventh=seventh)
    base = 12 * (octave + 1)  # MIDI note 0 = C-1, so C(octave) = 12*(octave+1)

    anchors = []
    near = base
    for pc in pcs:
        near = nearest_pitch(pc, near)
        anchors.append(near)

    if prev is None:
        return tuple(anchors)

    notes = []
    for i, pc in enumerate(pcs):
        prev_note = prev[i] if i < len(prev) else anchors[i]
        notes.append(bounded_nearest_pitch(pc, prev_note, anchors[i]))
    return tuple(notes)
