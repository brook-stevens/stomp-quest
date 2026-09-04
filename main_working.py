import signal
import mido
import time
import lgpio

# 1. Open your virtual software output port
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

# 2. Setup Parameters
CC_CHANNEL = 0        # Channel 1 for normal effects (0-indexed)
NAV_CHANNEL = 15      # Channel 16 for changing whole pedalboards (0-indexed)

# Define your 4 switches mapping pins to their data configuration
switches_config = {
    5:  {"name": "Effect Toggle 1",  "type": "cc", "val": 20},
    6:  {"name": "Effect Toggle 2",  "type": "cc", "val": 21},
    23: {"name": "Load Pedalboard A", "type": "pc", "val": 0},
 #   27: {"name": "Load Pedalboard B", "type": "pc", "val": 1},
}

# Track independent toggle states only for the CC pedals
cc_states = {20: False, 21: False}

# 3. Direct Hardware Interrupt Callback Handler
def gpio_callback(chip, gpio, level, tick):
    # level == 0 means switch latched down (Grounded)
    # level == 1 means switch unlatched up (Pulled High)
    is_down = (level == 0)
    cfg = switches_config.get(gpio)
    if not cfg:
        return
        
    msg = None
    
    if cfg["type"] == "cc":
        # Every latching click transition (down or up) toggles the state
        cc_states[cfg["val"]] = not cc_states[cfg["val"]]
        midi_val = 127 if cc_states[cfg["val"]] else 0
        msg = mido.Message('control_change', channel=CC_CHANNEL, control=cfg["val"], value=midi_val)
        status = "ON" if cc_states[cfg["val"]] else "OFF"
        print(f"🎸 {cfg['name']} -> Sent CC {cfg['val']} -> Value: {midi_val} ({status})")
        
    elif cfg["type"] == "pc":
        # Program Changes only execute on the initial downward physical stomp
        if is_down:
            msg = mido.Message('program_change', channel=NAV_CHANNEL, program=cfg["val"])
            print(f"🎛️ {cfg['name']} -> Sent Program Change (PC) {cfg['val']} on Channel {NAV_CHANNEL + 1}")

    # Broadcast the MIDI payload
    if msg:
        midi_out.send(msg)
        if 'midi_connect' in globals() or 'midi_connect' in locals():
            try:
                midi_connect.send(msg)
            except:
                pass

# 4. Initialize the Local GPIO Chip directly
h = lgpio.gpiochip_open(0)

callbacks = []
for pin in switches_config.keys():
    # Bundling PULL_UP inside claim_alert establishes hardware tracking
    lgpio.gpio_claim_alert(h, pin, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP)
    
    # Registering the callback explicitly targeting BOTH_EDGES changes
    cb = lgpio.callback(h, pin, lgpio.BOTH_EDGES, gpio_callback)
    callbacks.append(cb)

print("\n--- Direct LGPIO Guitar Foot Controller Active ---")
print("Pins 5,6 = CC Effects Toggle | Pins 23,27 = PC Pedalboard Switcher")
print("Press Ctrl+C to exit.")

# Safely sleep indefinitely without thread overhead
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down cleanly...")
finally:
    # Always release hardware handles when exiting
    for cb in callbacks:
        cb.cancel()
    lgpio.gpiochip_close(h)

