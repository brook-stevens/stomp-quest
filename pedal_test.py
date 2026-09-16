import signal
from gpiozero import Button

# Configure GPIO 17 as an input with the internal pull-up resistor enabled.
# Because it uses a pull-up, the Pi expects the pin to drop to Ground (LOW) 
# when the switch is pressed. gpiozero handles this logic automatically.
# 27 works
# 17 does not
# 23 works
# 24 does NOT
# 5 Works
# 6 Works
# 13,15 does NOT
footswitch = Button(3, pull_up=True)

def switch_pressed():
    print("🎸 Footswitch PRESSED! (Signal went LOW / Grounded)")

def switch_released():
    print("🔇 Footswitch RELEASED! (Signal went HIGH / Pull-up)")

# Assign the functions to the switch events
footswitch.when_pressed = switch_pressed
footswitch.when_released = switch_released

print("--- Guitar Pedal Footswitch Test Script ---")
print("Press the footswitch to test the connection. Press Ctrl+C to exit.")

# Keep the script running to listen for events
signal.pause()
