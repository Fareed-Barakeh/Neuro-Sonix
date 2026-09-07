"""Command-line interface.

    python -m neurosonix compose "Some text to sonify." --out outputs/demo
    python -m neurosonix compose "Some text." --out outputs/demo --arrange --tonal
    python -m neurosonix compose "Some text." --out outputs/demo --modulate dorian,mixolydian,lydian,aeolian
    python -m neurosonix batch examples/ --out outputs/ --arrange

Each run produces a .mid (playable in any DAW), a .wav (listen immediately,
no synth/soundfont needed), a .png piano-roll, and a .web.json for the
browser player. --arrange adds a full arrangement (parallel-harmony
countermelody, arpeggiated chords, a percussion layer that builds in
across the piece) on top of the base melody/harmony/bass; --tonal snaps
the melody onto its active scale instead of staying fully chromatic;
--modulate cycles the harmony (and, with --tonal, the melody) through a
list of modes sharing --key's tonic, one per sentence, instead of staying
in a single scale for the whole piece.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import arrange, harmony, render_midi, synth, visualize, web_export
from .compose import compose

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def _parse_key(key_str: str) -> harmony.Key:
    key_str = key_str.strip()
    mode = 'minor' if key_str.lower().endswith('m') else 'major'
    root = key_str[:-1] if mode == 'minor' else key_str
    # accept forms like "C", "C#", "Cs", "Am", "F#m"
    root = root.strip().upper().replace('S', '#')
    if root not in NOTE_NAMES:
        raise ValueError(f"unrecognized key root: {key_str!r} (try e.g. C, G, Am, F#m)")
    return harmony.Key(tonic_pc=NOTE_NAMES.index(root), mode=mode)


def _parse_modulate(modulate_str: str, tonic_pc: int) -> list[harmony.Key]:
    """A comma-separated list of mode names, all sharing one tonic pitch
    class -- modal interchange: 'D dorian -> D mixolydian -> D aeolian',
    not a full key change each time."""
    modes = [m.strip().lower() for m in modulate_str.split(',') if m.strip()]
    keys = []
    for m in modes:
        canonical = harmony.MODE_ALIASES.get(m, m)
        if canonical not in harmony.MODE_STEPS:
            raise ValueError(f"unrecognized mode: {m!r} (try one of {harmony.MODE_NAMES})")
        keys.append(harmony.Key(tonic_pc=tonic_pc, mode=canonical))
    return keys


def _run_one(text: str, out_stem: pathlib.Path, tempo: float, key_str: str, seed: int | None,
              arranged: bool, tonal: bool, modulate_str: str | None) -> dict:
    key = _parse_key(key_str)
    modulate = _parse_modulate(modulate_str, key.tonic_pc) if modulate_str else None
    score = compose(text, tempo_bpm=tempo, key=key, seed=seed, tonal=tonal, modulate=modulate)
    if arranged:
        score = arrange.progressive_arrangement(score)

    out_stem.parent.mkdir(parents=True, exist_ok=True)
    midi_path = out_stem.with_suffix('.mid')
    wav_path = out_stem.with_suffix('.wav')
    png_path = out_stem.with_suffix('.png')
    json_path = out_stem.with_suffix('.json')
    web_path = out_stem.with_suffix('.web.json')

    render_midi.save(score, str(midi_path))
    synth.save(score, str(wav_path))
    visualize.plot(score, title=out_stem.name.replace('_', ' ').title(), out_path=str(png_path))
    web_export.save(score, str(web_path), title=out_stem.name.replace('_', ' ').title())

    distinct_keys = list(dict.fromkeys(c.key.name() for c in score.chord_progression))
    analysis = {
        'text': text,
        'key': key.name(),
        'scales_used': distinct_keys,
        'tempo_bpm': tempo,
        'arranged': arranged,
        'tonal': tonal,
        'tracks': sorted(score.tracks.keys()),
        'letters_sonified': len(score.tracks['melody']),
        'duration_seconds': round(score.length_seconds, 2),
        'chord_progression': [c.key.chord_label(c.degree) for c in score.chord_progression],
    }
    json_path.write_text(json.dumps(analysis, indent=2))
    return analysis


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='neurosonix', description=__doc__,
                                       formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    p_compose = sub.add_parser('compose', help='sonify one piece of text')
    p_compose.add_argument('text', help='text to sonify (quote it, or pass --file)')
    p_compose.add_argument('--file', help='read text from a file instead of the argument')
    p_compose.add_argument('--out', default='outputs/output', help='output path stem (no extension)')
    p_compose.add_argument('--tempo', type=float, default=96.0)
    p_compose.add_argument('--key', default='C', help='e.g. C, G, Am, F#m')
    p_compose.add_argument('--seed', type=int, default=None)
    p_compose.add_argument('--arrange', action='store_true',
                             help='add countermelody, arpeggio, and a building percussion layer')
    p_compose.add_argument('--tonal', action='store_true',
                             help='snap the melody onto its active scale instead of staying chromatic')
    p_compose.add_argument('--modulate', default=None,
                             help='comma-separated modes to cycle through per sentence, e.g. '
                                  'dorian,mixolydian,lydian,aeolian (shares --key\'s tonic)')

    p_batch = sub.add_parser('batch', help='sonify every .txt file in a folder')
    p_batch.add_argument('input_dir')
    p_batch.add_argument('--out', default='outputs', help='output folder')
    p_batch.add_argument('--tempo', type=float, default=96.0)
    p_batch.add_argument('--key', default='C')
    p_batch.add_argument('--seed', type=int, default=None)
    p_batch.add_argument('--arrange', action='store_true')
    p_batch.add_argument('--tonal', action='store_true')
    p_batch.add_argument('--modulate', default=None)

    args = parser.parse_args(argv)

    if args.command == 'compose':
        text = pathlib.Path(args.file).read_text() if args.file else args.text
        analysis = _run_one(text, pathlib.Path(args.out), args.tempo, args.key, args.seed,
                              args.arrange, args.tonal, args.modulate)
        print(json.dumps(analysis, indent=2))

    elif args.command == 'batch':
        in_dir = pathlib.Path(args.input_dir)
        out_dir = pathlib.Path(args.out)
        txt_files = sorted(in_dir.glob('*.txt'))
        if not txt_files:
            print(f'no .txt files found in {in_dir}', file=sys.stderr)
            return 1
        web_json_paths = {}
        for f in txt_files:
            text = f.read_text()
            analysis = _run_one(text, out_dir / f.stem, args.tempo, args.key, args.seed,
                                  args.arrange, args.tonal, args.modulate)
            print(f'{f.name}: {analysis["letters_sonified"]} letters, '
                   f'{analysis["duration_seconds"]}s -> {out_dir / f.stem}.{{mid,wav,png,json,web.json}}')
            web_json_paths[f.stem] = str((out_dir / f.stem).with_suffix('.web.json'))

        # keep the interactive player's data bundle in sync with whatever
        # batch just (re)rendered -- see outputs/player.html
        bundle_path = out_dir / 'neurosonix-data.js'
        web_export.bundle(web_json_paths, str(bundle_path))
        print(f'-> {bundle_path} (player data bundle for outputs/player.html)')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
