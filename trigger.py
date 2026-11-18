"""
Mapping trigger: takes a photo every TRIGGER_DIST metres while the drone is ARMED.

Runs by itself on boot (see setup/mapping-drone.service) - no Wi-Fi or SSH needed:
  * waits for the flight controller (Cube over USB) and the camera
  * asks the Cube for position + GPS time (works with no ground station connected)
  * only shoots while armed, so no photos while carrying the drone around
  * each power-up gets a new folder output/photos/flight_NNN (the Jetson clock is
    wrong with no internet, so folders are numbered and the GPS time is logged)
"""
from pymavlink import mavutil
from datetime import datetime, timezone
import glob
import json
import os
import math
import time

from lib import paths
from lib.camera import Camera

# ---------- Settings ----------
# Where the flight controller is. Leave MAV_CONNECTION unset to auto-find the Cube on USB.
#   'udp:127.0.0.1:14550'   -> SITL / MAVProxy (desk testing)
#   '/dev/ttyACM0'          -> flight controller over USB
MAV_CONNECTION = os.environ.get("MAV_CONNECTION", "auto")
MAV_BAUD = int(os.environ.get("MAV_BAUD", "115200"))
# Metres between photos. The camera needs ~1.9 s per shot, so the real spacing is
# at least (ground speed x 1.9 s) - e.g. ~34 m at 18 m/s. Pick this from your
# altitude/overlap, not smaller than that.
TRIGGER_DIST = float(os.environ.get("TRIGGER_DIST", "10"))
ONLY_WHEN_ARMED = os.environ.get("ONLY_WHEN_ARMED", "1") != "0"   # set to 0 for bench tests
# Only shoot above this height (m above home) - skips the takeoff roll and landing
MIN_ALT = float(os.environ.get("MIN_ALT", "10"))
POSITION_HZ = 5            # how often to ask the Cube for position
# NO_CAMERA=1: test without a camera - everything runs, shots are only logged.
# NO_CAMERA_DELAY: pretend each shot takes this long (s), like the real camera.
NO_CAMERA = os.environ.get("NO_CAMERA", "0") == "1"
NO_CAMERA_DELAY = float(os.environ.get("NO_CAMERA_DELAY", "0"))

PHOTOS_ROOT = paths.PHOTOS
LOG_PATH = paths.FLIGHT_LOG


def log(text):
    print(text, flush=True)
    try:
        with open(paths.TRIGGER_LOG, "a") as f:     # also keep a copy in output/
            f.write(text + "\n")
    except OSError:
        pass   # never let logging stop the flight script


def next_flight_dir():
    """photos/flight_001, flight_002 ... - never reuses a folder that has photos,
    whatever the clock says. The folder is only created at the first photo, so
    power-ups without a flight don't leave empty folders."""
    os.makedirs(PHOTOS_ROOT, exist_ok=True)
    nums = [int(d[7:]) for d in os.listdir(PHOTOS_ROOT)
            if d.startswith("flight_") and d[7:].isdigit()
            and os.listdir(os.path.join(PHOTOS_ROOT, d))]
    n = max(nums, default=0) + 1
    return f"flight_{n:03d}", os.path.join(PHOTOS_ROOT, f"flight_{n:03d}")


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def find_port():
    if MAV_CONNECTION != "auto":
        return MAV_CONNECTION
    # Cube USB shows up as two serial ports; interface 00 is MAVLink
    for pattern in ("/dev/serial/by-id/*CubePilot*if00", "/dev/serial/by-id/*ArduPilot*if00",
                    "/dev/serial/by-id/*if00", "/dev/ttyACM0", "/dev/ttyACM*"):
        found = sorted(glob.glob(pattern))
        if found:
            return found[0]
    return None


def connect_mavlink():
    while True:
        port = find_port()
        if port is None:
            log("Waiting for flight controller (no USB serial port yet)...")
            time.sleep(3)
            continue
        try:
            mav = mavutil.mavlink_connection(port, baud=MAV_BAUD)
            if mav.wait_heartbeat(timeout=10):
                log(f"Connected to flight controller on {port}")
                return mav
            log(f"No heartbeat on {port} yet...")
            mav.close()
        except Exception as e:
            log(f"Waiting for flight controller on {port} ({e})")
        time.sleep(3)


def request_streams(mav):
    """Ask the Cube to send position and GPS time. Without a ground station
    connected to this port, ArduPilot may not send them otherwise."""
    for msg_id, hz in ((mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT, POSITION_HZ),
                       (mavutil.mavlink.MAVLINK_MSG_ID_SYSTEM_TIME, 1)):
        mav.mav.command_long_send(
            mav.target_system, mav.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            msg_id, int(1e6 / hz), 0, 0, 0, 0, 0)
    # Older firmware: classic stream request as a backup
    mav.mav.request_data_stream_send(mav.target_system, mav.target_component,
                                     mavutil.mavlink.MAV_DATA_STREAM_POSITION, POSITION_HZ, 1)
    mav.mav.request_data_stream_send(mav.target_system, mav.target_component,
                                     mavutil.mavlink.MAV_DATA_STREAM_EXTRA3, 1, 1)


