import os
import json
import time
import subprocess
from PIL import Image, ImageDraw, ImageFont

COLOR_MODE = "BGR;16"
MODEP_STATE_FILE = "/var/modep/last_pedalboard.txt"
MODEP_CTRL_PRIMARY = "/usr/local/pisound/scripts/pisound-btn/modep-ctrl.py"
MODEP_CTRL_FALLBACK = "/usr/modep/scripts/modep-ctrl.py"
FEEDBACK_FILE = "/var/modep/button_feedback.json"
FRAME_INTERVAL = 0.1
FEEDBACK_DURATION = 2.0
FRAMEBUFFER = "/dev/fb0"

try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    font_stats = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except IOError:
    font_title = font_body = font_stats = ImageFont.load_default()


def read_feedback(feedback_file=FEEDBACK_FILE, now=None, duration=FEEDBACK_DURATION):
    """Return the latest feedback message while it is still fresh."""
    try:
        with open(feedback_file, "r") as feedback_handle:
            feedback = json.load(feedback_handle)
        timestamp = float(feedback["timestamp"])
        message = str(feedback["message"]).strip()
        current_time = time.time() if now is None else now
        if message and 0 <= current_time - timestamp < duration:
            return message
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return None


def _to_bgr565_bytes(img):
    pixels = bytearray()
    rgb_bytes = img.tobytes()
    for offset in range(0, len(rgb_bytes), 3):
        red, green, blue = rgb_bytes[offset:offset + 3]
        value = (blue >> 3) << 11 | (green >> 2) << 5 | (red >> 3)
        pixels.extend(value.to_bytes(2, "little"))
    return bytes(pixels)


def render_frame(pb_name, cpu_load, feedback=None):
    """Render the current pedalboard and optional button feedback."""
    img = Image.new("RGB", (320, 240), color="black")
    canvas = ImageDraw.Draw(img)
    canvas.text((20, 20), "ACTIVE PEDALBOARD:", fill="yellow", font=font_title)
    display_text = pb_name.strip() if pb_name else "No Patch Loaded"
    canvas.text((20, 70), display_text[:22], fill="white", font=font_body)
    canvas.text((20, 190), f"CPU LOAD: {cpu_load:.1f}%", fill="green", font=font_stats)
    if feedback:
        canvas.rectangle((0, 215, 320, 240), fill="blue")
        canvas.text((10, 218), feedback[:38], fill="white", font=font_stats)
    return _to_bgr565_bytes(img)


def write_frame(frame_bytes, framebuffer=FRAMEBUFFER, previous_bytes=None):
    """Write changed frame bytes and return them as the new cache value."""
    if frame_bytes == previous_bytes:
        return previous_bytes
    try:
        with open(framebuffer, "wb") as framebuffer_handle:
            bytes_written = framebuffer_handle.write(frame_bytes)
        if bytes_written != len(frame_bytes):
            print(f"Warning: Data mismatch. Wrote {bytes_written} out of {len(frame_bytes)} bytes.")
        return frame_bytes
    except IOError as error:
        print(f"Framebuffer write block: {error}")
        return previous_bytes


def read_pedalboard_name():
    pb_name = "Connecting to MODEP..."
    raw_output = ""

    # Method 1: Check the internal state tracking log file if it exists
    if os.path.exists(MODEP_STATE_FILE):
        try:
            with open(MODEP_STATE_FILE, 'r') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
                if lines:
                    raw_output = lines[0]
        except Exception:
            pass

    # Method 2: Fallback query via the absolute modep-ctrl binary utility
    if not raw_output:
        cmd_tool = MODEP_CTRL_PRIMARY if os.path.exists(MODEP_CTRL_PRIMARY) else MODEP_CTRL_FALLBACK
        if os.path.exists(cmd_tool):
            try:
                cmd = f"python3 {cmd_tool} current"
                output = subprocess.check_output(cmd, shell=True, text=True)
                if output.strip():
                    raw_output = output.strip()
            except Exception:
                pass

    # =====================================================================
    # BULLETPROOF SCRUBBING BLOCK
    # No matter which method grabbed the text, strip the path and file type extensions here:
    # =====================================================================
    if raw_output:
        # Extracts just 'MyPreset.pedalboard' out of the full path string
        filename = os.path.basename(raw_output)
        # Strips out the extension to leave just 'MyPreset'
        pb_name = filename.replace('.pedalboard', '')
    else:
        pb_name = "No Board Active"
    # =====================================================================

    return pb_name


def main():
    previous_frame = None
    while True:
        pb_name = read_pedalboard_name()
        cpu_load = os.getloadavg()[0] * 10
        feedback = read_feedback()
        frame = render_frame(pb_name, cpu_load, feedback)
        previous_frame = write_frame(frame, previous_bytes=previous_frame)
        time.sleep(FRAME_INTERVAL)


if __name__ == "__main__":
    main()

