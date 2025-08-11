# NeuroSonix
NeuroSonix is an AI-driven sonification system that transforms alphabetic text into structured music compositions. Letters are mapped to pitch, rhythm, and dynamics, with AI models enhancing the output through harmonic generation and expressive velocity shaping. Developed for the A Missing Camera installation in Weaving the Present, Shaping the Future at The MAC, Belfast, Northern Ireland, NeuroSonix turns written testimonies into immersive audio experiences that bridge algorithmic composition and human storytelling.

# Technical Overview
Text Encoding — Alphabetic characters mapped to numerical values representing pitch, duration, and dynamics.
Rule-Based Composition Layer — Deterministic mapping rules generate base melodies and rhythmic structures from text sequences.
AI Harmony Generation — Neural models trained on harmonic progressions add contextual chord structures to complement the base melody.
AI-Driven Velocity Mapping — Machine learning models adjust note velocities for expressive dynamics influenced by sentence structure and emotional emphasis.
Sound Synthesis — MIDI generation and synthesis pipeline renders the compositions into audio files for installation playback.
Automation — Batch processing capabilities for large sets of textual inputs.

        │Text (testimonies, phrases)
        ▼                           
        │Encoding (letter → pitch / duration / dynamics)
        ▼                                               
        │Base Melody (rule-based composition)
        ▼                                    
        │AI Harmony & Dynamics (neural chords + velocity shaping)
        ▼                                                                                                                                                         
        │MIDI (tracks, tempo, instrumentation) 
        ▼                                        
        │Audio (rendered in DAW)
        ▼                       

# Tools & Libraries
Python — Core processing and mapping logic.
MIDI Libraries — For generating and editing structured musical data (mido, pretty_midi).
ML Frameworks — TensorFlow / PyTorch for AI harmony and velocity models.
DAW Integration — For rendering, mixing, and mastering final audio output.
Custom Mapping Configurations — Allowing alternative text-to-sound mapping strategies.

# Potential Applications
Artistic sonification of written works, datasets, and archival material.
Cross-modal storytelling in exhibitions, immersive installations, and interactive media.
AI-assisted algorithmic composition from textual inputs.
Accessibility tools for converting text into sound-based representations.

# Context
Weaving the Present, Shaping the Future was a socially engaged art project by Khaled Barakeh amplifying the voices and experiences of asylum seekers in Northern Ireland through multiple artistic media. My contribution — NeuroSonix — added a sound dimension by sonifying personal testimonies, allowing these narratives to resonate beyond the written word.



