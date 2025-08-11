# Define the mapping from letters to musical notes in Arabic Maqam Nahawand scale
nahawand_alphabet_to_notes = {
    'A': 'C4', 'B': 'D4', 'C': 'D4♯', 'D': 'E4',
    'E': 'F4', 'F': 'F4♯', 'G': 'G4', 'H': 'A4',
    'I': 'A4♯', 'J': 'B4', 'K': 'C5', 'L': 'D5',
    'M': 'D5♯', 'N': 'E5', 'O': 'F5', 'P': 'F5♯',
    'Q': 'G5', 'R': 'G5#', 'S': 'A5', 'T': 'A5♯',
    'U': 'B5', 'V': 'C6', 'W': 'D6', 'X': 'D6♯',
    'Y': 'E6', 'Z': 'F6'
}

# Ask the user for input
user_input = input("Enter a word or phrase: ")

# Convert the input to uppercase for consistency
user_input = user_input.upper()

# Create an empty list to store the mapped notes
mapped_notes = []

# Initialize a variable to keep track of spaces
space_flag = False

# Iterate through each character in the user's input
for character in user_input:
    # Check if the character is a letter and exists in the dictionary
    if character.isalpha() and character in nahawand_alphabet_to_notes:
        # Append the corresponding musical note to the mapped_notes list
        mapped_notes.append(nahawand_alphabet_to_notes[character])
        space_flag = False
    else:
        # For characters that are not letters or not in the dictionary, add a space if not already added
        if not space_flag:
            mapped_notes.append(" ")
            space_flag = True

# Join the mapped notes list into a single string
mapped_notes_str = ''.join(mapped_notes)

# Print the mapped musical notes with spaces between words
print("Mapped musical notes in Arabic Maqam Nahawand scale:", mapped_notes_str)