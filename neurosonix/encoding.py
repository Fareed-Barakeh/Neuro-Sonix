"""Text -> pitch encoding.

This is NeuroSonix's original creative rule, preserved exactly from the
first version of the project (see Code/turn-into-text/A_Missing_Camera.py):
the alphabet is mapped onto 26 consecutive chromatic semitones, A = C2
through Z = C#4. Nothing about the encoding changes here -- what's new is
that it now drives a full composition (rhythm, dynamics, harmony) instead
of only producing a printable string of note names.
"""
from __future__ import annotations

from dataclasses import dataclass

BASE_MIDI_NOTE = 36  # C2: NeuroSonix's anchor note for the letter 'A'

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def letter_to_midi(letter: str) -> int:
    """A -> 36 (C2), B -> 37 (C#2), ... Z -> 61 (C#4)."""
    letter = letter.upper()
    if not ('A' <= letter <= 'Z'):
        raise ValueError(f"not a letter: {letter!r}")
    return BASE_MIDI_NOTE + (ord(letter) - ord('A'))


def midi_to_note_name(midi_note: int) -> str:
    octave = midi_note // 12 - 1
    name = NOTE_NAMES[midi_note % 12]
    return f"{name}{octave}"


@dataclass
class Token:
    """One playable event derived from a single character."""
    char: str
    midi_note: int
    is_word_start: bool
    is_upper: bool
    sentence_index: int
    position_in_sentence: int  # 0..1, this token's fractional place in its sentence


@dataclass
class Phrase:
    """One sentence's worth of tokens, plus the punctuation that ended it."""
    tokens: list[Token]
    terminator: str  # '.', '!', '?', or '' for the final unterminated phrase


def tokenize(text: str) -> list[Phrase]:
    """Split text into sentences, then into letter-tokens with light metadata.

    Non-letters (spaces, punctuation, digits) aren't dropped silently --
    they end words and, at sentence-ending punctuation, end phrases -- but
    they don't themselves become notes. This mirrors the original script's
    treatment of non-alphabetic characters as separators/rests.
    """
    phrases: list[Phrase] = []
    current_tokens: list[Token] = []
    word_start = True
    sentence_index = 0

    # crude sentence split that keeps the terminator attached to know
    # what kind of phrase-ending gesture to render (see dynamics.py)
    raw_sentences: list[tuple[str, str]] = []
    buf = []
    for ch in text:
        buf.append(ch)
        if ch in '.!?':
            raw_sentences.append((''.join(buf[:-1]), ch))
            buf = []
    if buf:
        raw_sentences.append((''.join(buf), ''))

    for sentence_text, terminator in raw_sentences:
        letters_only = [c for c in sentence_text if c.isalpha()]
        n = max(len(letters_only), 1)
        letter_i = 0
        word_start = True
        for ch in sentence_text:
            if ch.isalpha():
                tok = Token(
                    char=ch,
                    midi_note=letter_to_midi(ch),
                    is_word_start=word_start,
                    is_upper=ch.isupper(),
                    sentence_index=sentence_index,
                    position_in_sentence=letter_i / n,
                )
                current_tokens.append(tok)
                letter_i += 1
                word_start = False
            elif ch.isspace():
                word_start = True
            # other punctuation inside a sentence (commas, dashes...) is
            # simply not sonified as its own note -- it still breaks a
            # "word start" the same way a space does
            else:
                word_start = True
        if current_tokens or terminator:
            phrases.append(Phrase(tokens=current_tokens, terminator=terminator))
        current_tokens = []
        sentence_index += 1

    return [p for p in phrases if p.tokens]
