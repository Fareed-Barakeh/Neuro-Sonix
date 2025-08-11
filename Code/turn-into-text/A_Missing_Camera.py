# Define the mapping from letters to musical notes
alphabet_to_notes = {
    
    'A': 'C2', 'B': 'C2#', 'C': 'D2', 'D': 'D2#',
    'E': 'E2', 'F': 'F2', 'G': 'F2#', 'H': 'G2',
    'I': 'G2#', 'J': 'A2', 'K': 'A2#', 'L': 'B2',
    'M': 'C3', 'N': 'C3#', 'O': 'D3', 'P': 'D3#',
    'Q': 'E3', 'R': 'F3', 'S': 'F3#', 'T': 'G3',
    'U': 'G3#', 'V': 'A3', 'W': 'A3#', 'X': 'B3',
    'Y': 'C4', 'Z': 'C4#'
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
    if character.isalpha() and character in alphabet_to_notes:
        # Append the corresponding musical note to the mapped_notes list
        mapped_notes.append(alphabet_to_notes[character])
        space_flag = False
    else:
        # For characters that are not letters or not in the dictionary, add a space if not already added
        if not space_flag:
            mapped_notes.append(" ")
            space_flag = True


# Join the mapped notes list into a single string
mapped_notes_str = ''.join(mapped_notes)


# Print the mapped musical notes with spaces between words
print("Mapped musical notes:", mapped_notes_str)
    
