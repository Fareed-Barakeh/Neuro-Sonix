"""Score -> a piano-roll chart: what the text actually sounds like, as a picture."""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from .compose import Score
from .encoding import midi_to_note_name
from .harmony import PITCH_CLASS_NAMES

BG = '#111113'
GRID = '#26262a'
COLORS = {'melody': '#3987e5', 'harmony': '#d95926', 'bass': '#199e70'}


def plot(score: Score, title: str | None = None, out_path: str | None = None):
    fig, ax = plt.subplots(figsize=(15, 7.5), facecolor=BG)
    ax.set_facecolor(BG)

    all_notes = [ev.midi_note for evs in score.tracks.values() for ev in evs]
    lo, hi = min(all_notes) - 2, max(all_notes) + 2

    # chord-region shading, lightly, with roman-numeral labels
    for start, dur, degree in score.chord_progression:
        ax.add_patch(Rectangle((start, lo), dur, hi - lo, facecolor=COLORS['harmony'],
                                 alpha=0.05, linewidth=0, zorder=0))
        ax.text(start + dur / 2, hi - 0.6, score.key.roman_numerals[degree],
                 color='#c9946b', fontsize=8.5, ha='center', va='top', alpha=0.85)

    for voice in ('bass', 'harmony', 'melody'):  # draw order: bass under, melody on top
        color = COLORS[voice]
        for ev in score.tracks[voice]:
            ax.add_patch(FancyBboxPatch(
                (ev.start_beat, ev.midi_note - 0.38), ev.duration_beat, 0.76,
                boxstyle='round,pad=0,rounding_size=0.06',
                facecolor=color, edgecolor=BG, linewidth=0.6,
                alpha=0.35 + 0.5 * (ev.velocity / 127), zorder=3 if voice == 'melody' else 2,
            ))

    # letters on the melody line, so the piano roll doubles as a way to read
    # the text back off the score -- past a length where every letter would
    # just smear together, drop back to labeling every other note
    melody_notes = score.tracks['melody']
    stride = 1 if len(melody_notes) <= 120 else 2
    for ev in melody_notes[::stride]:
        if ev.char:
            ax.text(ev.start_beat + ev.duration_beat / 2, ev.midi_note + 0.55, ev.char.upper(),
                     color='white', fontsize=7.5, ha='center', va='bottom', alpha=0.85, fontweight='bold')

    ax.set_xlim(-0.5, score.length_beats + 1)
    ax.set_ylim(lo, hi + 1.5)
    y_ticks = range(int(lo) - (int(lo) % 12), int(hi) + 12, 12)
    ax.set_yticks(list(y_ticks))
    ax.set_yticklabels([midi_to_note_name(n) for n in y_ticks])
    ax.set_xlabel('Beats', color='#c8c8c8', fontsize=11)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors='#c8c8c8', labelsize=9.5)

    handles = [plt.Line2D([0], [0], color=COLORS[v], lw=8, alpha=0.8) for v in ('melody', 'harmony', 'bass')]
    ax.legend(handles, ['Melody (text)', 'Harmony (Markov chords)', 'Bass'],
               loc='upper right', frameon=False, labelcolor='white', fontsize=10)

    ax.set_title(title or 'NeuroSonix Piano Roll', color='white', fontsize=19,
                  pad=16, loc='left', fontweight='bold')
    fig.text(0.1, 0.925,
             f'Key: {score.key.name()}  ·  Tempo: {score.tempo_bpm:.0f} BPM  ·  '
             f'{len(score.tracks["melody"])} letters sonified',
             color='#9a9a9a', fontsize=10.5)

    plt.tight_layout(rect=(0, 0, 1, 0.9))
    if out_path:
        plt.savefig(out_path, dpi=200, facecolor=fig.get_facecolor())
    return fig
