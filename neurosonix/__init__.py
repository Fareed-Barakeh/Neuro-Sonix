"""NeuroSonix: text-to-music sonification.

Alphabetic text is mapped to pitch (chromatic, A=C2..Z=C#4), rhythm
(letter-frequency entropy), dynamics (sentence-phrase arcs and emphasis),
and harmony (a melody-biased Markov chord progression), then rendered to
MIDI, to audio (a built-in additive synth, no DAW required), and to a
piano-roll picture.

    from neurosonix.compose import compose
    from neurosonix import render_midi, synth, visualize

    score = compose("Some text to sonify.")
    render_midi.save(score, "out.mid")
    synth.save(score, "out.wav")
    visualize.plot(score, out_path="out.png")
"""
from .compose import Score, compose
from .harmony import Key

__all__ = ['compose', 'Score', 'Key']
__version__ = '2.0.0'
