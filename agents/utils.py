import os
import subprocess

def get_screenshot(img_path):
    # os.makedirs(os.path.dirname(img_path), exist_ok=True)
    # img = pyautogui.screenshot()
    # img.save(img_path)
    os.makedirs(os.path.dirname(img_path), exist_ok=True)
    subprocess.run([
        "import",
        "-display", os.environ.get("DISPLAY", ":99"),
        "-window", "root",
        img_path
    ], check = True)
    return