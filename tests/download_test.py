import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # so lib/ and trigger.py can be imported
import os

from lib import paths
from lib.camera import Camera

PHOTO_DIR = os.path.join(paths.OUTPUT, "download_test")
os.makedirs(PHOTO_DIR, exist_ok=True)

camera = Camera()
camera.connect()

shot_count = 0

try:
    while True:
        input(f"Press Enter to take shot {shot_count + 1} (Ctrl+C to quit)")
        shot_count += 1
        ok, files, err, _ = camera.capture(os.path.join(PHOTO_DIR, f"shot_{shot_count}"))
        if ok:
            print(f"Shot {shot_count} - saved {', '.join(files)}")
        else:
            print(f"Error: {err}")
except KeyboardInterrupt:
    pass
finally:
    camera.close()
