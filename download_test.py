import subprocess
import time
import os

os.makedirs("/home/lillianxu_88/mapping_drone/photos", exist_ok=True)
subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
time.sleep(1)

shot_count = 0

while True:
    input(f"Press Enter to take shot {shot_count + 1} (Ctrl+C to quit)")
    shot_count += 1
    result = subprocess.run(
        ['gphoto2', '--capture-image-and-download', '--force-overwrite',
         '--filename', f'/home/lillianxu_88/mapping_drone/photos/shot_{shot_count}.jpg'],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode == 0:
        print(f"Shot {shot_count} - saved to Pi")
    else:
        print(f"Error: {result.stderr.strip()}")
    time.sleep(3)
