import time, os
import gphoto2 as gp

cam = gp.Camera()
cam.init()

N = 10
for i in range(N):
    t0 = time.perf_counter()
    path = cam.capture(gp.GP_CAPTURE_IMAGE)          # trigger + wait until camera has the file
    t1 = time.perf_counter()
    f = cam.file_get(path.folder, path.name, gp.GP_FILE_TYPE_NORMAL)  # camera -> Jetson
    t2 = time.perf_counter()
    out = f"timing_{i}.jpg"
    f.save(out)                                      # write to SSD
    t3 = time.perf_counter()

    mb = os.path.getsize(out) / 1e6
    print(f"{i}: capture {t1-t0:.2f}s | download {t2-t1:.2f}s "
          f"({mb/(t2-t1):.1f} MB/s) | save {t3-t2:.2f}s | "
          f"TOTAL {t3-t0:.2f}s | {mb:.1f} MB")

cam.exit()