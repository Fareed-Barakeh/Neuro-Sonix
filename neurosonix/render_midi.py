"""Score -> a standard multi-track .mid file (mido), playable in any DAW."""
from __future__ import annotations

import mido

from .compose import Score

PPQ = 480  # ticks per quarter note

# General MIDI program numbers
GM_PROGRAM = {
    'melody': 73,        # Flute -- clear, single-voice, reads as "the text speaking"
    'harmony': 89,       # Pad 2 (warm) -- sustained chords under the melody
    'bass': 33,          # Fingered Bass
    'countermelody': 69, # Oboe -- distinct from the flute lead, sits just under it
    'arpeggio': 9,       # Glockenspiel -- bright, articulate, cuts through the pad
}

PERCUSSION_CHANNEL = 9  # GM channel 10 (0-indexed 9): fixed drum map, no program_change


def _beats_to_ticks(beats: float) -> int:
    return round(beats * PPQ)


def render(score: Score) -> mido.MidiFile:
    mid = mido.MidiFile(ticks_per_beat=PPQ)

    tempo_track = mido.MidiTrack()
    tempo_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(score.tempo_bpm), time=0))
    tempo_track.append(mido.MetaMessage('track_name', name='NeuroSonix', time=0))
    mid.tracks.append(tempo_track)

    fixed_channels = {'melody': 0, 'harmony': 1, 'bass': 2, 'countermelody': 3, 'arpeggio': 4}
    next_channel = max(fixed_channels.values()) + 1
    for name, events in score.tracks.items():
        track = mido.MidiTrack()
        is_percussion = name == 'percussion'
        if is_percussion:
            channel = PERCUSSION_CHANNEL
        else:
            if name not in fixed_channels:
                fixed_channels[name] = next_channel
                next_channel += 1
            channel = fixed_channels[name]
        track.append(mido.MetaMessage('track_name', name=name, time=0))
        if not is_percussion:
            track.append(mido.Message('program_change', program=GM_PROGRAM.get(name, 0), channel=channel, time=0))

        # flatten to (tick, is_note_on, note, velocity) then sort -- required
        # because mido tracks are a stream of *delta* times, and overlapping
        # chord/pad notes mean on/off events interleave across notes
        raw = []
        for ev in events:
            on_tick = _beats_to_ticks(ev.start_beat)
            off_tick = _beats_to_ticks(ev.start_beat + ev.duration_beat)
            if off_tick <= on_tick:
                off_tick = on_tick + 1
            raw.append((on_tick, 1, ev.midi_note, ev.velocity))
            raw.append((off_tick, 0, ev.midi_note, 0))
        raw.sort(key=lambda r: (r[0], r[1]))  # note_offs (0) before note_ons (1) at the same tick

        prev_tick = 0
        for tick, is_on, note, vel in raw:
            delta = max(0, tick - prev_tick)
            if is_on:
                track.append(mido.Message('note_on', note=note, velocity=vel, time=delta, channel=channel))
            else:
                track.append(mido.Message('note_off', note=note, velocity=0, time=delta, channel=channel))
            prev_tick = tick

        mid.tracks.append(track)

    return mid


def save(score: Score, path: str) -> None:
    render(score).save(path)
