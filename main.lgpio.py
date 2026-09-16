import signal
import mido
import time
import lgpio
import subprocess

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

# 2. Map Pins to their configuration definitions
switches_config = {
    5:  {"name": "Effect Toggle 1",  "type": "cc",   "val": 20},
    6:  {"name": "Effect Toggle 2",  "type": "cc",   "val": 21},
    23: {"name": "Next Pedalboard",  "type": "cmd",  "val": "/usr/modep/scripts/next_pedalboard.sh"},
    27: {"name": "Prev Pedalboard",  "type": "cmd",  "val": "/usr/modep/scripts/prev_pedalboard.sh"},
}

# Track independent toggle states only for the CC pedals
cc_states = {20: False, 21: False}

# Track standard Unix timestamps to accurately drop contact bouncing (use current time as on startup we 
# sometimes get a signal we want to ignore)
now = time.time()
last_press_time = {5: now, 6: now, 23: now, 27: now}
DEBOUNCE_TIME = 0.300  # 300 milliseconds window to completely block duplicate clicks

# 3. Direct Hardware Interrupt Callback Handler
def gpio_callback(chip, gpio, level, tick):
    print("um")
    cfg = switches_config.get(gpio)
    if not cfg:
        return
        
    current_time = time.time()
    
    if cfg["type"] == "cc":
        # Debounce the latching switch to filter erratic line triggers
        if (current_time - last_press_time[gpio]) < DEBOUNCE_TIME:
            return
        last_press_time[gpio] = current_time

        cc_states[cfg["val"]] = not cc_states[cfg["val"]]
        midi_val = 127 if cc_states[cfg["val"]] else 0
        msg = mido.Message('control_change', channel=CC_CHANNEL, control=cfg["val"], value=midi_val)
        
        midi_out.send(msg)
        if 'midi_connect' in globals() or 'midi_connect' in locals():
            try: midi_connect.send(msg)
            except: pass
            
        status = "ON" if cc_states[cfg["val"]] else "OFF"
        print(f"🎸 {cfg['name']} Pressed/Released! Sent CC {cfg['val']} -> Value: {midi_val} ({status})")
        
    elif cfg["type"] == "cmd":
        # Check the debounce window solely for real down-clicks
        if (current_time - last_press_time[gpio]) < DEBOUNCE_TIME:
            return  
            
        last_press_time[gpio] = current_time
        print(f"🎛️ {cfg['name']} Stomped Down! Running Script: {cfg['val']}")
        try:
            subprocess.Popen(["/bin/bash", cfg["val"]])
        except Exception as e:
            print(f"❌ Shell Script invocation failed: {e}")

# 4. Initialize the Local GPIO Chip completely
h = lgpio.gpiochip_open(0)
CC_CHANNEL = 0
callbacks = []

for pin in switches_config.keys():
    try:
        print(f"Appending gpio callbacks {pin}")
        while 0!=lgpio.gpio_claim_alert(h, pin, lgpio.BOTH_EDGES, lgpio.SET_PULL_UP):
            print("Failed claiming gpio retrying in 1 second")
            time.sleep(1)

        print("Setting dbounce")
        lgpio.gpio_set_debounce_micros(h, pin, 30000)
        print("take 2")
       
        cb = lgpio.callback(h, pin, lgpio.BOTH_EDGES, gpio_callback)
        print("take 3")
        callbacks.append(cb)
        time.sleep(1)
    except Exception as initialization_error:
        print(f"❌ Critical Alert: Failed to register hook on Pin {pin}: {initialization_error}")

print("\n--- Debounced LGPIO Guitar Foot Controller Active ---")
print("Pins 5,6 = CC Effects Toggle | Pins 23,27 = modep-ctrl Shell Scripts")
print("Press Ctrl+C to exit.")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down cleanly...")
finally:
    for cb in callbacks:
        cb.cancel()
    lgpio.gpiochip_close(h)

