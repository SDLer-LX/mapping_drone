import subprocess
import time
import os

subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
time.sleep(1)

shot_count = 0

while True:
    input(f"Press Enter to take shot {shot_count + 1} (Ctrl+C to quit)")
    shot_count += 1
    result = subprocess.run(
        ['gphoto2', '--capture-image'],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print(f"Shot {shot_count} - taken")
    else:
        print(f"Error: {result.stderr.strip()}")
