import time
import os
import subprocess

try:
    import gphoto2 as gp
    HAS_GPHOTO = True
except:
    HAS_GPHOTO = False

os.makedirs("/home/lillianxu_88/mapping_drone/photos", exist_ok=True)

subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
time.sleep(1)

camera = gp.Camera()
camera.init()
print("Camera connected")

shot_count = 0

while True:
    input(f"Press Enter to take shot {shot_count + 1} (Ctrl+C to quit)")
    shot_count += 1
    try:
        file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
        time.sleep(2)
        target = camera.file_get(file_path.folder, file_path.name, gp.GP_FILE_TYPE_NORMAL)
        target.save(f"/home/lillianxu_88/mapping_drone/photos/shot_{shot_count}.jpg")
        print(f"Shot {shot_count}: {file_path.name} - saved")
    except Exception as e:
        print(f"Camera error: {e} - reconnecting...")
        time.sleep(2)
        try:
            camera.exit()
        except:
            pass
        try:
            camera = gp.Camera()
            camera.init()
            print("Camera reconnected")
        except:
            print("Reconnect failed")
