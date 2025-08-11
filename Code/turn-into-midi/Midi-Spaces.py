# -*- coding: utf-8 -*-

import mido
from mido import MidiFile, MidiTrack, Message
import os

# Define a mapping of musical note names to MIDI note numbers

note_to_midi = {
    'C2': 36, 'C2#': 37, 'D2': 38, 'D2#': 39, 'E2': 40, 'F2': 41, 'F2#': 42,
    'G2': 43, 'G2#': 44, 'A2': 45, 'A2#': 46, 'B2': 47,
    'C3': 48, 'C3#': 49, 'D3': 50, 'D3#': 51, 'E3': 52, 'F3': 53, 'F3#': 54,
    'G3': 55, 'G3#': 56, 'A3': 57, 'A3#': 58, 'B3': 59,
    'C4': 60, 'C4#': 61
}

# Function to convert a character with a number and optional sharp symbol to a MIDI note
def char_with_number_to_midi(char_with_number):
    char_with_number = char_with_number.upper()  # Convert to uppercase and replace hash with sharp symbol
    print(char_with_number)  # For debugging
    if char_with_number in note_to_midi:
        return note_to_midi[char_with_number]
    else:
        print(f"Note '{char_with_number}' not found in the dictionary.")  # For debugging
        return None


# Function to convert a word to a MIDI sequence
def word_to_midi_sequence(word):
    sequence = []
    i = 0
    while i < len(word):
        char = word[i]
        if char.isalpha():
            note = char
            i += 1
            # Check if the next characters are digits
            while i < len(word) and word[i].isdigit():
                note += word[i]
                i += 1   
                while i < len(word) and '#' in word[i] :
                    note += word[i]
                    i += 1   
                    #print(note)
            midi_note = char_with_number_to_midi(note)
            print(midi_note)
            
            if midi_note is not None:
                sequence.append(midi_note)
        else:
            i += 1  # Skip non-alphabetic characters
    return sequence


# Input a series of words as a sentence
sentence_input = input("Enter a series of words: ")


# Split the input sentence into words
words = sentence_input.split()


# Create a MIDI file and track
mid = MidiFile()
track = MidiTrack()
mid.tracks.append(track)


# Adjust this timing to control the note durations
note_duration = 500


# Iterate through the words and convert them to MIDI sequences with rest notes
for word in words:
    midi_sequence = word_to_midi_sequence(word)
    if midi_sequence:
        for midi_note in midi_sequence:
            # Add a note-on message for each MIDI note
            track.append(Message('note_on', note=midi_note, velocity=64, time=0))
            # Add a note-off message for each MIDI note
            track.append(Message('note_off', note=midi_note, velocity=64, time=note_duration))
        # Add a rest note (silence) after each word
        track.append(Message('note_off', note=0, velocity=0, time=note_duration))
    else:
        # Add a rest note (silence) for spaces between words
        track.append(Message('note_off', note=0, velocity=0, time=note_duration))


# Specify the desktop directory directly without using ~
desktop_path = "/Users/fareedbarakeh/Desktop/"


# Save the MIDI file on the desktop
midi_file_path = os.path.join(desktop_path, "x.mid")
mid.save(midi_file_path)
print(f"Transformed words to MIDI with spaces between words and saved as '{midi_file_path}'.")