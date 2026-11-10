from pymavlink import mavutil
from datetime import datetime, timezone
import json
import os
import math
import time
import subprocess

# ---------- Settings ----------
# Where the flight controller is:
#   'udp:127.0.0.1:14550'   -> SITL / MAVProxy (desk testing)
#   '/dev/ttyACM0'          -> flight controller over USB
#   '/dev/ttyTHS1'          -> flight controller on Jetson 40-pin UART (check: ls /dev/ttyTHS*)
MAV_CONNECTION = os.environ.get("MAV_CONNECTION", "/dev/ttyACM0")
MAV_BAUD = int(os.environ.get("MAV_BAUD", "115200"))
TRIGGER_DIST = 10  # metres between photos

# Save next to this script, so it works for any username (Pi or Jetson)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_NAME = datetime.now().strftime("%Y%m%d_%H%M%S")
PHOTO_DIR = os.path.join(BASE_DIR, "photos", RUN_NAME)   # new folder every run -> no overwriting
LOG_PATH = os.path.join(BASE_DIR, "flight_log.jsonl")
os.makedirs(PHOTO_DIR, exist_ok=True)


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def connect_mavlink():
    while True:
        try:
            mav = mavutil.mavlink_connection(MAV_CONNECTION, baud=MAV_BAUD)
            if mav.wait_heartbeat(timeout=10):
                print(f"Connected to flight controller on {MAV_CONNECTION}", flush=True)
                return mav
            print("No heartbeat yet...", flush=True)
        except Exception as e:
            print(f"Waiting for flight controller ({e})", flush=True)
        time.sleep(5)


def main():
    print(f"Saving photos to {PHOTO_DIR}", flush=True)
    mav = connect_mavlink()

    # Stop the desktop from grabbing the camera
    subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
    time.sleep(1)

    last_lat = None
    last_lon = None
    shot_count = 0

    with open(LOG_PATH, "a") as log_file:
        while True:
            msg = mav.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1)
            if not msg:
                continue

            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            alt = msg.relative_alt / 1000

            if lat == 0 and lon == 0:
                continue  # no GPS fix yet

            if last_lat is not None and haversine(last_lat, last_lon, lat, lon) < TRIGGER_DIST:
                continue

            shot_count += 1
            last_lat, last_lon = lat, lon
            filename = os.path.join(PHOTO_DIR, f"shot_{shot_count}.jpg")
            shot_time = datetime.now(timezone.utc).isoformat()

            try:
                result = subprocess.run(
                    ['gphoto2', '--capture-image-and-download', '--force-overwrite',
                     '--filename', filename],
                    capture_output=True, text=True, timeout=60
                )
                ok = result.returncode == 0
                err = "" if ok else result.stderr.strip()
            except subprocess.TimeoutExpired:
                ok, err = False, "timeout"

            if ok:
                print(f"Shot {shot_count} at {lat}, {lon}, {alt}m", flush=True)
            else:
                print(f"Camera error on shot {shot_count}: {err}", flush=True)

            entry = {
                "run": RUN_NAME,
                "shot": shot_count,
                "file": os.path.basename(filename),
                "ok": ok,
                "time": shot_time,
                "lat": lat,
                "lon": lon,
                "alt": alt,
            }
            log_file.write(json.dumps(entry) + "\n")
            log_file.flush()

            # Throw away GPS messages that piled up while the camera was busy,
            # so the next decision uses the CURRENT position, not an old one.
            while mav.recv_match(type='GLOBAL_POSITION_INT', blocking=False):
                pass


if __name__ == "__main__":
    main()