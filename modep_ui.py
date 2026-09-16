import os
import time
import subprocess
from PIL import Image, ImageDraw, ImageFont

COLOR_MODE = "BGR;16"
MODEP_STATE_FILE = "/var/modep/last_pedalboard.txt"
MODEP_CTRL_PRIMARY = "/usr/local/pisound/scripts/pisound-btn/modep-ctrl.py"
MODEP_CTRL_FALLBACK = "/usr/modep/scripts/modep-ctrl.py"

try:
    font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    font_stats = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
except IOError:
    font_title = font_body = font_stats = ImageFont.load_default()

while True:
    print("Starting loop")
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

    # Screen Canvas Draw Execution Block
    img = Image.new('RGB', (320, 240), color='black')
    canvas = ImageDraw.Draw(img)

    canvas.text((20, 20), "ACTIVE PEDALBOARD:", fill='yellow', font=font_title)
    
    # Render the clean text string safely
    display_text = pb_name.strip() if pb_name else "No Patch Loaded"
    canvas.text((20, 70), display_text[:22], fill='white', font=font_body)
    
    # Fetch system performance metrics
    cpu_load = os.getloadavg()[0] * 10
    canvas.text((20, 190), f"CPU LOAD: {cpu_load:.1f}%", fill='green', font=font_stats)

    try:
        raw_bytes = img.convert(COLOR_MODE).tobytes()
        with open('/dev/fb0', 'wb') as f:
            bytes_written = f.write(raw_bytes)
        print("wrote bytes to screen")
        if bytes_written == len(raw_bytes):
            print(f"Success! Successfully wrote all {bytes_written} bytes.")
        else:
           print(f"Warning: Data mismatch. Wrote {bytes_written} out of {len(raw_bytes)} bytes.")
    except IOError as e:
        print(f"Framebuffer write block: {e}")

    time.sleep(1)

