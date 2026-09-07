"""Command-line interface.

    python -m neurosonix compose "Some text to sonify." --out outputs/demo
    python -m neurosonix batch examples/ --out outputs/

Each run produces a .mid (playable in any DAW), a .wav (listen immediately,
no synth/soundfont needed), and a .png piano-roll of the composition.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import harmony, render_midi, synth, visualize
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


def _run_one(text: str, out_stem: pathlib.Path, tempo: float, key_str: str, seed: int | None) -> dict:
    key = _parse_key(key_str)
    score = compose(text, tempo_bpm=tempo, key=key, seed=seed)

    out_stem.parent.mkdir(parents=True, exist_ok=True)
    midi_path = out_stem.with_suffix('.mid')
    wav_path = out_stem.with_suffix('.wav')
    png_path = out_stem.with_suffix('.png')
    json_path = out_stem.with_suffix('.json')

    render_midi.save(score, str(midi_path))
    synth.save(score, str(wav_path))
    visualize.plot(score, title=out_stem.name.replace('_', ' ').title(), out_path=str(png_path))

    analysis = {
        'text': text,
        'key': key.name(),
        'tempo_bpm': tempo,
        'letters_sonified': len(score.tracks['melody']),
        'duration_seconds': round(score.length_seconds, 2),
        'chord_progression': [score.key.roman_numerals[d] for _, _, d in score.chord_progression],
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

    p_batch = sub.add_parser('batch', help='sonify every .txt file in a folder')
    p_batch.add_argument('input_dir')
    p_batch.add_argument('--out', default='outputs', help='output folder')
    p_batch.add_argument('--tempo', type=float, default=96.0)
    p_batch.add_argument('--key', default='C')
    p_batch.add_argument('--seed', type=int, default=None)

    args = parser.parse_args(argv)

    if args.command == 'compose':
        text = pathlib.Path(args.file).read_text() if args.file else args.text
        analysis = _run_one(text, pathlib.Path(args.out), args.tempo, args.key, args.seed)
        print(json.dumps(analysis, indent=2))

    elif args.command == 'batch':
        in_dir = pathlib.Path(args.input_dir)
        out_dir = pathlib.Path(args.out)
        txt_files = sorted(in_dir.glob('*.txt'))
        if not txt_files:
            print(f'no .txt files found in {in_dir}', file=sys.stderr)
            return 1
        for f in txt_files:
            text = f.read_text()
            analysis = _run_one(text, out_dir / f.stem, args.tempo, args.key, args.seed)
            print(f'{f.name}: {analysis["letters_sonified"]} letters, '
                   f'{analysis["duration_seconds"]}s -> {out_dir / f.stem}.{{mid,wav,png,json}}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
