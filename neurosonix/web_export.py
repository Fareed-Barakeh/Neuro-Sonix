"""Score -> JSON, for the browser-side interactive piano-roll player.

This is a separate, note-level export from the summary dict cli.py writes
to <stem>.json -- that one's for a human skimming results; this one's the
full data a <canvas> player needs to draw and animate every note.
"""
from __future__ import annotations

import json

from .compose import Score


def to_dict(score: Score, title: str = '') -> dict:
    distinct_keys = list(dict.fromkeys(c.key.name() for c in score.chord_progression))
    key_label = distinct_keys[0] if len(distinct_keys) <= 1 else f'{distinct_keys[0]} → {len(distinct_keys)} scales'
    return {
        'title': title,
        'text': score.text,
        'key': key_label or score.key.name(),
        'tempo_bpm': score.tempo_bpm,
        'length_beats': score.length_beats,
        'length_seconds': score.length_seconds,
        'tracks': {
            voice: [
                {'start': ev.start_beat, 'dur': ev.duration_beat, 'note': ev.midi_note,
                 'vel': ev.velocity, 'char': ev.char}
                for ev in events
            ]
            for voice, events in score.tracks.items()
        },
        'chords': [
            {'start': c.start_beat, 'dur': c.duration_beat, 'roman': c.key.chord_label(c.degree),
             'key': c.key.name()}
            for c in score.chord_progression
        ],
    }


def save(score: Score, path: str, title: str = '') -> None:
    with open(path, 'w') as f:
        json.dump(to_dict(score, title=title), f)


def bundle(web_json_paths: dict[str, str], out_path: str, var_name: str = 'NEUROSONIX_PIECES') -> None:
    """Combine several <stem>.web.json files (keyed by piece id) into one
    `const NAME = {...};` JS file -- what player.html actually loads, via a
    plain <script src>, so it works from a double-clicked file:// page too
    (fetch() of local JSON is blocked by CORS there; a script tag isn't)."""
    pieces = {}
    for piece_id, path in web_json_paths.items():
        with open(path) as f:
            pieces[piece_id] = json.load(f)
    with open(out_path, 'w') as f:
        f.write(f'const {var_name} = ')
        json.dump(pieces, f)
        f.write(';\n')
