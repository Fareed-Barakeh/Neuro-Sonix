"""Advanced arrangement: layering and harmonizing on top of a base Score.

compose.py produces the core three tracks (melody, harmony pad, bass) in
one pass. This module is a second, optional pass over that same Score that
applies four classic arranging techniques, in order:

  1. HARMONIZE THE MELODY  -- add_countermelody()
     A second melodic line moving in parallel with the lead, a sixth
     above, sounding only on accented notes (word starts / uppercase) so
     it reads as emphasis rather than doubling every note. This is the
     oldest harmonization trick in the book: parallel thirds/sixths, the
     backbone of close vocal harmony -- placed above rather than below the
     lead here on purpose, since this whole system's pitch range already
     sits low (see compose.py's harmony_octave/bass_octave note) and
     stacking a third *voice* underneath would only crowd it further.

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
     1-3 (and the vocal layer below, when asked for) so the piece opens
     with just melody and bass, then admits the harmony pad, then the
     arpeggio, countermelody, and choir together, and only lets
     percussion in for the final phrase -- a build, the same shape film
     scores and electronic production both lean on.

A fifth, optional technique lives here too, off by default
(`progressive_arrangement(score, vocal=True)`):

  5. GIVE IT A VOICE -- add_vocal()
     A wordless choir, sung on the text's own vowels (see synth.py's
     formant-filtered 'vocal' TIMBRES entry): every vowel letter in the
     melody becomes a held note at that same pitch, so the choir is
     literally singing the vowels the text already spells, doubling the
     lead rather than harmonizing away from it.

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
COUNTERMELODY_INTERVAL = 9  # a sixth above the lead -- see add_countermelody

# a sung vowel needs real time to actually read as sung rather than clipped
# -- see add_vocal
VOCAL_MIN_DUR_BEATS = 0.9
VOCAL_STRETCH_FRACTION = 3.0

# percussion is General MIDI channel 10; these are its fixed key numbers
GM_CRASH = 49  # the only percussion voice arrange.py uses now -- see add_percussion()


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


def add_vocal(score: Score) -> Score:
    """A wordless choir, sung on the text's own vowels (see
    synth.TIMBRES['vocal'] for the formant-filtered instrument behind it).
    Every vowel letter in the melody (a e i o u) becomes a held, softened
    note at that same pitch -- literally the choir singing the vowels the
    text is already spelling out, doubling the melody's own pitch rather
    than harmonizing away from it, while consonants pass by unvoiced.
    Held well past the letter's own brief duration, so it reads as a
    sustained vowel, not a clipped chromatic blip; neighboring vowels'
    held notes overlap into each other by design, the way a chord of
    voices naturally would, rather than each cutting the last one off."""
    out = copy.deepcopy(score)
    vocal: list[NoteEvent] = []
    for ev in score.tracks['melody']:
        if ev.char.upper() not in 'AEIOU':
            continue
        dur = max(ev.duration_beat * VOCAL_STRETCH_FRACTION, VOCAL_MIN_DUR_BEATS)
        vel = max(1, int(ev.velocity * 0.6))
        vocal.append(NoteEvent(ev.start_beat, dur, ev.midi_note, vel, ev.char))
    out.tracks['vocal'] = vocal
    return out


def add_arpeggio(score: Score, pattern: tuple[int, ...] = (0, 1, 2, 1, 3)) -> Score:
    """Replace the static harmony pad with a rolled arpeggio at ARPEGGIO_STEP
    resolution. Chords are 3 or 4 voices now (see harmony.chord_tones,
    ChordEvent.seventh) -- grouped by shared start_beat rather than a fixed
    stride, so a 7th chord's extra voice joins the roll instead of throwing
    off every chord after it."""
    out = copy.deepcopy(score)
    arp: list[NoteEvent] = []
    pad = score.tracks['harmony']

    groups: list[list] = []
    for ev in pad:
        if groups and groups[-1][0].start_beat == ev.start_beat:
            groups[-1].append(ev)
        else:
            groups.append([ev])

    for chord_notes in groups:
        chord_tones = [ev.midi_note for ev in chord_notes]
        root = chord_notes[0]
        t = root.start_beat
        end = root.start_beat + root.duration_beat
        step_i = 0
        while t < end:
            note = chord_tones[pattern[step_i % len(pattern)] % len(chord_tones)]
            dur = min(ARPEGGIO_STEP, end - t) * 0.85
            vel = max(1, root.velocity - 6 + 4 * (step_i % 2))
            arp.append(NoteEvent(t, dur, note, vel, ''))
            t += ARPEGGIO_STEP
            step_i += 1
    out.tracks['arpeggio'] = arp
    return out


def add_percussion(score: Score) -> Score:
    """A soft shimmer at each sentence start, a longer one closing the piece.

    No per-word ticking and no kick: a hi-hat clicking on every word is a
    rhythm-section device, the opposite of an ambient texture, and a kick's
    thud reads as percussive impact rather than atmosphere. What's dreamy
    about a "pulse" here isn't a beat, it's a sparse, soft chime marking
    where a new sentence (a new scale, a new arrangement layer) begins --
    see synth.py's GM_CRASH rendering, tuned as a shimmer, not a crash.
    """
    out = copy.deepcopy(score)
    perc: list[NoteEvent] = []
    sentence_starts = _sentence_starts(score)
    for i, beat in enumerate(sentence_starts):
        vel = 30 if i > 0 else 22  # the very first entrance stays almost inaudible
        perc.append(NoteEvent(beat, 1.0, GM_CRASH, vel, ''))
    if score.length_beats > 0:
        perc.append(NoteEvent(max(0.0, score.length_beats - 0.5), 1.2, GM_CRASH, 50, ''))
    out.tracks['percussion'] = perc
    return out


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


def progressive_arrangement(score: Score, vocal: bool = False, percussion: bool = True) -> Score:
    """Stage the layers in across the piece instead of all at once: melody
    + bass open it, the harmony pad enters at the second phrase, arpeggio,
    countermelody, and the choir (if `vocal`) all join at the third, and
    percussion (if `percussion`) only for the final phrase.
    """
    arranged = add_arpeggio(add_countermelody(score), pattern=(0, 1, 2, 1))
    if percussion:
        arranged = add_percussion(arranged)
    if vocal:
        arranged = add_vocal(arranged)
    sentence_starts = _sentence_starts(score)
    n = len(sentence_starts)

    def entrance_beat(stage: int) -> float:
        idx = min(stage, max(n - 1, 0))
        return sentence_starts[idx] if sentence_starts else 0.0

    harmony_from = entrance_beat(1) if n > 1 else 0.0
    layer_from = entrance_beat(2) if n > 2 else harmony_from
    vocal_from = layer_from  # joins alongside arpeggio/countermelody, not a further-delayed reveal
    perc_from = entrance_beat(max(n - 1, 0)) if n > 1 else 0.0

    arranged.tracks['harmony'] = [e for e in arranged.tracks['harmony'] if e.start_beat >= harmony_from]
    arranged.tracks['arpeggio'] = [e for e in arranged.tracks['arpeggio'] if e.start_beat >= layer_from]
    arranged.tracks['countermelody'] = [e for e in arranged.tracks['countermelody'] if e.start_beat >= layer_from]
    if percussion:
        arranged.tracks['percussion'] = [e for e in arranged.tracks['percussion'] if e.start_beat >= perc_from]
    if vocal:
        arranged.tracks['vocal'] = [e for e in arranged.tracks['vocal'] if e.start_beat >= vocal_from]
    return arranged
