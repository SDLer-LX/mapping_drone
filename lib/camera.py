"""
Shared camera helper for trigger.py and timing_test.py.

Keeps ONE gphoto2 session open to the camera instead of starting a new
`gphoto2` command for every photo. That is faster (~1.9 s vs ~2.3 s per shot
on the Sony a6000) and avoids the main mid-flight failure mode: a timed-out
`gphoto2` process getting killed halfway through a transfer, which leaves the
camera stuck so the next shots fail too.

On any error it closes the session, reconnects and retries the shot.
Every file the camera produces is saved with its real extension
(.jpg, .arw ...), so a RAW file is never saved as "shot_N.jpg".

Needs the python gphoto2 package (already in ~/venv-drone):
    pip install gphoto2
"""
import os
import subprocess
import time

import gphoto2 as gp

# If the camera is set to RAW or RAW+JPEG, switch it to JPEG only.
# RAW files are ~24 MB and make every shot much slower. Set to None to leave it alone.
FORCE_JPEG_QUALITY = "Fine"     # "Standard" or "Fine"
RETRIES = 2                     # extra attempts per shot after a failure
EVENT_TIMEOUT_MS = 3000         # how long to wait for extra files (RAW+JPEG)


def stop_gvfs():
    """Stop the desktop's camera auto-mount, which grabs the camera."""
    subprocess.run(["pkill", "-f", "gvfs-gphoto2"], capture_output=True)


class Camera:
    def __init__(self, log=print):
        self.log = log
        self.cam = None
        self.reconnects = 0

    # ---------- connection ----------
    def connect(self, wait=True):
        """Open the camera session. With wait=True, keep trying until it works."""
        while True:
            stop_gvfs()
            try:
                cam = gp.Camera()
                cam.init()
                self.cam = cam
                self._check_settings()
                return True
            except gp.GPhoto2Error as e:
                self.cam = None
                if not wait:
                    self.log(f"Camera not available: {e}")
                    return False
                self.log(f"Waiting for camera ({e}) - is it on, USB = PC Remote?")
                time.sleep(2)

    def close(self):
        if self.cam is not None:
            try:
                self.cam.exit()
            except gp.GPhoto2Error:
                pass
        self.cam = None

    def reconnect(self):
        self.reconnects += 1
        self.close()
        time.sleep(1)
        return self.connect(wait=False)

    # ---------- settings ----------
    def _get(self, name):
        try:
            cfg = self.cam.get_config()
            return cfg.get_child_by_name(name).get_value()
        except gp.GPhoto2Error:
            return None

    def _check_settings(self):
        quality = self._get("imagequality")
        if FORCE_JPEG_QUALITY and quality and "RAW" in quality:
            try:
                cfg = self.cam.get_config()
                cfg.get_child_by_name("imagequality").set_value(FORCE_JPEG_QUALITY)
                self.cam.set_config(cfg)
                self.log(f"Camera was set to {quality}; switched to JPEG {FORCE_JPEG_QUALITY}")
                quality = FORCE_JPEG_QUALITY
            except gp.GPhoto2Error as e:
                self.log(f"WARNING: camera is set to {quality} and could not be changed ({e}). "
                         "Set Quality to JPEG on the camera - RAW makes every shot much slower.")
        focus = self._get("focusmode")
        battery = self._get("batterylevel")
        self.log(f"Camera ready: quality={quality}, focus={focus}, battery={battery}")
        if focus and focus != "Manual":
            self.log("  Tip: focus is not Manual. In the air the camera may refuse to fire "
                     "when autofocus can't lock. Use MF focused at infinity for mapping.")

    def battery(self):
        return self._get("batterylevel")

    # ---------- capture ----------
    def _capture_once(self, base_path):
        path = self.cam.capture(gp.GP_CAPTURE_IMAGE)
        files = [self._download(path.folder, path.name, base_path)]
        # RAW+JPEG gives a second file - collect it so it doesn't pile up on the camera
        end = time.time() + EVENT_TIMEOUT_MS / 1000
        while time.time() < end:
            ev, data = self.cam.wait_for_event(100)
            if ev == gp.GP_EVENT_FILE_ADDED:
                files.append(self._download(data.folder, data.name, base_path))
            elif ev in (gp.GP_EVENT_TIMEOUT, gp.GP_EVENT_CAPTURE_COMPLETE):
                break
        return files

    def _download(self, folder, name, base_path):
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        out = base_path + ext
        f = self.cam.file_get(folder, name, gp.GP_FILE_TYPE_NORMAL)
        f.save(out)
        try:
            self.cam.file_delete(folder, name)
        except gp.GPhoto2Error:
            pass  # many cameras (a6000) delete it themselves
        return out

    def capture(self, base_path):
        """Take one photo. base_path has no extension, e.g. photos/run/shot_5

        Returns (ok, files, error_text, attempts).
        """
        err = ""
        for attempt in range(1, RETRIES + 2):
            if self.cam is None and not self.connect(wait=False):
                err = "camera not connected"
                time.sleep(1)
                continue
            try:
                files = self._capture_once(base_path)
                if files and all(os.path.getsize(p) > 0 for p in files):
                    return True, files, "", attempt
                err = "no file saved"
            except gp.GPhoto2Error as e:
                err = str(e)
            self.log(f"  capture attempt {attempt} failed: {err} - reconnecting")
            self.reconnect()
        return False, [], err, RETRIES + 1
