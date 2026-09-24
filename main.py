import json
import os
import subprocess
import tempfile
import time
from signal import pause

import mido
from gpiozero import Button


PORT_NAME = "GuitarPedalPort"
TARGET_KEYWORDS = ("modep", "mod-host", "pisound")
CC_CHANNEL = 0
FEEDBACK_FILE = "/var/modep/button_feedback.json"


switches_config = {
    6: {"name": "Effect Toggle 1", "type": "cc", "val": 20},
    3: {"name": "Effect Toggle 2", "type": "cc", "val": 21},
    23: {"name": "Next Pedalboard", "type": "cmd", "val": "/usr/modep/scripts/next_pedalboard.sh"},
    5: {"name": "Prev Pedalboard", "type": "cmd", "val": "/usr/modep/scripts/prev_pedalboard.sh"},
}


def publish_feedback(message, feedback_file=FEEDBACK_FILE, timestamp=None):
    """Publish the latest button message atomically for the display service."""
    payload = {"message": message, "timestamp": time.time() if timestamp is None else timestamp}
    directory = os.path.dirname(feedback_file) or "."
    try:
        os.makedirs(directory, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as temporary_file:
            json.dump(payload, temporary_file)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = temporary_file.name
        os.replace(temporary_path, feedback_file)
    except OSError as error:
        print(f"Could not publish display feedback: {error}")


def find_target_input(input_names, keywords=TARGET_KEYWORDS):
    """Return the first MIDI input matching a known MODEP identifier."""
    return next(
        (name for name in input_names if any(keyword in name.lower() for keyword in keywords)),
        None,
    )


def open_midi_outputs(open_output=mido.open_output, get_input_names=mido.get_input_names):
    """Open the virtual output and an optional direct MODEP output."""
    midi_out = open_output(PORT_NAME, virtual=True)
    print(f"Virtual Port '{PORT_NAME}' initialized.")

    midi_connect = None
    target_input = find_target_input(get_input_names())
    if target_input:
        try:
            midi_connect = open_output(target_input)
            print(f"Successfully auto-routed signals directly into: '{target_input}'")
        except Exception as error:
            print(f"Found '{target_input}', but could not auto-route directly: {error}")
    else:
        print("Could not find a running MODEP input port in the system.")

    return midi_out, midi_connect


def handle_cc_press(
    pin_number,
    control_number,
    name,
    midi_out,
    midi_connect,
    cc_states,
    message_factory=mido.Message,
    channel=CC_CHANNEL,
):
    """Toggle a CC and broadcast the resulting MIDI message."""
    try:
        cc_states[control_number] = not cc_states[control_number]
        midi_value = 127 if cc_states[control_number] else 0
        message = message_factory(
            "control_change", channel=channel, control=control_number, value=midi_value
        )
        midi_out.send(message)
        if midi_connect is not None:
            try:
                midi_connect.send(message)
            except Exception as error:
                print(f"Failed sending to auto-route target: {error}")

        status = "ON" if cc_states[control_number] else "OFF"
        feedback = f"{name}: MIDI Ch {channel + 1} | CC {control_number} | {midi_value} ({status})"
        publish_feedback(feedback)
        print(f"{name} (Pin {pin_number}) sent CC {control_number} -> {midi_value} ({status})")
    except Exception as error:
        print(f"Error inside CC handler: {error}")


def handle_cmd_press(pin_number, script_path, name, popen=subprocess.Popen):
    """Run a pedalboard script without waiting for it to finish."""
    try:
        direction = "Next" if "next" in name.lower() else "Prev"
        publish_feedback(direction)
        print(f"{name} (Pin {pin_number}) running script: {script_path}")
        popen(["/bin/bash", script_path])
    except Exception as error:
        print(f"Shell script invocation failed: {error}")


def register_buttons(
    midi_out,
    midi_connect,
    button_factory=Button,
    configs=switches_config,
):
    """Create GPIO buttons and attach callbacks, returning successful buttons."""
    cc_states = {config["val"]: False for config in configs.values() if config["type"] == "cc"}
    buttons = []
    print("Initializing GPIO Pins...")

    for pin, config in configs.items():
        try:
            button = button_factory(pin, pull_up=True, bounce_time=0.05)
            if config["type"] == "cc":
                callback = lambda _, p=pin, c=config["val"], n=config["name"]: handle_cc_press(
                    p, c, n, midi_out, midi_connect, cc_states
                )
            else:
                callback = lambda _, p=pin, s=config["val"], n=config["name"]: handle_cmd_press(
                    p, s, n
                )
            button.when_pressed = callback
            button.when_released = callback
            buttons.append(button)
            print(f"Successfully registered hook on Pin {pin} ({config['name']})")
        except Exception as error:
            print(f"Failed to register hook on Pin {pin}: {error}")

    return buttons


def main():
    midi_out, midi_connect = open_midi_outputs()
    register_buttons(midi_out, midi_connect)
    print("\nDebounced Gpiozero Guitar Foot Controller Active")
    print("Press Ctrl+C to exit.")
    try:
        pause()
    except KeyboardInterrupt:
        print("\nShutting down cleanly... GPIO resources released automatically.")


if __name__ == "__main__":
    main()

