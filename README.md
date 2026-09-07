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

## Listen

Two demonstration pieces are in [`outputs/`](outputs/), generated straight
from the text files in [`examples/`](examples/):

| Piece | Text | Key | Listen |
|---|---|---|---|
| `manifesto` | [`examples/manifesto.txt`](examples/manifesto.txt) — a short statement of what this project is | D minor | [outputs/manifesto.mp3](outputs/manifesto.mp3) |
| `entropy` | [`examples/entropy.txt`](examples/entropy.txt) — on how rare letters get emphasized | D minor | [outputs/entropy.mp3](outputs/entropy.mp3) |

Each also has a `.mid` (open it in any DAW or notation program), a `.wav`
(the same audio, uncompressed), and a `.png` piano roll showing the melody,
harmony, and bass together with the letters and chord names printed right
on the score.

![entropy.png](outputs/entropy.png)

## Quick start

```bash
pip install -r requirements.txt

python -m neurosonix compose "Some text to sonify." --out outputs/mine --key Am --tempo 100
# -> outputs/mine.mid, outputs/mine.wav, outputs/mine.png, outputs/mine.json

python -m neurosonix batch examples/ --out outputs/
# -> sonifies every .txt file in examples/
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
`synth.py`, and `visualize.py` all read from that same object, so the MIDI file,
the audio, and the picture can never drift out of sync with each other.

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
  synthesis with an ADSR envelope, not a sample library.

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
neurosonix/        the current engine (this README describes it)
examples/           input texts for the two demo pieces
outputs/            their rendered .mid / .wav / .mp3 / .png / .json
Code/legacy/        the original 2024 prototype scripts, kept for history
Audio/ Midi/ Score/ Sheet/   the original "A Missing Camera" piece and its
                    finished audio, score, and sheet music
```

## Potential applications

Artistic sonification of written works, datasets, and archival material.
Cross-modal storytelling in exhibitions, immersive installations, and
interactive media. Algorithmic composition from textual inputs.
Accessibility tools for converting text into sound-based representations.
