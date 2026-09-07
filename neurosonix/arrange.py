"""Advanced arrangement: layering and harmonizing on top of a base Score.

compose.py produces the core three tracks (melody, harmony pad, bass) in
one pass. This module is a second, optional pass over that same Score that
applies four classic arranging techniques, in order:

  1. HARMONIZE THE MELODY  -- add_countermelody()
     A second melodic line moving in parallel with the lead, a third
     below, sounding only on accented notes (word starts / uppercase) so
     it reads as emphasis rather than doubling every note. This is the
     oldest harmonization trick in the book: parallel thirds/sixths, the
     backbone of close vocal harmony.

  2. BREAK THE CHORDS INTO MOTION -- add_arpeggio()
     The harmony pad is static, sustained chords. This turns each chord
     into a rolled (root-third-fifth-third) arpeggio at a faster
     subdivision, giving the harmony rhythmic life instead of just
     sitting underneath the melody.

  3. ADD A PULSE -- add_percussion()
     A minimal rhythm-section layer: a soft tick on every word, a
     stronger hit on every sentence start, and a crash on the final
     phrase. Percussion is what makes an arrangement feel driven rather
     than ambient.

  4. STAGE THE ENTRANCES -- progressive_arrangement()
     The technique that actually makes an arrangement feel like it goes
     somewhere: don't play every layer from bar one. This orchestrates
     1-3 so the piece opens with just melody and bass, then admits the
     harmony pad, then the arpeggio and countermelody, and only lets
     percussion in for the final phrase -- a build, the same shape film
     scores and electronic production both lean on.

Each function returns a *new* Score with additional tracks; none of them
mutate compose.py's output, so the plain 3-track piece is always still
available by simply not calling this module.
"""
from __future__ import annotations

import copy

from . import harmony
from .compose import NoteEvent, Score

# arpeggio subdivision, in beats (a 16th note at the piece's own tempo)
ARPEGGIO_STEP = 0.25
COUNTERMELODY_INTERVAL = -3  # a third below the lead

# percussion is General MIDI channel 10; these are its fixed key numbers
GM_KICK, GM_HIHAT, GM_CRASH = 36, 42, 49


def _key_at(score: Score, beat: float) -> harmony.Key:
    """Whichever chord's key is sounding at `beat` -- the local key for a
    modulating piece, or just the one key for a piece that isn't."""
    active = score.key
    for chord in score.chord_progression:
        if chord.start_beat <= beat:
            active = chord.key
        else:
            break
    return active


def add_countermelody(score: Score, interval: int = COUNTERMELODY_INTERVAL) -> Score:
    """A second voice in parallel harmony with the lead, on accented notes
    only. Snaps to whichever key is active at each note's own position, so
    this stays diatonic even through a modulation."""
    out = copy.deepcopy(score)
    counter: list[NoteEvent] = []
    for ev in score.tracks['melody']:
        if ev.velocity < 78:  # only the notes the phrase-arc/accent rules already emphasized
            continue
        raw = ev.midi_note + interval
        note = harmony.snap_to_scale(raw, _key_at(score, ev.start_beat))
        counter.append(NoteEvent(ev.start_beat, ev.duration_beat, note, max(1, ev.velocity - 22), ev.char))
    out.tracks['countermelody'] = counter
    return out


def add_arpeggio(score: Score, pattern: tuple[int, ...] = (0, 1, 2, 1)) -> Score:
    """Replace the static harmony pad with a rolled arpeggio at ARPEGGIO_STEP resolution."""
    out = copy.deepcopy(score)
    arp: list[NoteEvent] = []
    # group the existing pad by its chord (every 3 notes = one root/third/fifth chord)
    pad = score.tracks['harmony']
    for i in range(0, len(pad) - 2, 3):
        root, third, fifth = pad[i], pad[i + 1], pad[i + 2]
        chord_tones = [root.midi_note, third.midi_note, fifth.midi_note]
        t = root.start_beat
        end = root.start_beat + root.duration_beat
        step_i = 0
        while t < end:
            note = chord_tones[pattern[step_i % len(pattern)]]
            dur = min(ARPEGGIO_STEP, end - t) * 0.85
            vel = max(1, root.velocity - 6 + 4 * (step_i % 2))
            arp.append(NoteEvent(t, dur, note, vel, ''))
            t += ARPEGGIO_STEP
            step_i += 1
    out.tracks['arpeggio'] = arp
    return out


def add_percussion(score: Score) -> Score:
    """A soft tick per word, a stronger hit per sentence, a crash on the last phrase."""
    out = copy.deepcopy(score)
    perc: list[NoteEvent] = []
    word_starts = sorted({c.start_beat for c in _word_slots(score)})
    for beat in word_starts:
        perc.append(NoteEvent(beat, 0.12, GM_HIHAT, 46, ''))
    sentence_starts = _sentence_starts(score)
    for beat in sentence_starts:
        perc.append(NoteEvent(beat, 0.2, GM_KICK, 92, ''))
    if score.length_beats > 0:
        perc.append(NoteEvent(max(0.0, score.length_beats - 0.5), 1.0, GM_CRASH, 100, ''))
    out.tracks['percussion'] = perc
    return out


def _word_slots(score: Score):
    # chord_progression already carries one ChordEvent per word
    return score.chord_progression


def _sentence_starts(score: Score) -> list[float]:
    # a new sentence begins wherever a melody note follows a rest longer
    # than one word-gap -- cheap but effective without re-parsing the text
    melody = sorted(score.tracks['melody'], key=lambda e: e.start_beat)
    if not melody:
        return []
    starts = [melody[0].start_beat]
    for prev, cur in zip(melody, melody[1:]):
        gap = cur.start_beat - (prev.start_beat + prev.duration_beat)
        if gap > 0.9:  # bigger than a plain word_gap_beats() -> a phrase boundary
            starts.append(cur.start_beat)
    return starts


def progressive_arrangement(score: Score) -> Score:
    """Stage 1-3 in across the piece instead of all at once: melody + bass
    open it, the harmony pad enters at the second phrase, arpeggio and
    countermelody at the third, and percussion only for the final phrase.
    """
    arranged = add_percussion(add_arpeggio(add_countermelody(score), pattern=(0, 1, 2, 1)))
    sentence_starts = _sentence_starts(score)
    n = len(sentence_starts)

    def entrance_beat(stage: int) -> float:
        idx = min(stage, max(n - 1, 0))
        return sentence_starts[idx] if sentence_starts else 0.0

    harmony_from = entrance_beat(1) if n > 1 else 0.0
    layer_from = entrance_beat(2) if n > 2 else harmony_from
    perc_from = entrance_beat(max(n - 1, 0)) if n > 1 else 0.0

    arranged.tracks['harmony'] = [e for e in arranged.tracks['harmony'] if e.start_beat >= harmony_from]
    arranged.tracks['arpeggio'] = [e for e in arranged.tracks['arpeggio'] if e.start_beat >= layer_from]
    arranged.tracks['countermelody'] = [e for e in arranged.tracks['countermelody'] if e.start_beat >= layer_from]
    arranged.tracks['percussion'] = [e for e in arranged.tracks['percussion'] if e.start_beat >= perc_from]
    return arranged
