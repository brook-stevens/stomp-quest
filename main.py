import signal
import mido
import time
import subprocess
from gpiozero import Button
from signal import pause

# 1. Open your virtual software output port for CC toggles
port_name = 'GuitarPedalPort'
midi_out = mido.open_output(port_name, virtual=True)
print(f"✅ Virtual Port '{port_name}' initialized.")
time.sleep(1.0)

available_inputs = mido.get_input_names()
target_input = None
for name in available_inputs:
    if any(keyword in name.lower() for keyword in ["modep", "mod-host", "pisound"]):
        target_input = name
        break

if target_input:
    try:
        midi_connect = mido.open_output(target_input)
        print(f"🔗 Successfully auto-routed signals directly into: '{target_input}'")
    except Exception as e:
        print(f"⚠️ Found '{target_input}', but could not auto-route directly: {e}")
else:
    print("⚠️ Could not find a running MODEP input port in the system.")

# Global MIDI configurations
CC_CHANNEL = 0
cc_states = {20: False, 21: False}

# Move these to the very top (before the handlers) to guarantee they exist in scope
CC_CHANNEL = 0
cc_states = {20: False, 21: False}

# 2. Define the Action Handlers with crash protection
def handle_cc_press(pin_number, control_number, name):
    """Handles logic for CC Toggle switches"""
    global cc_states, midi_connect, CC_CHANNEL  # Explicitly declare global scopes
    print(f"🎸 {name} (Pin {pin_number}) Pressed!")
    
    try:
        # Toggle state
        cc_states[control_number] = not cc_states[control_number]
        midi_val = 127 if cc_states[control_number] else 0
        
        # Build and send message
        msg = mido.Message('control_change', channel=CC_CHANNEL, control=control_number, value=midi_val)
        midi_out.send(msg)
        
        # Try to pass to target input if it exists
        if 'midi_connect' in globals() and midi_connect is not None:
            try:
                midi_connect.send(msg)
            except Exception as midi_err:
                print(f"⚠️ Failed sending to auto-route target: {midi_err}")
                
        status = "ON" if cc_states[control_number] else "OFF"
        print(f"🎸 {name} (Pin {pin_number}) Pressed! Sent CC {control_number} -> Value: {midi_val} ({status})")
        
    except Exception as e:
        # Catching the error here keeps the background thread ALIVE
        print(f"❌ Error inside CC handler: {e}")

def handle_cmd_press(pin_number, script_path, name):
    """Handles running bash shell scripts"""
    try:
        print(f"🎛️ {name} (Pin {pin_number}) Stomped Down! Running Script: {script_path}")
        # Run process in background without waiting for it to finish
        subprocess.Popen(["/bin/bash", script_path])
    except Exception as e:
        print(f"❌ Shell Script invocation failed: {e}")


# 3. Map Pins to their configuration definitions
switches_config = {
    6: {"name": "Effect Toggle 1", "type": "cc", "val": 20},
    3: {"name": "Effect Toggle 2", "type": "cc", "val": 21},
    23: {"name": "Next Pedalboard", "type": "cmd", "val": "/usr/modep/scripts/next_pedalboard.sh"},
    5: {"name": "Prev Pedalboard", "type": "cmd", "val": "/usr/modep/scripts/prev_pedalboard.sh"},
}

# 4. Initialize Buttons with Gpiozero
button_objects = []

print("Initializing GPIO Pins...")
for pin, cfg in switches_config.items():
    try:
        # Keep bounce_time low (0.05) to filter out the mechanical click noise
        btn = Button(pin, pull_up=True, bounce_time=0.05)
        
        if cfg["type"] == "cc":
            # --- THE FIX FOR LATCHING SWITCHES ---
            # Trigger the handler on BOTH press and release so every single click counts
            btn.when_pressed = lambda _, p=pin, c=cfg["val"], n=cfg["name"]: handle_cc_press(p, c, n)
            btn.when_released = lambda _, p=pin, c=cfg["val"], n=cfg["name"]: handle_cc_press(p, c, n)
            
        elif cfg["type"] == "cmd":
            # Shell commands usually just need a single execution per physical click sequence
            btn.when_pressed = lambda _, p=pin, s=cfg["val"], n=cfg["name"]: handle_cmd_press(p, s, n)
            btn.when_released = lambda _, p=pin, s=cfg["val"], n=cfg["name"]: handle_cmd_press(p, s, n)
            
        button_objects.append(btn)
        print(f"✅ Successfully registered latching hook on Pin {pin} ({cfg['name']})")
        
    except Exception as initialization_error:
        print(f"❌ Critical Alert: Failed to register hook on Pin {pin}: {initialization_error}")


print("\n--- Debounced Gpiozero Guitar Foot Controller Active ---")
print("Pins 5,6 = CC Effects Toggle | Pins 23,27 = modep-ctrl Shell Scripts")
print("Press Ctrl+C to exit.")

try:
    # pause() blocks execution efficiently without burning CPU cycles in a while loop
    pause()
except KeyboardInterrupt:
    print("\nShutting down cleanly... GPIO resources released automatically.")

