"""Rhythm from information content.

Rather than a fixed or random note length, each letter's duration is
driven by its Shannon self-information under standard English letter
frequencies: -log2(p(letter)). Common letters (E, T, A...) are quick;
rare ones (Q, X, Z, J...) land as long, emphasized notes. A sentence
made of rare letters reads as deliberate and weighty; one made of common
letters reads as fast and light -- rhythm carries the text's own entropy.
"""
from __future__ import annotations

import math

# standard English letter-frequency table (percent), Cornell/CIA-style
# corpus figures used widely in cryptography and typography references
ENGLISH_LETTER_FREQ = {
    'E': 12.70, 'T': 9.06, 'A': 8.17, 'O': 7.51, 'I': 6.97, 'N': 6.75,
    'S': 6.33, 'H': 6.09, 'R': 5.99, 'D': 4.25, 'L': 4.03, 'C': 2.78,
    'U': 2.76, 'M': 2.41, 'W': 2.36, 'F': 2.23, 'G': 2.02, 'Y': 1.97,
    'P': 1.93, 'B': 1.49, 'V': 0.98, 'K': 0.77, 'J': 0.15, 'X': 0.15,
    'Q': 0.10, 'Z': 0.07,
}

_TOTAL = sum(ENGLISH_LETTER_FREQ.values())
SELF_INFORMATION = {
    letter: -math.log2(freq / _TOTAL) for letter, freq in ENGLISH_LETTER_FREQ.items()
}
_MIN_INFO = min(SELF_INFORMATION.values())  # 'E', most common -> shortest note
_MAX_INFO = max(SELF_INFORMATION.values())  # 'Q'/'Z', rarest -> longest note

# musically quantized durations, in fractions of a beat (quarter note = 1.0)
DURATION_LEVELS = [1 / 4, 1 / 3, 1 / 2, 2 / 3, 1.0, 1.5]


def letter_duration_beats(letter: str) -> float:
    """Map a letter's rarity to a quantized note length, in beats."""
    info = SELF_INFORMATION.get(letter.upper(), (_MIN_INFO + _MAX_INFO) / 2)
    t = (info - _MIN_INFO) / (_MAX_INFO - _MIN_INFO)
    idx = round(t * (len(DURATION_LEVELS) - 1))
    return DURATION_LEVELS[idx]


def word_gap_beats() -> float:
    return 0.5


def phrase_gap_beats(terminator: str) -> float:
    """Longer rest for a harder stop -- a period breathes more than a comma-less run-on."""
    return {'.': 2.0, '!': 1.75, '?': 2.25}.get(terminator, 1.0)
