"""Score -> a piano-roll chart: what the text actually sounds like, as a picture."""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from .compose import Score
from .encoding import midi_to_note_name
from .harmony import PITCH_CLASS_NAMES
from .synth import GM_CRASH, GM_HIHAT, GM_KICK

BG = '#111113'
GRID = '#26262a'
COLORS = {
    'melody': '#3987e5', 'harmony': '#d95926', 'bass': '#199e70',
    'countermelody': '#9085e9', 'arpeggio': '#eec24c',
}
TRACK_LABELS = {
    'melody': 'Melody (text)', 'harmony': 'Harmony (Markov chords)', 'bass': 'Bass',
    'countermelody': 'Countermelody (parallel harmony)', 'arpeggio': 'Arpeggio (broken chords)',
    'percussion': 'Percussion',
}
PITCHED_DRAW_ORDER = ['bass', 'harmony', 'arpeggio', 'countermelody', 'melody']
DRUM_COLOR = {GM_KICK: '#e8e8e8', GM_HIHAT: '#7c7c82', GM_CRASH: '#eec24c'}


def plot(score: Score, title: str | None = None, out_path: str | None = None):
    fig, ax = plt.subplots(figsize=(15, 7.5), facecolor=BG)
    ax.set_facecolor(BG)

    pitched_tracks = [t for t in PITCHED_DRAW_ORDER if t in score.tracks and score.tracks[t]]
    has_percussion = bool(score.tracks.get('percussion'))

    all_notes = [ev.midi_note for t in pitched_tracks for ev in score.tracks[t]]
    lo, hi = min(all_notes) - 2, max(all_notes) + 2
    perc_lane_y = lo - 3.5
    plot_lo = perc_lane_y - 1.5 if has_percussion else lo

    # chord-region shading, lightly, with roman-numeral labels (computed
    # from each chord's own key, so this is correct even mid-modulation)
    prev_key_name = None
    for chord in score.chord_progression:
        ax.add_patch(Rectangle((chord.start_beat, plot_lo), chord.duration_beat, (hi + 1.5) - plot_lo,
                                 facecolor=COLORS['harmony'], alpha=0.05, linewidth=0, zorder=0))
        ax.text(chord.start_beat + chord.duration_beat / 2, hi - 0.6, chord.key.chord_label(chord.degree),
                 color='#c9946b', fontsize=8.5, ha='center', va='top', alpha=0.85)
        if chord.key.name() != prev_key_name:
            ax.axvline(chord.start_beat, color='#5a5f6e', linewidth=1, linestyle=':', alpha=0.7, zorder=1)
            ax.text(chord.start_beat + 0.1, hi + 1.1, chord.key.name(), color='#8f96a8',
                     fontsize=8, ha='left', va='top', style='italic')
            prev_key_name = chord.key.name()

    for voice in pitched_tracks:  # bass under, melody on top
        color = COLORS[voice]
        for ev in score.tracks[voice]:
            ax.add_patch(FancyBboxPatch(
                (ev.start_beat, ev.midi_note - 0.38), max(ev.duration_beat, 0.03), 0.76,
                boxstyle='round,pad=0,rounding_size=0.06',
                facecolor=color, edgecolor=BG, linewidth=0.6,
                alpha=0.35 + 0.5 * (ev.velocity / 127), zorder=3 if voice == 'melody' else 2,
            ))

    if has_percussion:
        ax.axhline(perc_lane_y + 1.6, color=GRID, linewidth=0.8)
        for ev in score.tracks['percussion']:
            color = DRUM_COLOR.get(ev.midi_note, '#ffffff')
            height = {GM_KICK: 1.4, GM_CRASH: 1.6, GM_HIHAT: 0.7}.get(ev.midi_note, 0.6)
            ax.add_patch(Rectangle((ev.start_beat, perc_lane_y), max(ev.duration_beat, 0.05), height,
                                     facecolor=color, edgecolor='none',
                                     alpha=0.4 + 0.5 * (ev.velocity / 127), zorder=2))

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
    ax.set_ylim(plot_lo, hi + 1.5)
    y_ticks = list(range(int(lo) - (int(lo) % 12), int(hi) + 12, 12))
    y_labels = [midi_to_note_name(n) for n in y_ticks]
    if has_percussion:
        perc_tick = perc_lane_y + 0.7
        # drop any note tick close enough to visually collide with the
        # percussion-lane tick, rather than risk them landing on top of
        # each other depending on where this piece's pitch range happens to sit
        kept = [(t, lbl) for t, lbl in zip(y_ticks, y_labels) if abs(t - perc_tick) > 2.5]
        y_ticks, y_labels = [t for t, _ in kept], [lbl for _, lbl in kept]
        y_ticks.append(perc_tick)
        y_labels.append('Perc.')
    ax.set_yticks(y_ticks)
    ax.set_yticklabels(y_labels)
    ax.set_xlabel('Beats', color='#c8c8c8', fontsize=11)
    ax.yaxis.grid(True, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors='#c8c8c8', labelsize=9.5)

    legend_tracks = pitched_tracks + (['percussion'] if has_percussion else [])
    handles = [plt.Line2D([0], [0], color=COLORS.get(v, '#c8c8c8'), lw=8, alpha=0.8) for v in legend_tracks]
    legend = ax.legend(handles, [TRACK_LABELS[v] for v in legend_tracks],
                         loc='upper right', frameon=True, labelcolor='white', fontsize=9.5)
    legend.get_frame().set_facecolor('#17181d')
    legend.get_frame().set_edgecolor('#2c2e36')
    legend.get_frame().set_alpha(0.92)

    distinct_keys = list(dict.fromkeys(c.key.name() for c in score.chord_progression))
    key_label = distinct_keys[0] if len(distinct_keys) <= 1 else f'{distinct_keys[0]} → {len(distinct_keys)} scales'

    ax.set_title(title or 'NeuroSonix Piano Roll', color='white', fontsize=19,
                  pad=16, loc='left', fontweight='bold')
    fig.text(0.1, 0.925,
             f'Key: {key_label}  ·  Tempo: {score.tempo_bpm:.0f} BPM  ·  '
             f'{len(score.tracks["melody"])} letters sonified',
             color='#9a9a9a', fontsize=10.5)

    plt.tight_layout(rect=(0, 0, 1, 0.9))
    if out_path:
        plt.savefig(out_path, dpi=200, facecolor=fig.get_facecolor())
    return fig