def write_log(log_file, entry):
    log_file.write(json.dumps(entry) + "\n")
    log_file.flush()
    os.fsync(log_file.fileno())   # survive the battery being pulled after landing


def main():
    run_name, photo_dir = next_flight_dir()
    log(f"Saving photos to {photo_dir}  (every {TRIGGER_DIST:g} m, above {MIN_ALT:g} m, "
        f"only when armed: {ONLY_WHEN_ARMED})")
    mav = connect_mavlink()
    request_streams(mav)

    if NO_CAMERA:
        camera = None
        log("NO_CAMERA test mode - shots are logged, no photos taken")
    else:
        camera = Camera(log=log)
        # Don't wait here: if the camera is off/asleep, keep reading the Cube and
        # logging anyway. capture() reconnects by itself when a photo is due.
        if not camera.connect(wait=False):
            log("Camera not found yet - will keep trying at every shot")

    last_lat = last_lon = None
    shot_count = 0
    armed = False
    gps_time = None            # UTC from the Cube's GPS
    last_msg = time.time()
    last_request = time.time()

    with open(LOG_PATH, "a") as log_file:
        while True:
            # Re-ask for streams now and then (the Cube forgets if it reboots)
            if time.time() - last_request > 10:
                request_streams(mav)
                last_request = time.time()

            msg = mav.recv_match(type=['GLOBAL_POSITION_INT', 'HEARTBEAT', 'SYSTEM_TIME'],
                                 blocking=True, timeout=1)
            if not msg:
                if time.time() - last_msg > 15:
                    log("No data from flight controller for 15 s - reconnecting")
                    try:
                        mav.close()
                    except Exception:
                        pass
                    mav = connect_mavlink()
                    request_streams(mav)
                    last_msg = time.time()
                continue
            last_msg = time.time()
            kind = msg.get_type()

            if kind == 'HEARTBEAT':
                # Only the autopilot's heartbeat counts (not a ground station's)
                if msg.get_srcSystem() != mav.target_system or \
                        msg.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                    continue
                now_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                if now_armed != armed:
                    armed = now_armed
                    log("ARMED - photos on" if armed else "DISARMED - photos off")
                    write_log(log_file, {"run": run_name, "event": "armed" if armed else "disarmed",
                                         "gps_time": gps_time})
                    if armed:
                        last_lat = last_lon = None   # first photo right away after arming
                continue

            if kind == 'SYSTEM_TIME':
                if msg.time_unix_usec > 1_600_000_000 * 1_000_000:   # 0 until GPS has time
                    gps_time = datetime.fromtimestamp(msg.time_unix_usec / 1e6,
                                                      timezone.utc).isoformat()
                continue

            # GLOBAL_POSITION_INT
            if ONLY_WHEN_ARMED and not armed:
                continue

            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            alt = msg.relative_alt / 1000

            if lat == 0 and lon == 0:
                continue  # no GPS fix yet

            if alt < MIN_ALT:
                continue  # on the ground / taking off / landing

            if last_lat is not None and haversine(last_lat, last_lon, lat, lon) < TRIGGER_DIST:
                continue

            shot_count += 1
            last_lat, last_lon = lat, lon
            os.makedirs(photo_dir, exist_ok=True)
            base = os.path.join(photo_dir, f"shot_{shot_count}")
            shot_gps_time = gps_time

            t0 = time.perf_counter()
            if camera is None:
                time.sleep(NO_CAMERA_DELAY)
                ok, files, err, attempts = True, [], "no camera (test mode)", 1
            else:
                ok, files, err, attempts = camera.capture(base)
            dt = time.perf_counter() - t0

            if ok:
                log(f"Shot {shot_count} at {lat}, {lon}, {alt}m ({dt:.1f}s)")
            else:
                log(f"Camera error on shot {shot_count} after {attempts} tries: {err}")

            write_log(log_file, {
                "run": run_name,
                "shot": shot_count,
                "file": ",".join(os.path.basename(p) for p in files),
                "ok": ok,
                "error": err,
                "attempts": attempts,
                "seconds": round(dt, 2),
                "gps_time": shot_gps_time,
                "lat": lat,
                "lon": lon,
                "alt": alt,
            })
            os.sync()   # make sure the photo itself is on disk too

            # Throw away GPS messages that piled up while the camera was busy,
            # so the next decision uses the CURRENT position, not an old one.
            while mav.recv_match(type='GLOBAL_POSITION_INT', blocking=False):
                pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nStopped.")
