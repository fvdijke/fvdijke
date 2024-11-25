import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import platform
import os
import threading
import numpy as np
import simpleaudio as sa
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
import time
import mido
import sys
import configparser

# Ensure 'python-rtmidi' is available
try:
    import rtmidi  # Required for mido to access MIDI ports
except ImportError:
    print("The 'python-rtmidi' library is required for MIDI functionality.")
    sys.exit(1)


class PianoKey:
    """Class representing a single piano key."""

    def __init__(self, canvas, x, y, width, height, color, is_black=False,
                 note_name=None, frequency=None, midi_note=None, app=None):
        self.canvas = canvas
        self.is_black = is_black
        self.selected = False
        self.original_color = color
        self.note_name = note_name
        self.frequency = frequency
        self.midi_note = midi_note
        self.app = app  # Reference to the main application

        # Draw the key on the canvas
        self.rect = canvas.create_rectangle(x, y, x + width, y + height,
                                            fill=color, outline="black", width=1)

        # Bind mouse click to the key
        canvas.tag_bind(self.rect, "<Button-1>", self.on_click)

    def on_click(self, event):
        if not self.selected:
            # Mark the key as selected
            self.selected = True
            self.canvas.itemconfig(self.rect, fill="blue")
        else:
            # Deselect the key
            self.selected = False
            self.canvas.itemconfig(self.rect, fill=self.original_color)
        # Play the note if not muted
        if not self.app.is_muted:
            self.app.play_note_wrapper(self)
        # Update button states
        self.app.update_button_states()


class SavedKeyboard:
    """Class representing a saved keyboard (chord)."""

    def __init__(self, canvas, chord_name, key_states):
        self.canvas = canvas
        self.chord_name = chord_name
        self.key_states = key_states
        self.border_rect = None  # For highlighting during playback


