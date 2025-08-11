import mido
from mido import MidiFile, MidiTrack, Message
import os

import mido
from mido import MidiFile, MidiTrack, Message

# Define a mapping of musical note names to MIDI note numbers
note_to_midi = {
    'C': 60, 'C♯': 61, 'D': 62, 'D♯': 63, 'E': 64, 'F': 65, 'F♯': 66, 'G': 67, 'G♯': 68, 'A': 69, 'A♯': 70, 'B': 71
    }


# Function to convert musical note name to MIDI note number
def note_to_midi_number(note_name):
    if note_name in note_to_midi:
        return note_to_midi[note_name]
    else:
        raise ValueError(f"Invalid note name: {note_name}")


# Input a series of musical notes in the form of a sentence
sentence_input = input("Enter a series of musical notes as a sentence: ")


# Split the input sentence into words
words = sentence_input.split()

# Create a MIDI file and track
mid = MidiFile()
track = MidiTrack()
mid.tracks.append(track)

# Iterate through the words and convert them to MIDI
for word in words:
    for char in word:
        try:
            # Convert the character to uppercase for consistency
            char = char.upper()
            # Check if the character is a letter and exists in the dictionary
            if char.isalpha() and char in note_to_midi:
                # Convert the character to MIDI note number
                midi_note = note_to_midi_number(char)
                # Add a note-on message for the character
                track.append(Message('note_on', note=midi_note, velocity=64, time=0))
                # Add a note-off message after some time (adjust time as needed)
                track.append(Message('note_off', note=midi_note, velocity=64, time=500))
            else:
                # For characters that are not letters or not in the dictionary, add a rest note (e.g., silence)
                track.append(Message('note_off', note=0, velocity=0, time=500))
        except ValueError as e:
            print(e)


# Save the MIDI file
desktop_path = os.path.expanduser("~/Desktop/")
midi_file_path = os.path.join(desktop_path, "output.mid")
mid.save(midi_file_path)
print(f"Transformed musical notes to MIDI and saved as '{midi_file_path}'.")
print("Transformed musical notes to MIDI and saved as 'output.mid'.")

# E4 E5C5A5♯A5♯C5F5A4♯ F4♯E4E5G4♯A5E4