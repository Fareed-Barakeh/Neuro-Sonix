"""Expressive dynamics (MIDI velocity) from sentence structure.

Each phrase gets a smooth arc -- a rise toward its emotional center and a
settle toward its punctuation -- rather than a flat velocity. Word starts
and uppercase letters (shouted emphasis, acronyms, names) accent on top
of that arc.
"""
from __future__ import annotations

import math

BASE_VELOCITY = 60
ARC_RANGE = 28       # how much the phrase-position arc can swing velocity
WORD_START_BOOST = 6
UPPERCASE_BOOST = 14
TERMINATOR_BOOST = {'!': 16, '?': 8, '.': 0}


def phrase_arc(position: float) -> float:
    """0..1 across a phrase -> a gentle rise-then-settle curve (0..1)."""
    return math.sin(position * math.pi) ** 0.7


def token_velocity(position_in_sentence: float, is_word_start: bool, is_upper: bool) -> int:
    v = BASE_VELOCITY + ARC_RANGE * phrase_arc(position_in_sentence)
    if is_word_start:
        v += WORD_START_BOOST
    if is_upper:
        v += UPPERCASE_BOOST
    return int(max(1, min(127, round(v))))


def terminator_velocity(terminator: str) -> int:
    return int(max(1, min(127, BASE_VELOCITY + ARC_RANGE + TERMINATOR_BOOST.get(terminator, 0))))