class ScrollFrame(tk.Frame):
    """A scrollable frame class for Tkinter."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Create a canvas object and a vertical scrollbar for scrolling
        self.vscrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        self.vscrollbar.pack(fill=tk.Y, side=tk.RIGHT, expand=False)
        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0,
                                yscrollcommand=self.vscrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vscrollbar.config(command=self.canvas.yview)

        # Create a frame inside the canvas which will be scrolled
        self.scrollable_frame = tk.Frame(self.canvas)
        # Store the window item ID
        self.window_item = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')

        # Bind events to make sure the scrollable frame resizes properly
        self.scrollable_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Bind mousewheel events
        self.bind_mousewheel(self.canvas)

    def on_frame_configure(self, event):
        # Update the scroll region to encompass the inner frame
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        # Resize the inner frame to match the canvas size
        canvas_width = event.width
        self.canvas.itemconfigure(self.window_item, width=canvas_width)

    def bind_mousewheel(self, widget):
        # Cross-platform scrolling
        widget.bind("<Enter>", lambda _: widget.bind_all("<MouseWheel>", self._on_mousewheel))
        widget.bind("<Leave>", lambda _: widget.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        # Handle mousewheel scrolling
        if platform.system() == 'Windows':
            delta = int(-1 * (event.delta / 120))
        elif platform.system() == 'Darwin':
            delta = int(-1 * event.delta)
        else:
            delta = 1 if event.num == 5 else -1
        self.canvas.yview_scroll(delta, "units")


class PianoApp:
    def __init__(self, root):
        self.root = root

        # Initialize configuration
        self.config = configparser.ConfigParser()
        self.load_settings()

        # Initialize language variable
        self.language_var = tk.StringVar(value=self.config.get('Settings', 'language', fallback='en'))
        self.language_var.trace('w', self.change_language)

        # Translation dictionary
        self.translations = {
            'en': {
                'title': "Pianoman v1.0 by FvD",
                'song_name': "Song Name",
                'number_of_octaves': "Number of Octaves",
                'next_chord': "Next Chord",
                'save_chord': "Save Chord",
                'play_chord': "Play Chord",
                'clear_chord': "Clear Chord",
                'delete_chord': "Delete Chord",
                'play_song': "Play Song",
                'stop_song': "Stop Song",
                'mute_input': "Mute Input",
                'unmute_input': "Unmute Input",
                'what_chord': "What Chord?",
                'pc_volume': "PC Volume:",
                'midi_volume': "MIDI Volume:",
                'chord_speed': "Chord Speed:",
                'song_speed': "Song Speed:",
                'help': "Help",
                'file_menu': "File",
                'edit_menu': "Edit",
                'playback_menu': "Playback",
                'options_menu': "Options",
                'language_menu': "Language / Taal",
                'new_song': "New Song",
                'load_song': "Load Song",
                'save_song': "Save Song",
                'save_song_as': "Save Song As",
                'save_as_pdf': "Save as PDF",
                'print_pdf': "Print PDF",
                'exit': "Exit",
                'unsaved_changes_message': "You have unsaved changes. Do you want to save before exiting?",
                'save_song_prompt': "The song has not been saved yet. Do you want to save before exiting?",
                'delete_chord_message': "There is no chord in edit mode to delete.",
                'playing': "Playing:",
                'playback_stopped': "Playback stopped.",
                'invalid_note': "The note is out of MIDI range after octave adjustment.",
                'invalid_note_title': "Invalid Note",
                'chord_not_recognized': "Chord not recognized.",
                'chord_recognition_title': "Chord Recognition",
                'edit_keys_message': "Edit keys and press Save Chord when finished.",
                # Add other translations as needed
            },
            'nl': {
                'title': "Pianoman v1.0 door FvD",
                'song_name': "Liednaam",
                'number_of_octaves': "Aantal Octaven",
                'next_chord': "Volgend Akkoord",
                'save_chord': "Akkoord Opslaan",
                'play_chord': "Speel Akkoord",
                'clear_chord': "Wis Akkoord",
                'delete_chord': "Verwijder Akkoord",
                'play_song': "Speel Lied",
                'stop_song': "Stop Lied",
                'mute_input': "Geluid Uit",
                'unmute_input': "Geluid Aan",
                'what_chord': "Welk Akkoord?",
                'pc_volume': "PC Volume:",
                'midi_volume': "MIDI Volume:",
                'chord_speed': "Akkoordsnelheid:",
                'song_speed': "Liedsnelheid:",
                'help': "Help",
                'file_menu': "Bestand",
                'edit_menu': "Bewerken",
                'playback_menu': "Afspelen",
                'options_menu': "Opties",
                'language_menu': "Taal / Language",
                'new_song': "Nieuw Lied",
                'load_song': "Laad Lied",
                'save_song': "Bewaar Lied",
                'save_song_as': "Bewaar Lied Als",
                'save_as_pdf': "Bewaar als PDF",
                'print_pdf': "Print PDF",
                'exit': "Afsluiten",
                'unsaved_changes_message': "Je hebt niet-opgeslagen wijzigingen. Wil je opslaan voor het afsluiten?",
                'save_song_prompt': "Het lied is nog niet opgeslagen. Wil je opslaan voor het afsluiten?",
                'delete_chord_message': "Er is geen akkoord in bewerkingsmodus om te verwijderen.",
                'playing': "Speelt:",
                'playback_stopped': "Afspelen gestopt.",
                'invalid_note': "De noot ligt buiten het MIDI-bereik na octaafaanpassing.",
                'invalid_note_title': "Ongeldige Noot",
                'chord_not_recognized': "Akkoord niet herkend.",
                'chord_recognition_title': "Akkoordherkenning",
                'edit_keys_message': "Bewerk toetsen en druk op Akkoord Opslaan wanneer klaar.",
                # Add other translations as needed
            }
        }

        # Set window title
        self.root.title(self.translations[self.language_var.get()]['title'])

        # Number of octaves (from settings, default is 4)
        self.octaves = self.config.getint('Settings', 'number_of_octaves', fallback=4)

        # Key dimensions
        self.white_key_width = 20
        self.white_key_height = 100
        self.black_key_width = 12
        self.black_key_height = 60

        # Calculate total width of a keyboard
        total_white_keys = self.octaves * 7
        keyboard_width = total_white_keys * self.white_key_width + 20  # Extra 20 pixels for margin
        keyboard_height = 150  # Height of the input keyboard canvas

        # Set main window dimensions
        window_width = int(2 * keyboard_width) + 50  # Extra margin for scrollbars and borders
        window_height = int(5 * keyboard_height) + 250  # Adjusted to fit new buttons
        self.root.geometry(f"{window_width}x{window_height}")

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Flag to track unsaved changes
        self.unsaved_changes = False
        self.song_saved = False  # Tracks if the song has been saved at least once
        self.current_song_file = None  # Stores the current song file path

        # Variable to store the last saved PDF file path
        self.last_pdf_file = None

        # Mute status
        self.is_muted = False

        # Output method (PC Audio or MIDI)
        self.output_method = tk.StringVar(value=self.config.get('Settings', 'output_method', fallback="PC Audio"))
        self.output_method.trace("w", self.update_midi_instrument_menu_state)  # Trace changes

        # MIDI output port
        self.midi_output = None
        self.selected_midi_port = self.config.get('Settings', 'midi_port', fallback=None)

        # MIDI instrument (default to Acoustic Grand Piano, program number 0)
        self.midi_instrument = self.config.getint('Settings', 'midi_instrument', fallback=0)
        self.midi_instrument_name = self.config.get('Settings', 'midi_instrument_name', fallback="Acoustic Grand Piano")

        # Volume controls
        self.pc_volume = tk.DoubleVar(value=self.config.getfloat('Settings', 'pc_volume', fallback=0.5))
        self.midi_volume = tk.IntVar(value=self.config.getint('Settings', 'midi_volume', fallback=64))

        # Song speed control (1 to 20, integer)
        self.song_speed = tk.IntVar(value=self.config.getint('Settings', 'song_speed', fallback=10))  # Default to medium speed

        # Chord speed control
        self.chord_speed = tk.IntVar(value=self.config.getint('Settings', 'chord_speed', fallback=0))  # 0 = all notes at once, 1-20 = arpeggiated speed

        # Starting octave for playback
        self.playback_octave = tk.IntVar(value=self.config.getint('Settings', 'playback_octave', fallback=0))

        # Help window relative position to main window
        self.help_window_rel_x = None
        self.help_window_rel_y = None

        # Flag to control song playback
        self.is_playing_song = False

        # Song Name Entry with Label
        self.song_name_var = tk.StringVar()
        song_name_frame = tk.Frame(root)
        song_name_frame.pack(pady=5)

        # Add a label for the song name
        self.song_name_label = tk.Label(song_name_frame, text=self.translations[self.language_var.get()]['song_name'])
        self.song_name_label.pack(side=tk.LEFT)

        self.song_name_entry = tk.Entry(song_name_frame, textvariable=self.song_name_var)
        self.song_name_entry.pack(side=tk.LEFT)
        self.song_name_var.trace("w", self.mark_unsaved)

        # Label for the number of octaves
        octave_frame = tk.Frame(root)
        octave_frame.pack(pady=5)
        self.octave_label = tk.Label(octave_frame, text=f"{self.translations[self.language_var.get()]['number_of_octaves']}: {self.octaves}")
        self.octave_label.pack(side=tk.LEFT)

        # Frame with scrollbar for saved keyboards using ScrollFrame
        self.saved_keyboards_frame = ScrollFrame(root)
        self.saved_keyboards_frame.pack(fill=tk.BOTH, expand=True)

        # Frame for the current row of keyboards
        self.current_row_frame = tk.Frame(self.saved_keyboards_frame.scrollable_frame)
        self.current_row_frame.pack(anchor='w')

        # Message label above the input keyboard
        self.message_label_var = tk.StringVar()
        self.message_label = tk.Label(root, textvariable=self.message_label_var, font=("Arial", 10), fg="red")
        self.message_label.pack()

        # Canvas for the input keyboard
        self.input_canvas = tk.Canvas(root, width=keyboard_width, height=keyboard_height, bg='lightgray',
                                      bd=0, highlightthickness=0)
        self.input_canvas.pack(pady=5)

        # Add chord name input field and "What Chord?" button
        self.chord_name_var = tk.StringVar()
        chord_name_frame = tk.Frame(root)
        chord_name_frame.pack(pady=5)
        self.chord_name_entry = tk.Entry(chord_name_frame, textvariable=self.chord_name_var, width=20, justify='center')
        self.chord_name_entry.pack(side=tk.LEFT)
        self.chord_name_var.trace("w", self.mark_unsaved)

        # Add the "What Chord?" button next to the input field
        self.what_chord_button = tk.Button(chord_name_frame, text=self.translations[self.language_var.get()]['what_chord'], command=self.recognize_chord)
        self.what_chord_button.pack(side=tk.LEFT, padx=5)

        # Status label to display the chord being played during playback
        self.playback_status_var = tk.StringVar()
        self.playback_status_label = tk.Label(root, textvariable=self.playback_status_var, font=("Arial", 12), fg="blue")
        self.playback_status_label.pack(pady=5)

        # Add buttons below the input keyboard
        button_frame = tk.Frame(root)
        button_frame.pack(pady=5)

        self.next_chord_button = tk.Button(button_frame, text=self.translations[self.language_var.get()]['next_chord'], command=self.save_and_reset_keyboard)
        self.next_chord_button.pack(side=tk.LEFT, padx=5)

        self.play_chord_button = tk.Button(button_frame, text=self.translations[self.language_var.get()]['play_chord'], command=self.play_chord)
        self.play_chord_button.pack(side=tk.LEFT, padx=5)

        self.clear_chord_button = tk.Button(button_frame, text=self.translations[self.language_var.get()]['clear_chord'], command=self.clear_keyboard)
        self.clear_chord_button.pack(side=tk.LEFT, padx=5)

        self.delete_chord_button = tk.Button(button_frame, text=self.translations[self.language_var.get()]['delete_chord'], command=self.delete_current_chord)
        self.delete_chord_button.pack(side=tk.LEFT, padx=5)

        self.play_song_button = tk.Button(button_frame, text=self.translations[self.language_var.get()]['play_song'], command=self.play_or_stop_song)
        self.play_song_button.pack(side=tk.LEFT, padx=5)

        self.mute_button = tk.Button(button_frame, text=self.translations[self.language_var.get()]['mute_input'], command=self.toggle_mute)
        self.mute_button.pack(side=tk.LEFT, padx=5)

        # Volume and Speed Controls
        volume_frame = tk.Frame(root)
        volume_frame.pack(pady=5)

        self.pc_volume_label = tk.Label(volume_frame, text=self.translations[self.language_var.get()]['pc_volume'])
        self.pc_volume_label.pack(side=tk.LEFT)
        self.pc_volume_slider = tk.Scale(volume_frame, from_=0, to=1, orient=tk.HORIZONTAL, resolution=0.01,
                                         variable=self.pc_volume)
        self.pc_volume_slider.pack(side=tk.LEFT)

        self.midi_volume_label = tk.Label(volume_frame, text=self.translations[self.language_var.get()]['midi_volume'])
        self.midi_volume_label.pack(side=tk.LEFT)
        self.midi_volume_slider = tk.Scale(volume_frame, from_=0, to=127, orient=tk.HORIZONTAL,
                                           variable=self.midi_volume)
        self.midi_volume_slider.pack(side=tk.LEFT)

        self.chord_speed_label = tk.Label(volume_frame, text=self.translations[self.language_var.get()]['chord_speed'])
        self.chord_speed_label.pack(side=tk.LEFT, padx=5)
        self.chord_speed_slider = tk.Scale(volume_frame, from_=0, to=20, orient=tk.HORIZONTAL,
                                           variable=self.chord_speed)
        self.chord_speed_slider.pack(side=tk.LEFT)

        self.song_speed_label = tk.Label(volume_frame, text=self.translations[self.language_var.get()]['song_speed'])
        self.song_speed_label.pack(side=tk.LEFT, padx=5)
        self.song_speed_slider = tk.Scale(volume_frame, from_=1, to=20, orient=tk.HORIZONTAL,
                                          variable=self.song_speed)
        self.song_speed_slider.pack(side=tk.LEFT)

        # List to keep track of saved keyboards
        self.saved_keyboards = []

        # Counter to track the number of keyboards per row
        self.keyboards_in_row = 0

        # Maximum number of keyboards per row
        self.max_keyboards_per_row = 2

        # Track which keyboard is currently being edited
        self.currently_editing_keyboard = None

        # Create the menu bar
        self.create_menu()

        # Draw the input keyboard (moved after button definitions)
        self.draw_piano()

        # Update button states
        self.update_button_states()

        # Load MIDI output if necessary
        if self.output_method.get() == "MIDI Output":
            self.load_midi_output()

    def create_menu(self):
        menubar = tk.Menu(self.root)

        lang = self.language_var.get()

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=self.translations[lang]['new_song'], command=self.new_song)
        file_menu.add_command(label=self.translations[lang]['load_song'], command=self.load_song)
        file_menu.add_command(label=self.translations[lang]['save_song'], command=self.save_song)
        file_menu.add_command(label=self.translations[lang]['save_song_as'], command=self.save_song_as)
        file_menu.add_separator()
        file_menu.add_command(label=self.translations[lang]['save_as_pdf'], command=self.save_pdf)
        file_menu.add_command(label=self.translations[lang]['print_pdf'], command=self.print_pdf)
        file_menu.add_separator()
        file_menu.add_command(label=self.translations[lang]['exit'], command=self.on_closing)
        menubar.add_cascade(label=self.translations[lang]['file_menu'], menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label=self.translations[lang]['next_chord'], command=self.save_and_reset_keyboard)
        edit_menu.add_command(label=self.translations[lang]['clear_chord'], command=self.clear_keyboard)
        edit_menu.add_command(label=self.translations[lang]['delete_chord'], command=self.delete_current_chord)
        menubar.add_cascade(label=self.translations[lang]['edit_menu'], menu=edit_menu)

        # Playback Menu
        playback_menu = tk.Menu(menubar, tearoff=0)
        playback_menu.add_command(label=self.translations[lang]['play_chord'], command=self.play_chord)
        playback_menu.add_command(label=self.translations[lang]['play_song'], command=self.play_or_stop_song)
        playback_menu.add_separator()
        self.is_muted_var = tk.BooleanVar(value=self.is_muted)
        playback_menu.add_checkbutton(label=self.translations[lang]['mute_input'], variable=self.is_muted_var, command=self.toggle_mute)
        menubar.add_cascade(label=self.translations[lang]['playback_menu'], menu=playback_menu)

        # Options Menu
        options_menu = tk.Menu(menubar, tearoff=0)
        output_menu = tk.Menu(options_menu, tearoff=0)
        output_menu.add_radiobutton(label="PC Audio", variable=self.output_method, value="PC Audio",
                                    command=self.change_output_method)
        output_menu.add_radiobutton(label="MIDI Output", variable=self.output_method, value="MIDI Output",
                                    command=self.change_output_method)
        options_menu.add_cascade(label="Output Method", menu=output_menu)

        # MIDI Device Submenu
        self.midi_device_menu = tk.Menu(options_menu, tearoff=0)
        options_menu.add_cascade(label="MIDI Devices", menu=self.midi_device_menu)
        self.update_midi_device_menu()

        # MIDI Instrument Submenu
        self.midi_instrument_menu = tk.Menu(options_menu, tearoff=0)
        options_menu.add_cascade(label="MIDI Instruments", menu=self.midi_instrument_menu)
        self.create_midi_instrument_menu()
        self.update_midi_instrument_menu_state()

        # Starting Octave Menu
        starting_octave_menu = tk.Menu(options_menu, tearoff=0)
        for i in range(-4, 5):
            starting_octave_menu.add_radiobutton(label=str(i), command=lambda i=i: self.set_playback_octave(i),
                                                 value=i, variable=self.playback_octave)
        options_menu.add_cascade(label="Starting Octave", menu=starting_octave_menu)

        # Octave Selection
        octave_menu = tk.Menu(options_menu, tearoff=0)
        for i in range(1, 5):
            octave_menu.add_radiobutton(label=str(i), command=lambda i=i: self.set_octaves(i),
                                        value=i, variable=tk.IntVar(value=self.octaves))
        options_menu.add_cascade(label=self.translations[lang]['number_of_octaves'], menu=octave_menu)

        # Language Selection Submenu
        language_menu = tk.Menu(options_menu, tearoff=0)
        options_menu.add_cascade(label=self.translations[lang]['language_menu'], menu=language_menu)

        language_menu.add_radiobutton(label="English / Engels", variable=self.language_var, value="en", command=self.change_language)
        language_menu.add_radiobutton(label="Dutch / Nederlands", variable=self.language_var, value="nl", command=self.change_language)

        menubar.add_cascade(label=self.translations[lang]['options_menu'], menu=options_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=self.translations[lang]['help'], command=self.show_help)
        menubar.add_cascade(label=self.translations[lang]['help'], menu=help_menu)

        self.root.config(menu=menubar)

    def update_midi_instrument_menu_state(self, *args):
        if self.output_method.get() == "MIDI Output":
            self.midi_instrument_menu.entryconfig("Instrument Groups", state="normal")
        else:
            self.midi_instrument_menu.entryconfig("Instrument Groups", state="disabled")

    def create_midi_instrument_menu(self):
        # General MIDI Instrument Families and Instruments
        self.instrument_families = [
            ("Piano", ["Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano",
                       "Honky-tonk Piano", "Electric Piano 1", "Electric Piano 2",
                       "Harpsichord", "Clavinet"]),
            ("Chromatic Percussion", ["Celesta", "Glockenspiel", "Music Box", "Vibraphone",
                                      "Marimba", "Xylophone", "Tubular Bells", "Dulcimer"]),
            ("Organ", ["Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
                       "Reed Organ", "Accordion", "Harmonica", "Tango Accordion"]),
            ("Guitar", ["Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)",
                        "Electric Guitar (clean)", "Electric Guitar (muted)", "Overdriven Guitar",
                        "Distortion Guitar", "Guitar harmonics"]),
            ("Bass", ["Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
                      "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2"]),
            ("Strings", ["Violin", "Viola", "Cello", "Contrabass", "Tremolo Strings",
                         "Pizzicato Strings", "Orchestral Harp", "Timpani"]),
            ("Ensemble", ["String Ensemble 1", "String Ensemble 2", "SynthStrings 1", "SynthStrings 2",
                          "Choir Aahs", "Voice Oohs", "Synth Choir", "Orchestra Hit"]),
            ("Brass", ["Trumpet", "Trombone", "Tuba", "Muted Trumpet", "French Horn",
                       "Brass Section", "SynthBrass 1", "SynthBrass 2"]),
            ("Reed", ["Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
                      "Oboe", "English Horn", "Bassoon", "Clarinet"]),
            ("Pipe", ["Piccolo", "Flute", "Recorder", "Pan Flute", "Blown Bottle",
                      "Shakuhachi", "Whistle", "Ocarina"]),
            ("Synth Lead", ["Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)",
                            "Lead 4 (chiff)", "Lead 5 (charang)", "Lead 6 (voice)",
                            "Lead 7 (fifths)", "Lead 8 (bass + lead)"]),
            ("Synth Pad", ["Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)",
                           "Pad 4 (choir)", "Pad 5 (bowed)", "Pad 6 (metallic)",
                           "Pad 7 (halo)", "Pad 8 (sweep)"]),
            ("Synth Effects", ["FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)",
                               "FX 4 (atmosphere)", "FX 5 (brightness)", "FX 6 (goblins)",
                               "FX 7 (echoes)", "FX 8 (sci-fi)"]),
            ("Ethnic", ["Sitar", "Banjo", "Shamisen", "Koto", "Kalimba",
                        "Bag pipe", "Fiddle", "Shanai"]),
            ("Percussive", ["Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
                            "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal"]),
            ("Sound Effects", ["Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
                               "Telephone Ring", "Helicopter", "Applause", "Gunshot"])
        ]

        self.midi_instrument_menu.add_command(label="Instrument Groups", state="normal")  # Dummy entry

        # Create submenus for instrument families
        for family_index, (family_name, instruments) in enumerate(self.instrument_families):
            family_menu = tk.Menu(self.midi_instrument_menu, tearoff=0)
            for instrument_index, instrument_name in enumerate(instruments):
                program_number = family_index * 8 + instrument_index
                family_menu.add_radiobutton(
                    label=instrument_name,
                    command=lambda p=program_number, n=instrument_name: self.select_midi_instrument(p, n),
                    variable=tk.IntVar(value=self.midi_instrument),
                    value=program_number
                )
            self.midi_instrument_menu.add_cascade(label=family_name, menu=family_menu)

    def select_midi_instrument(self, program_number, instrument_name, show_message=True):
        self.midi_instrument = program_number
        self.midi_instrument_name = instrument_name
        if self.midi_output:
            try:
                msg = mido.Message('program_change', program=program_number)
                self.midi_output.send(msg)
                if show_message:
                    messagebox.showinfo("MIDI Instrument", f"Instrument set to '{instrument_name}'.")
                self.save_settings()
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while setting the MIDI instrument:\n{e}")

    def update_midi_device_menu(self):
        self.midi_device_menu.delete(0, tk.END)
        available_ports = mido.get_output_names()
        if not available_ports:
            self.midi_device_menu.add_command(label="No MIDI devices available", state=tk.DISABLED)
        else:
            for port in available_ports:
                self.midi_device_menu.add_radiobutton(label=port, command=lambda p=port: self.select_midi_port(p),
                                                      value=port, variable=tk.StringVar(value=self.selected_midi_port))

    def select_midi_port(self, port_name):
        self.selected_midi_port = port_name
        if self.midi_output:
            self.midi_output.close()
        self.midi_output = mido.open_output(port_name)
        # Send program change message to set the instrument
        self.select_midi_instrument(self.midi_instrument, self.midi_instrument_name, show_message=False)  # Suppress message
        messagebox.showinfo("MIDI Output", f"MIDI output set to '{port_name}'.")
        self.save_settings()

    def set_octaves(self, num_octaves):
        self.octaves = num_octaves
        # Redraw the keyboard
        self.draw_piano()
        # Update the label
        lang = self.language_var.get()
        self.octave_label.config(text=f"{self.translations[lang]['number_of_octaves']}: {self.octaves}")
        self.save_settings()

    def set_playback_octave(self, octave):
        self.playback_octave.set(octave)
        self.save_settings()

    def change_output_method(self):
        method = self.output_method.get()
        if method == "MIDI Output":
            # Open MIDI output port
            self.load_midi_output()
        else:
            # Close MIDI output port if open
            if self.midi_output:
                self.midi_output.close()
                self.midi_output = None
        self.save_settings()
        self.update_midi_instrument_menu_state()

    def load_midi_output(self):
        available_ports = mido.get_output_names()
        if not available_ports:
            messagebox.showwarning("MIDI Output", "No MIDI output ports available.")
            self.output_method.set("PC Audio")
            return
        if self.selected_midi_port not in available_ports:
            self.selected_midi_port = available_ports[0]
        self.midi_output = mido.open_output(self.selected_midi_port)
        # Send program change message to set the instrument
        self.select_midi_instrument(self.midi_instrument, self.midi_instrument_name, show_message=False)  # Suppress message on startup
        self.save_settings()

    def mark_unsaved(self, *args):
        self.unsaved_changes = True

    def update_button_states(self):
        # Check if any keys are selected
        selected_keys = any(key.selected for key in self.white_keys + self.black_keys)
        if selected_keys:
            self.play_chord_button.config(state=tk.NORMAL)
            self.clear_chord_button.config(state=tk.NORMAL)
        else:
            self.play_chord_button.config(state=tk.DISABLED)
            self.clear_chord_button.config(state=tk.DISABLED)

        # Enable or disable the 'Delete Chord' button based on edit mode
        if self.currently_editing_keyboard:
            self.delete_chord_button.config(state=tk.NORMAL)
        else:
            self.delete_chord_button.config(state=tk.DISABLED)

    def save_and_reset_keyboard(self):
        # Calculate the width of the saved canvas
        canvas_width = self.input_canvas.winfo_width()
        canvas_height = self.input_canvas.winfo_height()

        # Save the keyboard state
        key_states = [key.selected for key in self.white_keys + self.black_keys]
        chord_name = self.chord_name_var.get()

        if self.currently_editing_keyboard:
            # Update the existing saved keyboard
            saved_keyboard = self.currently_editing_keyboard
            saved_keyboard.key_states = key_states
            saved_keyboard.chord_name = chord_name
            self.update_saved_canvas(saved_keyboard)
            # Reset the currently editing keyboard
            self.currently_editing_keyboard = None
            # Clear the message label
            self.message_label_var.set("")
            # Reset the button text back to "Next Chord"
            lang = self.language_var.get()
            self.next_chord_button.config(text=self.translations[lang]['next_chord'])
        else:
            # Create a new canvas to display the saved keyboard
            saved_canvas = tk.Canvas(self.current_row_frame, width=canvas_width, height=canvas_height + 20,  # Extra height for chord name
                                     bg='lightgray', bd=0, highlightthickness=0)

            saved_canvas.pack(side='left', padx=5, pady=5)
            self.keyboards_in_row += 1

            # Draw the keys on the saved canvas
            self.draw_saved_canvas(saved_canvas, key_states)

            # Add the chord name above the saved keyboard
            saved_canvas.create_text(canvas_width / 2, canvas_height + 10, text=chord_name, font=("Arial", 10))

            # Create a SavedKeyboard object and add it to the list
            saved_keyboard = SavedKeyboard(saved_canvas, chord_name, key_states)
            self.saved_keyboards.append(saved_keyboard)

            # Bind click event to load the saved keyboard for editing
            saved_canvas.bind("<Button-1>", lambda event, sk=saved_keyboard: self.load_keyboard(sk))

            if self.keyboards_in_row >= self.max_keyboards_per_row:
                # Start a new row
                self.current_row_frame = tk.Frame(self.saved_keyboards_frame.scrollable_frame)
                self.current_row_frame.pack(anchor='w', pady=5)
                self.keyboards_in_row = 0

            # Clear the message label
            self.message_label_var.set("")

        # Reset the input keyboard
        self.clear_keyboard()

        # Update the scroll region
        self.saved_keyboards_frame.canvas.update_idletasks()
        self.saved_keyboards_frame.canvas.configure(scrollregion=self.saved_keyboards_frame.canvas.bbox('all'))

        # Scroll to the bottom to show the latest keyboard
        self.saved_keyboards_frame.canvas.yview_moveto(1.0)

        # Mark as having unsaved changes
        self.unsaved_changes = True

    def draw_piano(self):
        # Clear existing keys if any
        self.input_canvas.delete("all")

        starting_midi_note = 48  # C3
        starting_octave = 3

        white_notes = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        white_key_offsets = [0, 2, 4, 5, 7, 9, 11]

        black_notes = ['C#', 'D#', '', 'F#', 'G#', 'A#', '']
        black_key_offsets = [1, 3, None, 6, 8, 10, None]

        x = 10
        y = 10

        self.white_keys = []
        self.black_keys = []

        total_white_keys = self.octaves * 7
        keyboard_width = total_white_keys * self.white_key_width + 20  # Extra 20 pixels for margin
        self.input_canvas.config(width=keyboard_width)

        for octave in range(self.octaves):
            # Draw white keys
            for i in range(len(white_notes)):
                note_name = white_notes[i] + str(starting_octave + octave)
                semitone_offset = white_key_offsets[i] + octave * 12
                midi_number = starting_midi_note + semitone_offset
                frequency = 440 * 2 ** ((midi_number - 69) / 12)
                key = PianoKey(
                    self.input_canvas,
                    x + (octave * 7 + i) * self.white_key_width,
                    y,
                    self.white_key_width,
                    self.white_key_height,
                    "white",
                    is_black=False,
                    note_name=note_name,
                    frequency=frequency,
                    midi_note=midi_number,
                    app=self  # Reference to main application
                )
                self.white_keys.append(key)

            # Draw black keys
            for i in range(len(black_notes)):
                if black_notes[i] != '':
                    note_name = black_notes[i] + str(starting_octave + octave)
                    semitone_offset = black_key_offsets[i] + octave * 12
                    midi_number = starting_midi_note + semitone_offset
                    frequency = 440 * 2 ** ((midi_number - 69) / 12)
                    key = PianoKey(
                        self.input_canvas,
                        x + (octave * 7 + i) * self.white_key_width + self.white_key_width - self.black_key_width / 2,
                        y,
                        self.black_key_width,
                        self.black_key_height,
                        "black",
                        is_black=True,
                        note_name=note_name,
                        frequency=frequency,
                        midi_note=midi_number,
                        app=self  # Reference to main application
                    )
                    self.black_keys.append(key)

        # Update button states
        self.update_button_states()

    def draw_saved_canvas(self, saved_canvas, key_states):
        all_keys = self.white_keys + self.black_keys
        for key, selected in zip(all_keys, key_states):
            fill_color = "blue" if selected else key.original_color
            coords = self.input_canvas.coords(key.rect)
            x1, y1, x2, y2 = coords
            tags = ('white_key',) if not key.is_black else ('black_key',)
            saved_canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=fill_color,
                outline="black",
                width=1,
                tags=tags
            )

    def update_saved_canvas(self, saved_keyboard):
        saved_canvas = saved_keyboard.canvas
        saved_canvas.delete("all")
        canvas_width = saved_canvas.winfo_width()
        canvas_height = saved_canvas.winfo_height() - 20  # 20 pixels for chord name

        # Draw the keys on the saved canvas
        self.draw_saved_canvas(saved_canvas, saved_keyboard.key_states)

        # Add the chord name above the saved keyboard
        chord_name = saved_keyboard.chord_name
        saved_canvas.create_text(canvas_width / 2, canvas_height + 10, text=chord_name, font=("Arial", 10))

    def load_keyboard(self, saved_keyboard):
        # Set the currently editing keyboard
        self.currently_editing_keyboard = saved_keyboard
        # Load the saved keys into the input keyboard
        key_states = saved_keyboard.key_states
        all_keys = self.white_keys + self.black_keys

        for key, selected in zip(all_keys, key_states):
            key.selected = selected
            fill_color = "blue" if selected else key.original_color
            self.input_canvas.itemconfig(key.rect, fill=fill_color)

        # Set the chord name
        self.chord_name_var.set(saved_keyboard.chord_name)

        # Show the message above the input keyboard
        lang = self.language_var.get()
        self.message_label_var.set(self.translations[lang]['edit_keys_message'])

        # Change the button text to "Save Chord"
        self.next_chord_button.config(text=self.translations[lang]['save_chord'])

        # Update button states
        self.update_button_states()

    def clear_keyboard(self):
        # Deselect all keys and reset colors
        for key in self.white_keys + self.black_keys:
            key.selected = False
            self.input_canvas.itemconfig(key.rect, fill=key.original_color)

        # Reset the chord name input field
        self.chord_name_var.set("")
        # Reset the currently editing keyboard
        self.currently_editing_keyboard = None
        # Clear the message label
        self.message_label_var.set("")

        # Reset the button text to "Next Chord"
        lang = self.language_var.get()
        self.next_chord_button.config(text=self.translations[lang]['next_chord'])

        # Update button states
        self.update_button_states()

    def delete_current_chord(self):
        if self.currently_editing_keyboard:
            # Remove the canvas of the current keyboard
            self.currently_editing_keyboard.canvas.destroy()
            # Remove the keyboard from the list
            index = self.saved_keyboards.index(self.currently_editing_keyboard)
            del self.saved_keyboards[index]

            # Update the GUI to shift subsequent keyboards
            # Remove all keyboards from the GUI
            for widget in self.saved_keyboards_frame.scrollable_frame.winfo_children():
                widget.destroy()

            # Reset the counter for keyboards per row
            self.keyboards_in_row = 0
            self.current_row_frame = tk.Frame(self.saved_keyboards_frame.scrollable_frame)
            self.current_row_frame.pack(anchor='w')

            # Redraw all saved keyboards
            for saved_keyboard in self.saved_keyboards:
                # Create a new canvas for each keyboard
                canvas_width = self.input_canvas.winfo_width()
                canvas_height = self.input_canvas.winfo_height()
                saved_canvas = tk.Canvas(self.current_row_frame, width=canvas_width, height=canvas_height + 20,
                                         bg='lightgray', bd=0, highlightthickness=0)
                saved_canvas.pack(side='left', padx=5, pady=5)
                self.keyboards_in_row += 1

                # Draw the keys on the saved canvas
                self.draw_saved_canvas(saved_canvas, saved_keyboard.key_states)

                # Add the chord name above the saved keyboard
                saved_canvas.create_text(canvas_width / 2, canvas_height + 10, text=saved_keyboard.chord_name, font=("Arial", 10))

                # Update the canvas of the saved keyboard
                saved_keyboard.canvas = saved_canvas

                # Bind click event to load the saved keyboard for editing
                saved_canvas.bind("<Button-1>", lambda event, sk=saved_keyboard: self.load_keyboard(sk))

                if self.keyboards_in_row >= self.max_keyboards_per_row:
                    # Start a new row
                    self.current_row_frame = tk.Frame(self.saved_keyboards_frame.scrollable_frame)
                    self.current_row_frame.pack(anchor='w', pady=5)
                    self.keyboards_in_row = 0

            # Reset the currently editing keyboard
            self.currently_editing_keyboard = None
            # Clear the message label
            self.message_label_var.set("")
            # Reset the button text to "Next Chord"
            lang = self.language_var.get()
            self.next_chord_button.config(text=self.translations[lang]['next_chord'])
            # Reset the input keyboard
            self.clear_keyboard()
            # Mark as having unsaved changes
            self.unsaved_changes = True
            # Update button states
            self.update_button_states()
        else:
            messagebox.showinfo(self.translations[self.language_var.get()]['delete_chord'], self.translations[self.language_var.get()]['delete_chord_message'])

    def new_song(self):
        if not self.song_saved:
            response = messagebox.askyesnocancel(self.translations[self.language_var.get()]['save_song'],
                                                 self.translations[self.language_var.get()]['save_song_prompt'])
            if response:  # User chose 'Yes' to save
                self.save_song()
            elif response is False:  # User chose 'No'
                pass
            else:
                return  # User chose 'Cancel' or closed the dialog

        self.song_name_var.set("")
        self.chord_name_var.set("")
        self.saved_keyboards.clear()
        self.keyboards_in_row = 0
        for widget in self.saved_keyboards_frame.scrollable_frame.winfo_children():
            widget.destroy()
        self.current_row_frame = tk.Frame(self.saved_keyboards_frame.scrollable_frame)
        self.current_row_frame.pack(anchor='w')
        self.clear_keyboard()
        self.unsaved_changes = False
        self.song_saved = False
        self.current_song_file = None

    def save_pdf(self):
        if not self.saved_keyboards:
            messagebox.showwarning("Save as PDF", "No chords have been saved yet.")
            return

        song_title = self.song_name_var.get() or "Untitled"
        default_pdf_path = self.config.get('Settings', 'default_pdf_path', fallback='')
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"{song_title}.pdf",
                                                 filetypes=[("PDF files", "*.pdf")],
                                                 initialdir=default_pdf_path)
        if not file_path:
            return  # User canceled

        # Save default PDF path
        self.config.set('Settings', 'default_pdf_path', os.path.dirname(file_path))
        self.save_settings()

        try:
            self.generate_pdf(file_path, song_title)
            # Store the last saved PDF file path
            self.last_pdf_file = file_path
            messagebox.showinfo("PDF Saved", f"The file '{file_path}' has been saved.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving the PDF:\n{e}")

    def generate_pdf(self, file_path, song_title):
        c = pdf_canvas.Canvas(file_path, pagesize=A4)
        page_width, page_height = A4
        margin = 50

        # Add title
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(page_width / 2, page_height - margin, song_title)

        # Calculate keyboard dimensions
        keyboard_width = page_width / 2 - margin * 1.5
        keyboard_height = 50
        white_key_width = keyboard_width / (self.octaves * 7)
        black_key_width = white_key_width * 0.6
        black_key_height = keyboard_height * 0.6

        x_position = margin
        y_position = page_height - margin - 50 - keyboard_height
        keyboards_in_row = 0
        keyboards_per_row = 2
        keyboards_in_page = 0
        keyboards_per_page = 8
        current_page = 1
        total_keyboards = len(self.saved_keyboards)
        total_pages = (total_keyboards - 1) // keyboards_per_page + 1

        for idx, saved_keyboard in enumerate(self.saved_keyboards, start=1):
            # Draw chord name
            c.setFont("Helvetica", 12)
            c.drawString(x_position, y_position + keyboard_height + 10, saved_keyboard.chord_name)

            # Draw keyboard
            all_keys = self.white_keys + self.black_keys
            key_states = saved_keyboard.key_states

            # Draw white keys
            for i, key in enumerate(all_keys):
                if not key.is_black:
                    x = x_position + i * white_key_width
                    y = y_position
                    c.rect(x, y, white_key_width, keyboard_height, stroke=1, fill=0)
                    if key_states[i]:
                        c.setFillColorRGB(0, 0, 1)  # Blue color
                        c.rect(x, y, white_key_width, keyboard_height, stroke=0, fill=1)
                        c.setFillColorRGB(0, 0, 0)  # Reset to black

            # Draw black keys
            for i, key in enumerate(all_keys):
                if key.is_black:
                    x = x_position + (i - 0.5) * white_key_width
                    y = y_position + keyboard_height - black_key_height
                    c.rect(x, y, black_key_width, black_key_height, stroke=1, fill=1)
                    if key_states[i]:
                        c.setFillColorRGB(0, 0, 1)  # Blue color
                        c.rect(x, y, black_key_width, black_key_height, stroke=0, fill=1)
                        c.setFillColorRGB(0, 0, 0)  # Reset to black

            # Update positions
            keyboards_in_row += 1
            keyboards_in_page += 1
            if keyboards_in_row >= keyboards_per_row:
                x_position = margin
                y_position -= keyboard_height + 70  # Adjust spacing
                keyboards_in_row = 0
            else:
                x_position += keyboard_width + margin

            if keyboards_in_page >= keyboards_per_page or y_position < margin:
                # Start a new page
                c.showPage()
                current_page += 1
                keyboards_in_page = 0
                x_position = margin
                y_position = page_height - margin - 50 - keyboard_height
                keyboards_in_row = 0

                # Add title again
                c.setFont("Helvetica-Bold", 16)
                c.drawCentredString(page_width / 2, page_height - margin, song_title)

            if idx == total_keyboards or keyboards_in_page == keyboards_per_page:
                # Add page numbering
                c.setFont("Helvetica", 10)
                c.drawCentredString(page_width / 2, margin / 2, f"Page {current_page} of {total_pages}")

        c.save()

    def print_pdf(self):
        if not self.last_pdf_file:
            messagebox.showwarning("Print PDF", "No PDF file has been saved yet.")
            return
        try:
            if platform.system() == 'Windows':
                # Use default PDF reader to print
                os.startfile(self.last_pdf_file, "print")
            elif platform.system() == 'Darwin':
                # macOS
                os.system(f'lpr \"{self.last_pdf_file}\"')
            else:
                # Linux and others
                os.system(f'lpr \"{self.last_pdf_file}\"')
            messagebox.showinfo("Print PDF", "PDF file sent to the printer.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while printing the PDF:\n{e}")

    def show_help(self):
        # Create a custom help window
        help_window = tk.Toplevel(self.root)
        help_window.title(self.translations[self.language_var.get()]['help'])

        # Set the help window position if previously saved
        if self.help_window_rel_x is not None and self.help_window_rel_y is not None:
            # Position relative to the main window
            main_x = self.root.winfo_x()
            main_y = self.root.winfo_y()
            help_window.geometry(f"+{main_x + self.help_window_rel_x}+{main_y + self.help_window_rel_y}")
        else:
            help_window.geometry("600x600")

        # Use ScrollFrame for the help window
        help_frame = ScrollFrame(help_window)
        help_frame.pack(fill=tk.BOTH, expand=True)

        scrollable_frame = help_frame.scrollable_frame

        # Help message with explanations of all functionalities
        help_text_en = (
            "Welcome to Pianoman!\n\n"
            "With this application, you can visualize piano chords, hear the notes, and save them as a PDF.\n\n"
            "Features:\n"
            "- **Song Name:** Enter and translate the song name dynamically.\n"
            "- **Number of Octaves:** Select the number of octaves for your keyboard.\n"
            "- **Chords:** Select keys to form chords, play them, save, edit, and delete.\n"
            "- **Playback:** Play individual chords or the entire song with adjustable speed.\n"
            "- **Volume Controls:** Adjust PC audio and MIDI volumes.\n"
            "- **MIDI Integration:** Choose MIDI output devices and instruments.\n"
            "- **Translations:** Switch between English and Dutch languages seamlessly.\n\n"
            "How to Use:\n"
            "1. **Select Keys:** Click on the piano keys to select/deselect them.\n"
            "2. **Name Chord:** Enter a name for your chord.\n"
            "3. **Save Chord:** Click 'Next Chord' to save the current chord.\n"
            "4. **Edit Chord:** Click on a saved chord to edit it. The 'Next Chord' button will change to 'Save Chord'.\n"
            "5. **Play Chord:** Play the selected chord.\n"
            "6. **Play Song:** Play all saved chords in sequence.\n\n"
            "For more detailed instructions, refer to the documentation or contact support."
        )

        help_text_nl = (
            "Welkom bij Pianoman!\n\n"
            "Met deze applicatie kun je piano-akkoorden visualiseren, de noten horen en ze opslaan als een PDF.\n\n"
            "Functies:\n"
            "- **Liednaam:** Voer de liednaam in en vertaal deze dynamisch.\n"
            "- **Aantal Octaven:** Selecteer het aantal octaven voor je keyboard.\n"
            "- **Akkoorden:** Selecteer toetsen om akkoorden te vormen, speel ze af, sla ze op, bewerk en verwijder ze.\n"
            "- **Afspelen:** Speel individuele akkoorden of het hele lied af met aanpasbare snelheid.\n"
            "- **Volumecontrole:** Pas het PC-audio- en MIDI-volume aan.\n"
            "- **MIDI-integratie:** Kies MIDI-uitvoerapparaten en instrumenten.\n"
            "- **Vertalingen:** Wissel naadloos tussen Engels en Nederlands.\n\n"
            "Hoe te gebruiken:\n"
            "1. **Selecteer Toetsen:** Klik op de piano toetsen om ze te selecteren/deselecteren.\n"
            "2. **Naam Akkoord:** Voer een naam in voor je akkoord.\n"
            "3. **Opslaan Akkoord:** Klik op 'Volgend Akkoord' om het huidige akkoord op te slaan.\n"
            "4. **Bewerken Akkoord:** Klik op een opgeslagen akkoord om het te bewerken. De knop 'Volgend Akkoord' verandert naar 'Akkoord Opslaan'.\n"
            "5. **Speel Akkoord:** Speel het geselecteerde akkoord af.\n"
            "6. **Speel Lied:** Speel alle opgeslagen akkoorden in volgorde af.\n\n"
            "Voor meer gedetailleerde instructies, raadpleeg de documentatie of neem contact op met ondersteuning."
        )

        lang = self.language_var.get()
        help_text = help_text_en if lang == 'en' else help_text_nl

        tk.Label(scrollable_frame, text=help_text, justify="left", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 0))

        # Add an Exit button at the bottom
        exit_button = tk.Button(scrollable_frame, text="Close Help" if lang == 'en' else "Sluit Help", command=help_window.destroy)
        exit_button.pack(pady=10)

        # Save help window position on close
        def save_help_window_position():
            # Get positions relative to the main window
            self.help_window_rel_x = help_window.winfo_x() - self.root.winfo_x()
            self.help_window_rel_y = help_window.winfo_y() - self.root.winfo_y()
            self.save_settings()
            help_window.destroy()

        help_window.protocol("WM_DELETE_WINDOW", save_help_window_position)

    def save_song(self):
        if self.current_song_file:
            file_path = self.current_song_file
        else:
            result = self.save_song_as()  # Prompt for file name if not already saved
            if not result:
                return
            else:
                file_path = self.current_song_file
        try:
            # Prepare data to save
            song_data = {
                "song_name": self.song_name_var.get(),
                "saved_keyboards": [],
                "number_of_octaves": self.octaves
            }
            for saved_keyboard in self.saved_keyboards:
                song_data["saved_keyboards"].append({
                    "chord_name": saved_keyboard.chord_name,
                    "key_states": saved_keyboard.key_states
                })
            # Write data to file
            with open(file_path, 'w') as f:
                json.dump(song_data, f)
            # Update song name
            self.song_name_var.set(song_data["song_name"])
            self.song_name_entry.delete(0, tk.END)
            self.song_name_entry.insert(0, song_data["song_name"])
            messagebox.showinfo("Save Song", f"Song saved successfully to '{file_path}'.")
            self.unsaved_changes = False
            self.song_saved = True
            self.current_song_file = file_path
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving the song:\n{e}")

    def save_song_as(self):
        try:
            song_title = self.song_name_var.get() or "Untitled"
            default_song_path = self.config.get('Settings', 'default_song_path', fallback='')
            # Ask the user for a file name to save the song
            file_path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=f"{song_title}.json",
                                                     filetypes=[("JSON files", "*.json")],
                                                     initialdir=default_song_path)
            if file_path:
                # Save default song path
                self.config.set('Settings', 'default_song_path', os.path.dirname(file_path))
                self.save_settings()
                # Prepare data to save
                song_data = {
                    "song_name": os.path.splitext(os.path.basename(file_path))[0],
                    "saved_keyboards": [],
                    "number_of_octaves": self.octaves
                }
                for saved_keyboard in self.saved_keyboards:
                    song_data["saved_keyboards"].append({
                        "chord_name": saved_keyboard.chord_name,
                        "key_states": saved_keyboard.key_states
                    })
                # Write data to file
                with open(file_path, 'w') as f:
                    json.dump(song_data, f)
                # Update song name
                self.song_name_var.set(song_data["song_name"])
                self.song_name_entry.delete(0, tk.END)
                self.song_name_entry.insert(0, song_data["song_name"])
                messagebox.showinfo("Save Song", f"Song saved successfully to '{file_path}'.")
                self.unsaved_changes = False
                self.song_saved = True
                self.current_song_file = file_path
                return True
            else:
                return False  # User canceled
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving the song:\n{e}")
            return False

    def load_song(self):
        # Ask the user to select a song file to load
        default_song_path = self.config.get('Settings', 'default_song_path', fallback='')
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")],
                                               initialdir=default_song_path)
        if file_path:
            try:
                # Save default song path
                self.config.set('Settings', 'default_song_path', os.path.dirname(file_path))
                self.save_settings()
                # Read data from file
                with open(file_path, 'r') as f:
                    song_data = json.load(f)
                # Clear current song
                self.new_song()
                # Set song name
                song_name = song_data.get("song_name", os.path.splitext(os.path.basename(file_path))[0])
                self.song_name_var.set(song_name)
                self.song_name_entry.delete(0, tk.END)
                self.song_name_entry.insert(0, song_name)

                # Set number of octaves if present
                self.octaves = song_data.get("number_of_octaves", self.octaves)
                self.set_octaves(self.octaves)

                # Load saved keyboards
                for keyboard_data in song_data.get("saved_keyboards", []):
                    # Recreate the saved keyboards
                    chord_name = keyboard_data["chord_name"]
                    key_states = keyboard_data["key_states"]
                    # Create a new saved keyboard
                    canvas_width = self.input_canvas.winfo_width()
                    canvas_height = self.input_canvas.winfo_height()
                    saved_canvas = tk.Canvas(self.current_row_frame, width=canvas_width, height=canvas_height + 20,
                                             bg='lightgray', bd=0, highlightthickness=0)

                    saved_canvas.pack(side='left', padx=5, pady=5)
                    self.keyboards_in_row += 1

                    # Draw the keys on the saved canvas
                    self.draw_saved_canvas(saved_canvas, key_states)

                    # Add the chord name above the saved keyboard
                    saved_canvas.create_text(canvas_width / 2, canvas_height + 10, text=chord_name, font=("Arial", 10))

                    # Create a SavedKeyboard object and add it to the list
                    saved_keyboard = SavedKeyboard(saved_canvas, chord_name, key_states)
                    self.saved_keyboards.append(saved_keyboard)

                    # Bind click event to load the saved keyboard for editing
                    saved_canvas.bind("<Button-1>", lambda event, sk=saved_keyboard: self.load_keyboard(sk))

                    if self.keyboards_in_row >= self.max_keyboards_per_row:
                        # Start a new row
                        self.current_row_frame = tk.Frame(self.saved_keyboards_frame.scrollable_frame)
                        self.current_row_frame.pack(anchor='w', pady=5)
                        self.keyboards_in_row = 0

                # Update the scroll region
                self.saved_keyboards_frame.canvas.update_idletasks()
                self.saved_keyboards_frame.canvas.configure(scrollregion=self.saved_keyboards_frame.canvas.bbox('all'))

                # Scroll to the bottom to show the latest keyboard
                self.saved_keyboards_frame.canvas.yview_moveto(1.0)

                self.unsaved_changes = False
                self.song_saved = True
                self.current_song_file = file_path

                messagebox.showinfo("Load Song", f"Song loaded successfully from '{file_path}'.")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while loading the song:\n{e}")

    def on_closing(self):
        try:
            lang = self.language_var.get()
            if not self.song_saved:
                response = messagebox.askyesnocancel(self.translations[lang]['save_song'],
                                                     self.translations[lang]['save_song_prompt'])
                if response:  # User chose 'Yes' to save
                    self.save_song()
                elif response is False:  # User chose 'No'
                    pass
                else:
                    return  # User chose 'Cancel' or closed the dialog
            elif self.unsaved_changes:
                response = messagebox.askyesnocancel(self.translations[lang]['save_song'],
                                                     self.translations[lang]['unsaved_changes_message'])
                if response:  # User chose 'Yes' to save
                    self.save_song()
                    self.root.destroy()
                elif response is False:  # User chose 'No'
                    self.root.destroy()
                else:
                    pass  # User chose 'Cancel' or closed the dialog
            else:
                self.root.destroy()
            # Save settings on exit
            self.save_settings()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while exiting:\n{e}")

    def play_note_wrapper(self, key):
        # Adjust the note according to playback octave
        octave_shift = self.playback_octave.get() * 12
        if self.output_method.get() == "MIDI Output" and self.midi_output:
            # Adjust MIDI note
            midi_note = key.midi_note + octave_shift
            if 0 <= midi_note <= 127:
                threading.Thread(target=self.play_midi_note, args=(midi_note,), daemon=True).start()
            else:
                lang = self.language_var.get()
                messagebox.showwarning(self.translations[lang]['invalid_note_title'], self.translations[lang]['invalid_note'])
        else:
            # Adjust frequency
            frequency = key.frequency * (2 ** self.playback_octave.get())
            threading.Thread(target=play_note_pc, args=(frequency,), kwargs={'volume': self.pc_volume.get()}, daemon=True).start()

    def play_midi_note(self, midi_note, duration=0.5):
        velocity = self.midi_volume.get()
        msg_on = mido.Message('note_on', note=midi_note, velocity=velocity)
        msg_off = mido.Message('note_off', note=midi_note, velocity=velocity)
        self.midi_output.send(msg_on)
        time.sleep(duration)
        self.midi_output.send(msg_off)

    def play_chord(self):
        # Collect selected keys
        selected_keys = [key for key in self.white_keys + self.black_keys if key.selected]
        if not selected_keys:
            # Should not happen since button is disabled when no keys are selected
            return
        # Sort keys from lowest to highest frequency
        selected_keys.sort(key=lambda k: k.frequency)
        if self.chord_speed.get() == 0:
            # Play all notes at once
            if self.output_method.get() == "MIDI Output" and self.midi_output:
                midi_notes = []
                octave_shift = self.playback_octave.get() * 12
                for key in selected_keys:
                    midi_note = key.midi_note + octave_shift
                    if 0 <= midi_note <= 127:
                        midi_notes.append(midi_note)
                    else:
                        lang = self.language_var.get()
                        messagebox.showwarning(self.translations[lang]['invalid_note_title'], self.translations[lang]['invalid_note'])
                        return
                threading.Thread(target=self.play_midi_chord, args=(midi_notes,), daemon=True).start()
            else:
                frequencies = [key.frequency * (2 ** self.playback_octave.get()) for key in selected_keys]
                # Generate and play chord
                threading.Thread(target=play_chord_pc, args=(frequencies,), kwargs={'volume': self.pc_volume.get()}, daemon=True).start()
        else:
            # Play notes one by one based on chord speed
            threading.Thread(target=self.play_arpeggiated_chord, args=(selected_keys,), daemon=True).start()

    def play_arpeggiated_chord(self, selected_keys):
        while selected_keys:
            speed = self.chord_speed.get()
            if speed == 0:
                delay = 0.1
            else:
                delay = 2.0 / speed  # Inverse relationship: higher speed = shorter delay
            key = selected_keys.pop(0)
            self.play_note_wrapper(key)
            start_time = time.time()
            while time.time() - start_time < delay:
                time.sleep(0.01)

    def play_midi_chord(self, midi_notes, duration=0.5):
        velocity = self.midi_volume.get()
        msgs_on = [mido.Message('note_on', note=note, velocity=velocity) for note in midi_notes]
        msgs_off = [mido.Message('note_off', note=note, velocity=velocity) for note in midi_notes]
        for msg in msgs_on:
            self.midi_output.send(msg)
        time.sleep(duration)
        for msg in msgs_off:
            self.midi_output.send(msg)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self.is_muted_var.set(self.is_muted)
        lang = self.language_var.get()
        if self.is_muted:
            self.mute_button.config(text=self.translations[lang]['unmute_input'])
        else:
            self.mute_button.config(text=self.translations[lang]['mute_input'])

    def play_or_stop_song(self):
        lang = self.language_var.get()
        if self.is_playing_song:
            # Stop song playback
            self.is_playing_song = False
            self.play_song_button.config(text=self.translations[lang]['play_song'])
            self.playback_status_var.set(self.translations[lang]['playback_stopped'])
        else:
            # Start song playback
            self.is_playing_song = True
            self.play_song_button.config(text=self.translations[lang]['stop_song'])
            threading.Thread(target=self._play_song_thread, daemon=True).start()

    def _play_song_thread(self):
        idx = 0
        total_chords = len(self.saved_keyboards)
        while idx < total_chords and self.is_playing_song:
            saved_keyboard = self.saved_keyboards[idx]
            chord_name = saved_keyboard.chord_name
            key_states = saved_keyboard.key_states
            all_keys = self.white_keys + self.black_keys
            selected_keys = [key for key, selected in zip(all_keys, key_states) if selected]
            if selected_keys:
                # Sort keys from lowest to highest frequency
                selected_keys.sort(key=lambda k: k.frequency)
                # Update playback status
                lang = self.language_var.get()
                self.playback_status_var.set(f"{self.translations[lang]['playing']} {chord_name}")
                self.root.after(0, self.root.update_idletasks)

                # Highlight the saved keyboard
                self.highlight_saved_keyboard(saved_keyboard)

                if self.chord_speed.get() == 0:
                    # Play all notes at once
                    if self.output_method.get() == "MIDI Output" and self.midi_output:
                        midi_notes = []
                        octave_shift = self.playback_octave.get() * 12
                        for key in selected_keys:
                            midi_note = key.midi_note + octave_shift
                            if 0 <= midi_note <= 127:
                                midi_notes.append(midi_note)
                            else:
                                lang = self.language_var.get()
                                messagebox.showwarning(self.translations[lang]['invalid_note_title'], self.translations[lang]['invalid_note'])
                                self.is_playing_song = False
                                break
                        if not self.is_playing_song:
                            break
                        self.play_midi_chord(midi_notes, duration=0.5)
                    else:
                        frequencies = [key.frequency * (2 ** self.playback_octave.get()) for key in selected_keys]
                        play_chord_pc(frequencies, duration=0.5, volume=self.pc_volume.get())
                else:
                    # Play notes one by one based on chord speed
                    self.play_arpeggiated_chord_during_song(selected_keys)

                # Calculate delay based on song speed
                delay = 2.0 / self.song_speed.get()  # Inverse relationship

                # Wait for the duration of the song speed
                start_time = time.time()
                while time.time() - start_time < delay:
                    if not self.is_playing_song:
                        break
                    time.sleep(0.1)
                if not self.is_playing_song:
                    break

                # Remove highlight
                self.unhighlight_saved_keyboard(saved_keyboard)
            idx += 1
        # Clear playback status after playback
        self.playback_status_var.set("")
        self.is_playing_song = False
        lang = self.language_var.get()
        self.play_song_button.config(text=self.translations[lang]['play_song'])

    def play_arpeggiated_chord_during_song(self, selected_keys):
        while selected_keys and self.is_playing_song:
            speed = self.chord_speed.get()
            if speed == 0:
                delay = 0.1
            else:
                delay = 2.0 / speed  # Inverse relationship: higher speed = shorter delay
            key = selected_keys.pop(0)
            self.play_note_wrapper(key)
            start_time = time.time()
            while time.time() - start_time < delay:
                if not self.is_playing_song:
                    break
                time.sleep(0.05)

    def highlight_saved_keyboard(self, saved_keyboard):
        saved_canvas = saved_keyboard.canvas
        x0, y0, x1, y1 = saved_canvas.bbox("all")
        saved_keyboard.border_rect = saved_canvas.create_rectangle(x0, y0, x1, y1, outline="red", width=2)

    def unhighlight_saved_keyboard(self, saved_keyboard):
        if saved_keyboard.border_rect:
            saved_keyboard.canvas.delete(saved_keyboard.border_rect)
            saved_keyboard.border_rect = None

    def save_settings(self):
        if not self.config.has_section('Settings'):
            self.config.add_section('Settings')
        self.config.set('Settings', 'number_of_octaves', str(self.octaves))
        self.config.set('Settings', 'output_method', self.output_method.get())
        self.config.set('Settings', 'midi_port', self.selected_midi_port or '')
        self.config.set('Settings', 'midi_instrument', str(self.midi_instrument))
        self.config.set('Settings', 'midi_instrument_name', self.midi_instrument_name)
        self.config.set('Settings', 'pc_volume', str(self.pc_volume.get()))
        self.config.set('Settings', 'midi_volume', str(self.midi_volume.get()))
        self.config.set('Settings', 'song_speed', str(self.song_speed.get()))
        self.config.set('Settings', 'chord_speed', str(self.chord_speed.get()))
        self.config.set('Settings', 'playback_octave', str(self.playback_octave.get()))
        self.config.set('Settings', 'language', self.language_var.get())
        if self.help_window_rel_x is not None and self.help_window_rel_y is not None:
            self.config.set('Settings', 'help_window_rel_x', str(self.help_window_rel_x))
            self.config.set('Settings', 'help_window_rel_y', str(self.help_window_rel_y))
        else:
            if self.config.has_option('Settings', 'help_window_rel_x'):
                self.config.remove_option('Settings', 'help_window_rel_x')
            if self.config.has_option('Settings', 'help_window_rel_y'):
                self.config.remove_option('Settings', 'help_window_rel_y')
        with open('settings.ini', 'w') as configfile:
            self.config.write(configfile)

    def load_settings(self):
        if os.path.exists('settings.ini'):
            self.config.read('settings.ini')
            # Load language setting
            self.language_var = tk.StringVar(value=self.config.get('Settings', 'language', fallback='en'))
            self.language_var.trace('w', self.change_language)
            # Load help window position relative to main window
            help_window_rel_x = self.config.get('Settings', 'help_window_rel_x', fallback=None)
            help_window_rel_y = self.config.get('Settings', 'help_window_rel_y', fallback=None)

            if help_window_rel_x and help_window_rel_x.strip() != '':
                self.help_window_rel_x = int(help_window_rel_x)
            else:
                self.help_window_rel_x = None

            if help_window_rel_y and help_window_rel_y.strip() != '':
                self.help_window_rel_y = int(help_window_rel_y)
            else:
                self.help_window_rel_y = None
        else:
            # Create default settings if settings.ini does not exist
            self.config['Settings'] = {
                'number_of_octaves': '4',
                'output_method': 'PC Audio',
                'midi_port': '',
                'midi_instrument': '0',
                'midi_instrument_name': 'Acoustic Grand Piano',
                'pc_volume': '0.5',
                'midi_volume': '64',
                'song_speed': '10',  # Default to medium speed
                'chord_speed': '0',
                'playback_octave': '0',
                'language': 'en'
            }
            with open('settings.ini', 'w') as configfile:
                self.config.write(configfile)
            # Initialize help window positions
            self.help_window_rel_x = None
            self.help_window_rel_y = None

    def recognize_chord(self):
        selected_keys = [key for key in self.white_keys + self.black_keys if key.selected]
        if not selected_keys:
            # No keys selected
            return

        # Get MIDI numbers of selected keys
        midi_notes = sorted([key.midi_note % 12 for key in selected_keys])  # Normalize to one octave (0-11)

        # Remove duplicates
        midi_notes = sorted(set(midi_notes))

        # Map MIDI note numbers to note names
        note_names_sharp = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

        # Try all possible roots
        possible_chords = []
        for root in midi_notes:
            intervals = [(note - root) % 12 for note in midi_notes]
            intervals = sorted(intervals)

            # Match intervals to chord types
            chord_type = self.match_intervals_to_chord(intervals)
            if chord_type:
                chord_name = f"{note_names_sharp[root]} {chord_type}"
                possible_chords.append(chord_name)

        if possible_chords:
            # Choose the most likely chord (first in the list)
            recognized_chord = possible_chords[0]
            self.chord_name_var.set(recognized_chord)
            # Suppress pop-up message
            # messagebox.showinfo("Chord Recognition", f"Recognized Chord: {recognized_chord}")
        else:
            # Suppress pop-up message
            lang = self.language_var.get()
            messagebox.showinfo(self.translations[lang]['chord_recognition_title'], self.translations[lang]['chord_not_recognized'])

    def match_intervals_to_chord(self, intervals):
        # Common chord types and their intervals
        chord_types = {
            'Major': [0, 4, 7],
            'Minor': [0, 3, 7],
            'Diminished': [0, 3, 6],
            'Augmented': [0, 4, 8],
            'Major Seventh': [0, 4, 7, 11],
            'Minor Seventh': [0, 3, 7, 10],
            'Dominant Seventh': [0, 4, 7, 10],
            'Suspended 2nd': [0, 2, 7],
            'Suspended 4th': [0, 5, 7],
            'Major Sixth': [0, 4, 7, 9],
            'Minor Sixth': [0, 3, 7, 9],
            'Ninth': [0, 4, 7, 10, 14],
            'Minor Ninth': [0, 3, 7, 10, 14],
            'Eleventh': [0, 4, 7, 10, 14, 17],
            'Minor Eleventh': [0, 3, 7, 10, 14, 17],
            'Thirteenth': [0, 4, 7, 10, 14, 17, 21],
            'Minor Thirteenth': [0, 3, 7, 10, 14, 17, 21],
            'Augmented Seventh': [0, 4, 8, 10],
            'Diminished Seventh': [0, 3, 6, 9],
            'Half-Diminished Seventh': [0, 3, 6, 10]
        }

        for chord_type, chord_intervals in chord_types.items():
            if chord_intervals == intervals:
                return chord_type
            # Check for subset match (e.g., if user plays only root and third)
            elif set(intervals).issubset(chord_intervals):
                return chord_type
        return None

    def change_language(self, *args):
        lang = self.language_var.get()

        # Update window title
        self.root.title(self.translations[lang]['title'])

        # Update labels
        self.octave_label.config(text=f"{self.translations[lang]['number_of_octaves']}: {self.octaves}")
        self.song_name_label.config(text=self.translations[lang]['song_name'])

        # Update buttons
        if self.currently_editing_keyboard:
            self.next_chord_button.config(text=self.translations[lang]['save_chord'])
        else:
            self.next_chord_button.config(text=self.translations[lang]['next_chord'])
        self.play_chord_button.config(text=self.translations[lang]['play_chord'])
        self.clear_chord_button.config(text=self.translations[lang]['clear_chord'])
        self.delete_chord_button.config(text=self.translations[lang]['delete_chord'])
        self.play_song_button.config(text=self.translations[lang]['play_song'] if not self.is_playing_song else self.translations[lang]['stop_song'])
        self.mute_button.config(text=self.translations[lang]['mute_input'] if not self.is_muted else self.translations[lang]['unmute_input'])
        self.what_chord_button.config(text=self.translations[lang]['what_chord'])

        # Update volume and speed labels
        self.pc_volume_label.config(text=self.translations[lang]['pc_volume'])
        self.midi_volume_label.config(text=self.translations[lang]['midi_volume'])
        self.chord_speed_label.config(text=self.translations[lang]['chord_speed'])
        self.song_speed_label.config(text=self.translations[lang]['song_speed'])

        # Update message labels
        self.message_label_var.set("")
        self.playback_status_var.set("")

        # Update menu labels by recreating the menu
        self.create_menu()

        # Save the selected language to settings
        self.save_settings()


# Function to play a single note using PC audio
def play_note_pc(frequency, duration=0.5, volume=0.5):
    fs = 44100  # Sampling rate
    t = np.linspace(0, duration, int(fs * duration), False)
    note = np.sin(frequency * t * 2 * np.pi)
    audio = note * volume * (2 ** 15 - 1) / np.max(np.abs(note))
    audio = audio.astype(np.int16)
    sa.play_buffer(audio, 1, 2, fs)


# Function to play a chord using PC audio
def play_chord_pc(frequencies, duration=0.5, volume=0.5):
    fs = 44100  # Sampling rate
    t = np.linspace(0, duration, int(fs * duration), False)
    # Generate sine wave for each frequency
    notes = [np.sin(frequency * t * 2 * np.pi) for frequency in frequencies]
    # Sum the notes
    audio = np.sum(notes, axis=0)
    # Normalize the audio to prevent clipping
    audio = audio / np.max(np.abs(audio))
    # Scale to 16-bit integer range and apply volume
    audio = audio * volume * (2 ** 15 - 1)
    audio = audio.astype(np.int16)
    sa.play_buffer(audio, 1, 2, fs)


if __name__ == "__main__":
    root = tk.Tk()
    app = PianoApp(root)
    root.mainloop()
