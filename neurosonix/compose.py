"""Orchestrates encoding -> rhythm -> dynamics -> harmony into one Score.

A Score is the single intermediate representation that render_midi.py,
synth.py, and visualize.py all read from -- one source of truth, so the
MIDI file, the rendered audio, and the piano-roll picture can never drift
out of sync with each other.
"""
from __future__ import annotations

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
class Score:
    text: str
    tempo_bpm: float
    key: harmony.Key
    tracks: dict[str, list[NoteEvent]] = field(default_factory=dict)
    chord_progression: list[tuple[float, float, int]] = field(default_factory=list)  # (start, dur, degree)

    @property
    def length_beats(self) -> float:
        return max((e.start_beat + e.duration_beat for evs in self.tracks.values() for e in evs), default=0.0)

    @property
    def length_seconds(self) -> float:
        return self.length_beats * 60.0 / self.tempo_bpm


def compose(text: str, tempo_bpm: float = 96.0, key: harmony.Key | None = None,
             harmony_octave: int = 3, bass_octave: int = 1, seed: int | None = None,
             tonal: bool = False) -> Score:
    """
    tonal: the melody is chromatic by default -- letters run across all 12
    semitones while the harmony sits on 7, and that friction is the
    original piece's character, not a flaw. Set tonal=True to instead snap
    every melody note onto the chosen key's scale (see
    harmony.snap_to_scale): same rhythm and contour, fully consonant with
    the chords underneath.
    """
    if not text.strip():
        raise ValueError("text is empty")
    key = key or harmony.Key(tonic_pc=0, mode='major')  # C major default

    phrases = encoding.tokenize(text)
    melody: list[NoteEvent] = []
    cursor = 0.0
    harmony_slots: list[tuple[float, float, int]] = []  # start, duration, melody_pc -- one per word

    for phrase in phrases:
        word_start_beat = cursor
        word_pitch_classes: list[int] = []
        prev_word_start = None
        for tok in phrase.tokens:
            if tok.is_word_start and prev_word_start is not None:
                dur = cursor - word_start_beat
                if dur > 0:
                    harmony_slots.append((word_start_beat, dur, _majority_pc(word_pitch_classes)))
                word_start_beat = cursor
                word_pitch_classes = []
            prev_word_start = True

            dur_beats = rhythm.letter_duration_beats(tok.char)
            vel = dynamics.token_velocity(tok.position_in_sentence, tok.is_word_start, tok.is_upper)
            note = harmony.snap_to_scale(tok.midi_note, key) if tonal else tok.midi_note
            melody.append(NoteEvent(cursor, dur_beats * 0.92, note, vel, tok.char))
            word_pitch_classes.append(note % 12)
            cursor += dur_beats

        if word_pitch_classes:
            dur = cursor - word_start_beat
            harmony_slots.append((word_start_beat, dur, _majority_pc(word_pitch_classes)))

        if phrase.terminator:
            vel = dynamics.terminator_velocity(phrase.terminator)
            cursor += rhythm.phrase_gap_beats(phrase.terminator)
        else:
            cursor += rhythm.word_gap_beats()

    # --- harmony: one Markov-sampled chord per word, biased by that word's melody.
    # Each chord voice-leads from the previous one (chord_midi_notes(prev=...))
    # instead of resetting to a fixed octave every time, so the pad and bass
    # glide by a few semitones per chord rather than jumping registers.
    degrees = harmony.generate_progression(key, [pc for _, _, pc in harmony_slots], seed=seed)
    harmony_track: list[NoteEvent] = []
    bass_track: list[NoteEvent] = []
    chord_progression: list[tuple[float, float, int]] = []
    prev_triad = None
    prev_bass = None
    bass_anchor = 12 * (bass_octave + 1)
    for (start, dur, _pc), degree in zip(harmony_slots, degrees):
        triad = harmony.chord_midi_notes(key, degree, octave=harmony_octave, prev=prev_triad)
        bass_root_pc = key.diatonic_triad(degree)[0]
        if prev_bass is None:
            bass_note = harmony.nearest_pitch(bass_root_pc, bass_anchor)
        else:
            bass_note = harmony.bounded_nearest_pitch(bass_root_pc, prev_bass, bass_anchor)
        prev_triad, prev_bass = triad, bass_note

        pad_dur = max(dur * 0.94, 0.1)
        for note in triad:
            harmony_track.append(NoteEvent(start, pad_dur, note, 46))
        bass_track.append(NoteEvent(start, pad_dur, bass_note, 58))
        chord_progression.append((start, dur, degree))

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
