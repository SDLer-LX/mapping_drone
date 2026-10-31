from pymavlink import mavutil
from datetime import datetime
import json
import os
import math
import time
import subprocess

try:
    import gphoto2 as gp
    HAS_GPHOTO = True
except:
    HAS_GPHOTO = False

os.makedirs("/home/lillianxu_88/mapping_drone/photos", exist_ok=True)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def connect_camera():
    if not HAS_GPHOTO:
        print("gphoto2 not available - camera disabled")
        return None
    try:
        subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
        time.sleep(1)
        camera = gp.Camera()
        camera.init()
        print("Camera connected")
        return camera
    except:
        print("No camera found - running without camera")
        return None

def main():
    #mav = mavutil.mavlink_connection('udp:127.0.0.1:14550')
    # USB (desk testing):
    while True:
        try:
            #mav = mavutil.mavlink_connection('/dev/ttyACM0', baud=115200)
            mav = mavutil.mavlink_connection('udp:127.0.0.1:14550')
            mav.wait_heartbeat()
            print("Connected to flight controller")
            break
        except:
            print("Waiting for flight controller...")
            time.sleep(5)

    subprocess.run(['pkill', '-f', 'gvfs-gphoto2'], capture_output=True)
    time.sleep(1)

    TRIGGER_DIST = 10
    last_lat = None
    last_lon = None

    shot_count = 0
    log_file = open("/home/lillianxu_88/mapping_drone/flight_log.jsonl", "a")

    while True:
        msg = mav.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=1)
        if msg:
            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            alt = msg.relative_alt / 1000

            if lat == 0 and lon == 0:
                continue

            should_trigger = False
            if last_lat is None:
                should_trigger = True
            elif haversine(last_lat, last_lon, lat, lon) >= TRIGGER_DIST:
                should_trigger = True

            if should_trigger:
                shot_count += 1
                last_lat = lat
                last_lon = lon
                print(f"Should take photo {shot_count}")
                result = subprocess.run(
                     ['gphoto2', '--capture-image-and-download', '--force-overwrite',
                     '--filename', f'/home/lillianxu_88/mapping_drone/photos/shot_{shot_count}.jpg'],
                     capture_output=True, text=True, timeout=60
                      )
#                result = subprocess.run( ['gphoto2', '--capture-image'],
 #                   capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"Shot {shot_count} at {lat}, {lon}, {alt}m")
                else:
                    print(f"Camera error: {result.stderr.strip()}")

                entry = {
                    "shot": shot_count,
                    "time": datetime.utcnow().isoformat(),
                    "lat": lat,
                    "lon": lon,
                    "alt": alt                }
                log_file.write(json.dumps(entry) + "\n")
                log_file.flush()

if __name__ == "__main__":
    main()

