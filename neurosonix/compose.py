"""Orchestrates encoding -> rhythm -> dynamics -> harmony into one Score.

A Score is the single intermediate representation that render_midi.py,
synth.py, and visualize.py all read from -- one source of truth, so the
MIDI file, the rendered audio, and the piano-roll picture can never drift
out of sync with each other.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import dynamics, encoding, harmony, rhythm


@dataclass
class NoteEvent:
    start_beat: float
    duration_beat: float
    midi_note: int
    velocity: int
    char: str = ''  # which source letter this note came from, for the visual/debug view


@dataclass
class ChordEvent:
    start_beat: float
    duration_beat: float
    degree: int          # 0-6, scale degree within `key`
    key: harmony.Key      # that chord's own key -- differs across chords when modulating
    seventh: bool = False  # a 7th chord (see harmony.chord_tones) rather than a plain triad


@dataclass
class Score:
    text: str
    tempo_bpm: float
    key: harmony.Key  # the piece's base/primary key, for display when not modulating
    tracks: dict[str, list[NoteEvent]] = field(default_factory=dict)
    chord_progression: list[ChordEvent] = field(default_factory=list)

    @property
    def length_beats(self) -> float:
        return max((e.start_beat + e.duration_beat for evs in self.tracks.values() for e in evs), default=0.0)

    @property
    def length_seconds(self) -> float:
        return self.length_beats * 60.0 / self.tempo_bpm


# probability a chord gets a 7th added, by scale degree -- dominant (V) and
# vii° favor it most (a dominant/leading-tone seventh's pull toward the
# tonic is stronger than the bare triad's), ii next (the jazz ii7-V7-I
# color), everything else more sparingly
SEVENTH_PROBABILITY = {0: 0.08, 1: 0.30, 2: 0.12, 3: 0.15, 4: 0.60, 5: 0.15, 6: 0.30}

# walking bass: a chord held this many beats or longer gets its last chunk
# handed to a passing tone approaching the *next* chord's root, instead of
# sustaining the same note the whole way -- what a bassist playing live
# actually does between chords
WALKING_BASS_MIN_BEATS = 1.3
WALKING_BASS_MAIN_FRACTION = 0.72


def compose(text: str, tempo_bpm: float = 96.0, key: harmony.Key | None = None,
             harmony_octave: int = 4, bass_octave: int = 1, seed: int | None = None,
             tonal: bool = False, modulate: list[harmony.Key] | None = None) -> Score:
    """
    harmony_octave/bass_octave: the pad's home octave sits a full octave
    above the bass's by default (4 vs 1) on purpose -- the melody's own
    chromatic range (A=C2..Z=C#4) is already low, and stacking the pad's
    fundamentals right next to the bass's crowds the same narrow low-end
    band both voices would otherwise fight over.

    tonal: the melody is chromatic by default -- letters run across all 12
    semitones while the harmony sits on 7, and that friction is the
    original piece's character, not a flaw. Set tonal=True to instead snap
    every melody note onto its phrase's scale (see harmony.snap_to_scale):
    same rhythm and contour, fully consonant with the chords underneath.

    modulate: a list of Keys to cycle through, one per sentence, instead of
    staying in a single key for the whole piece -- modal interchange when
    they share a tonic (e.g. D dorian -> D mixolydian -> D aeolian), a full
    key change when they don't. Affects both the harmony (each sentence's
    chords are drawn from its own key) and, if tonal=True, the melody.
    Leave as None to stay in the single `key` throughout (the default).
    """
    if not text.strip():
        raise ValueError("text is empty")
    key = key or harmony.Key(tonic_pc=0, mode='major')  # C major default

    def phrase_key(phrase_index: int) -> harmony.Key:
        if not modulate:
            return key
        return modulate[phrase_index % len(modulate)]

    phrases = encoding.tokenize(text)
    melody: list[NoteEvent] = []
    cursor = 0.0
    # [start, dur, melody_pc, key, cadence] per word -- cadence is None
    # except on the last word of a sentence, where it's that sentence's
    # terminator ('.', '!', '?', or '' if the text just ends)
    harmony_slots: list[list] = []

    for phrase_index, phrase in enumerate(phrases):
        pk = phrase_key(phrase_index)
        word_start_beat = cursor
        word_pitch_classes: list[int] = []
        prev_word_start = None
        for tok in phrase.tokens:
            if tok.is_word_start and prev_word_start is not None:
                dur = cursor - word_start_beat
                if dur > 0:
                    harmony_slots.append([word_start_beat, dur, _majority_pc(word_pitch_classes), pk, None])
                word_start_beat = cursor
                word_pitch_classes = []
            prev_word_start = True

            dur_beats = rhythm.letter_duration_beats(tok.char)
            vel = dynamics.token_velocity(tok.position_in_sentence, tok.is_word_start, tok.is_upper)
            note = harmony.snap_to_scale(tok.midi_note, pk) if tonal else tok.midi_note
            melody.append(NoteEvent(cursor, dur_beats * 0.92, note, vel, tok.char))
            word_pitch_classes.append(note % 12)
            cursor += dur_beats

        if word_pitch_classes:
            dur = cursor - word_start_beat
            harmony_slots.append([word_start_beat, dur, _majority_pc(word_pitch_classes), pk, None])

        if harmony_slots:
            harmony_slots[-1][4] = phrase.terminator or ''

        if phrase.terminator:
            vel = dynamics.terminator_velocity(phrase.terminator)
            cursor += rhythm.phrase_gap_beats(phrase.terminator)
        else:
            cursor += rhythm.word_gap_beats()

    # --- harmony: one Markov-sampled chord per word, biased by that word's
    # melody, drawn from that word's own (possibly modulated) key, and
    # pulled toward a real cadence at the end of each sentence (see
    # harmony.CADENCE_TARGET). Each chord voice-leads from the previous one
    # (chord_midi_notes(prev=...)) instead of resetting to a fixed octave
    # every time, so the pad and bass glide by a few semitones per chord
    # rather than jumping registers -- that still works smoothly across a
    # key change, since voice leading only cares about the previous
    # absolute pitch, not what key it was in.
    degrees = harmony.generate_progression(
        [(pc, k) for _, _, pc, k, _ in harmony_slots], seed=seed,
        cadences=[c for _, _, _, _, c in harmony_slots],
    )
    seventh_rng = random.Random(seed)

    harmony_track: list[NoteEvent] = []
    bass_track: list[NoteEvent] = []
    chord_progression: list[ChordEvent] = []
    prev_chord_notes = None
    prev_bass = None
    bass_anchor = 12 * (bass_octave + 1)

    for i, ((start, dur, _pc, slot_key, cadence), degree) in enumerate(zip(harmony_slots, degrees)):
        # a cadential arrival stays a plain triad -- the "we've landed"
        # chord reads more resolved without a seventh coloring it
        seventh = cadence is None and seventh_rng.random() < SEVENTH_PROBABILITY[degree]

        chord_notes = harmony.chord_midi_notes(slot_key, degree, octave=harmony_octave,
                                                 prev=prev_chord_notes, seventh=seventh)
        bass_root_pc = slot_key.chord_tones(degree)[0]
        if prev_bass is None:
            bass_note = harmony.nearest_pitch(bass_root_pc, bass_anchor)
        else:
            bass_note = harmony.bounded_nearest_pitch(bass_root_pc, prev_bass, bass_anchor)

        pad_dur = max(dur * 0.94, 0.1)
        for note in chord_notes:
            harmony_track.append(NoteEvent(start, pad_dur, note, 46))

        # walking bass: hand the tail of a long-enough chord to a passing
        # tone approaching the *next* chord's root by a half step, instead
        # of sustaining one note the whole way
        has_next = i + 1 < len(harmony_slots)
        if has_next and dur >= WALKING_BASS_MIN_BEATS:
            next_degree = degrees[i + 1]
            next_key = harmony_slots[i + 1][3]
            next_root_pc = next_key.chord_tones(next_degree)[0]
            passing_pc = (next_root_pc - 1) % 12
            main_dur = dur * WALKING_BASS_MAIN_FRACTION
            passing_dur = max(dur - main_dur, 0.05)
            bass_track.append(NoteEvent(start, main_dur * 0.96, bass_note, 58))
            passing_note = harmony.nearest_pitch(passing_pc, bass_note)
            bass_track.append(NoteEvent(start + main_dur, passing_dur * 0.9, passing_note, 42))
            prev_bass = passing_note
        else:
            bass_track.append(NoteEvent(start, pad_dur, bass_note, 58))
            prev_bass = bass_note

        prev_chord_notes = chord_notes
        chord_progression.append(ChordEvent(start, dur, degree, slot_key, seventh))

    score = Score(text=text, tempo_bpm=tempo_bpm, key=key)
    score.tracks['melody'] = melody
    score.tracks['harmony'] = harmony_track
    score.tracks['bass'] = bass_track
    score.chord_progression = chord_progression
    return score


def _majority_pc(pitch_classes: list[int]) -> int:
    if not pitch_classes:
        return 0
    return max(set(pitch_classes), key=pitch_classes.count)
