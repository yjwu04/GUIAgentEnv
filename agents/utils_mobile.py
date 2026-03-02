import os
import subprocess
def get_screenshot(img_path, adb_path):
    os.makedirs(os.path.dirname(img_path), exist_ok=True)
    with open(img_path, "wb") as f:
        subprocess.run([adb_path, "exec-out", "screencap", "-p"], stdout=f)