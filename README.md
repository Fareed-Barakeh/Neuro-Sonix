Idea ideated by Khaled Barakeh, developed and implemented by Fareed Barakeh.

# NeuroSonix

NeuroSonix turns alphabetic text into a full, playable musical composition
— pitch, rhythm, dynamics, and harmony, rendered straight to MIDI, to
audio, and to a picture of the score. No DAW, no soundfont, no manual
copy-pasting between scripts: one command in, a finished piece out.

The original 2024 prototype (kept below, in `Code/legacy/`) proved the
core idea — that a sentence typed by hand could become a melody — but it
was a handful of disconnected scripts glued together by hand, each one
saving to a hardcoded path on the Desktop. This is a rewrite: one real
package, `neurosonix/`, with an honest account of what's rule-based, what's
statistical, and what's audio DSP — see [What's actually inside](#whats-actually-inside)
below, since the original README overstated the AI involved.

## Listen — and play

**[Open the interactive player](outputs/player.html)** — a browser page (no
install, no server) that plays either demo piece back with a synced,
animated piano roll and the source text highlighted letter by letter as it
sounds, karaoke-style.

Two demonstration pieces, both fully arranged (see
[Advanced arrangement](#advanced-arrangement) below) and in [`outputs/`](outputs/),
generated straight from the text files in [`examples/`](examples/):

| Piece | Text | Key | Melody | Listen |
|---|---|---|---|---|
| `manifesto` | [`examples/manifesto.txt`](examples/manifesto.txt) — a short statement of what this project is | D minor | chromatic (default) | [outputs/manifesto.mp3](outputs/manifesto.mp3) |
| `entropy` | [`examples/entropy.txt`](examples/entropy.txt) — on how rare letters get emphasized | D minor | tonal (`--tonal`) | [outputs/entropy.mp3](outputs/entropy.mp3) |

Each also has a `.mid` (open it in any DAW or notation program), a `.wav`
(the same audio, uncompressed), a `.png` piano roll, and a `.web.json` (the
data the interactive player reads).

![entropy.png](outputs/entropy.png)

## Quick start

```bash
pip install -r requirements.txt

python -m neurosonix compose "Some text to sonify." --out outputs/mine --key Am --tempo 100
# -> outputs/mine.mid, outputs/mine.wav, outputs/mine.png, outputs/mine.json, outputs/mine.web.json

python -m neurosonix compose "Some text." --out outputs/mine --arrange --tonal
# -> the same, plus a countermelody, arpeggio, and percussion layer (--arrange),
#    with the melody snapped onto the chosen scale instead of staying chromatic (--tonal)

python -m neurosonix batch examples/ --out outputs/ --arrange
# -> sonifies every .txt file in examples/, and refreshes outputs/neurosonix-data.js
#    (the bundle outputs/player.html reads)
```

Or from Python directly:

```python
from neurosonix.compose import compose
from neurosonix.harmony import Key
from neurosonix import render_midi, synth, visualize

score = compose("Some text to sonify.", tempo_bpm=100, key=Key(tonic_pc=9, mode='minor'))  # A minor
render_midi.save(score, "out.mid")
synth.save(score, "out.wav")
visualize.plot(score, out_path="out.png")
```

## How it works

```
Text
 │  encoding.py    — A-Z mapped to 26 consecutive chromatic semitones,
 ▼                    A = C2 through Z = C#4 (the original NeuroSonix rule,
 │                    unchanged since 2024's A Missing Camera)
Pitch
 │  rhythm.py       — each letter's duration comes from its Shannon
 ▼                    self-information under standard English letter
 │                    frequencies: common letters (E, T, A) are quick,
 │                    rare ones (Q, X, Z, J) land as long, weighted notes
Rhythm
 │  dynamics.py     — velocity follows a rise-and-settle arc across each
 ▼                    sentence, with accents on word starts and uppercase
 │                    letters, and a distinct gesture per terminator (. ! ?)
Dynamics
 │  harmony.py      — a hand-authored Markov chain over the seven diatonic
 ▼                    triads of the chosen key, reweighted at each step by
 │                    how well each candidate chord fits the melody note
 │                    sounding at that moment
Harmony
 │  render_midi.py  — three-track MIDI (melody / harmony / bass), General
 ▼                    MIDI instruments, exact ticks from a shared beat clock
 │  synth.py        — the same beat clock rendered directly to audio by a
 ▼                    small additive synthesizer (sine harmonics + ADSR per
 │                    voice) — nothing here needs an external soundfont
 │  visualize.py    — a piano-roll picture of the same data, letters and
 ▼                    chord names printed on the notes
MIDI + Audio + Picture
```

`compose.py` runs the whole chain and returns one `Score` object; `render_midi.py`,
`synth.py`, `visualize.py`, and `web_export.py` all read from that same
object, so the MIDI file, the audio, the picture, and the interactive
player can never drift out of sync with each other.

## Advanced arrangement

`compose()` alone produces three tracks: melody, a harmony pad, and bass.
`--arrange` (or `neurosonix.arrange.progressive_arrangement()` from Python)
runs a second pass over that same `Score` that applies four classic
arranging techniques, in order — this is the actual step-by-step technique,
not just a one-line flag:

1. **Harmonize the melody** — `add_countermelody()`. A second melodic line
   in parallel harmony with the lead, a third below, sounding only on
   accented notes (word starts, uppercase letters) so it reads as emphasis
   rather than a doubled line. This is the oldest harmonization trick
   there is: parallel thirds and sixths, the backbone of close vocal
   harmony.
2. **Break the chords into motion** — `add_arpeggio()`. The harmony pad is
   static, sustained chords; this rolls each one into a
   root-third-fifth-third arpeggio at a 16th-note subdivision, so the
   harmony has rhythmic life instead of just sitting under the melody.
3. **Add a pulse** — `add_percussion()`. A minimal rhythm-section layer: a
   soft tick on every word, a stronger hit on every sentence, a crash on
   the final phrase.
4. **Stage the entrances** — `progressive_arrangement()`. The technique
   that actually makes an arrangement feel like it goes somewhere: layers
   1-3 don't all play from bar one. The piece opens with just melody and
   bass, the harmony pad enters at the second sentence, the countermelody
   and arpeggio at the third, and percussion only for the final phrase —
   the same build shape film scores and electronic production both lean
   on.

Each of the four functions returns a *new* `Score`; none of them mutate
`compose()`'s output, so the plain 3-track piece is always still available
by simply not calling `arrange`.

A related, separate knob: melody pitch is chromatic by default (see
[the pitch encoding](#how-it-works) above) — deliberately, since that
friction against the diatonic harmony is the original piece's character,
not a flaw to fix. `--tonal` (`compose(..., tonal=True)`) is the opt-in
alternative: `harmony.snap_to_scale()` pulls every melody note onto the
chosen key's scale, same rhythm and contour, fully consonant with the
chords underneath. `entropy` above uses it; `manifesto` doesn't, so the
two demo pieces show both.

One correctness note from building this: naively chaining "move each chord
voice to the nearest instance of its next pitch class" chord after chord
gives smooth *local* voice leading, but with nothing pulling a voice back
toward its home register, it can drift a bass line steadily downward over
a long piece with no bound. `harmony.bounded_nearest_pitch()` anchors each
voice to its fixed home-octave position and caps how far a step is allowed
to wander from it, keeping the smooth motion without the drift.

## What's actually inside

Worth being precise about, since the original README (below) named
TensorFlow and PyTorch, and neither is used anywhere in this codebase:

- **The pitch encoding is a fixed rule**, not learned: a lookup table, one
  semitone per letter.
- **Rhythm is a closed-form function** of a well-known information-theory
  quantity (letter self-information from published English letter
  frequencies) — not learned, not random.
- **Harmony is a Markov chain**: a 7×7 transition matrix over diatonic
  triads, hand-authored from ordinary functional-harmony tendencies (V
  resolves to I, ii favors V, and so on), sampled and reweighted by melody
  fit at each step. This is a real generative/statistical model — it is
  not a trained neural network, and there's no model file or training
  corpus in this repo. If a genuinely learned harmony model gets trained
  later, it belongs here as an alternative backend to `harmony.py`, not a
  rewrite of it.
- **Audio synthesis is deterministic DSP**: sine-harmonic additive
  synthesis with an ADSR envelope for pitched voices, noise/pitch-envelope
  synthesis for percussion — not a sample library.
- **The arrangement layer is rule-based arranging, not composition AI**:
  countermelody is a fixed parallel-third transposition, the arpeggio is a
  fixed broken-chord pattern, percussion follows a fixed word/sentence
  rule, and the "build" is staged by phrase index. Real techniques, hand-specified.

None of that makes the piece less real — a Markov chain reweighted by
melody fit is a genuine generative-music technique, and letter-entropy
rhythm is a legitimate sonification idea in its own right. It just isn't
deep learning, and this README won't claim it is.

## Automation

`python -m neurosonix batch <folder> --out <folder>` sonifies every `.txt`
file it finds — the batch-processing capability the original README
promised, now actually implemented.

## Project layout

```
neurosonix/        the current engine
  encoding.py         text -> chromatic pitch (the original rule)
  rhythm.py           letter-entropy -> note duration
  dynamics.py         sentence-arc -> velocity
  harmony.py          Markov chord progression + voice leading
  compose.py          orchestrates the four modules above into one Score
  arrange.py          the advanced-arrangement pass (see above)
  render_midi.py      Score -> .mid
  synth.py            Score -> .wav (built-in additive/noise synth)
  visualize.py        Score -> .png piano roll
  web_export.py       Score -> .web.json for outputs/player.html
  cli.py              `compose` / `batch` commands
examples/           input texts for the two demo pieces
outputs/            their rendered .mid / .wav / .mp3 / .png / .json /
                    .web.json, the data bundle, and player.html itself
Code/legacy/        the original 2024 prototype scripts, kept for history
Audio/ Midi/ Score/ Sheet/   the original "A Missing Camera" piece and its
                    finished audio, score, and sheet music
```

## Potential applications

Artistic sonification of written works, datasets, and archival material.
Cross-modal storytelling in exhibitions, immersive installations, and
interactive media. Algorithmic composition from textual inputs.
Accessibility tools for converting text into sound-based representations.
