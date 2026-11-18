"""
Fake Cube: plays a whole plane flight over MAVLink so trigger.py can be tested
indoors, with no GPS, RC or flying. trigger.py can't tell it from the real Cube.

Flight: on the ground (disarmed) -> armed on the ground -> takeoff roll + climb
-> straight survey leg at cruise height -> descend + land -> disarmed.

Run in two terminals on the Jetson, from ~/mapping_drone (see README.md):
    ~/venv-drone/bin/python tests/fake_cube.py --speed 18          # terminal 1
    OUTPUT_DIR=output/sim MAV_CONNECTION=udpin:127.0.0.1:14560 ~/venv-drone/bin/python trigger.py   # terminal 2

Options:
    --speed 18      ground speed m/s (plane cruise)
    --alt 80        survey height m
    --leg 600       survey leg length m
    --dropout 10    go silent for 10 s mid-leg (tests reconnect)
"""
import argparse
import math
import time

from pymavlink import mavutil

ap = argparse.ArgumentParser()
ap.add_argument("--speed", type=float, default=18)
ap.add_argument("--alt", type=float, default=80)
ap.add_argument("--leg", type=float, default=600)
ap.add_argument("--dropout", type=float, default=0)
ap.add_argument("--out", default="udpout:127.0.0.1:14560")
args = ap.parse_args()

mav = mavutil.mavlink_connection(args.out, source_system=1, source_component=1)
M = mavutil.mavlink

HOME_LAT, HOME_LON = 38.6488, -90.3108       # any point works
CLIMB = 3.0                                   # m/s
GPS_EPOCH = time.time() if time.time() > 1.6e9 else 1_794_960_000   # fake GPS clock

# (name, seconds, armed)
climb_s = args.alt / CLIMB
phases = [("ground, disarmed", 5, False),
          ("armed on ground", 5, True),
          ("takeoff + climb", climb_s, True),
          ("survey leg", args.leg / args.speed, True),
          ("descend + land", climb_s, True),
          ("landed, armed", 3, True),
          ("disarmed", 5, False)]

start = time.time()
dist = 0.0       # metres flown north from home
alt = 0.0
last = time.time()
t_boot = 0
print("Fake Cube sending on", args.out)
for name, secs, armed in phases:
    print(f"--> {name} ({secs:.0f} s)", flush=True)
    end = time.time() + secs
    leg_mid = time.time() + secs / 2
    dropped = False
    hb_next = 0
    while time.time() < end:
        now = time.time()
        dt, last = now - last, now
        if name in ("takeoff + climb", "survey leg", "descend + land"):
            dist += args.speed * dt
        if name == "takeoff + climb":
            alt = min(args.alt, alt + CLIMB * dt)
        elif name == "descend + land":
            alt = max(0.0, alt - CLIMB * dt)

        if args.dropout and name == "survey leg" and not dropped and now > leg_mid:
            print(f"    (silent for {args.dropout:.0f} s)", flush=True)
            time.sleep(args.dropout)
            dropped = True
            last = time.time()
            continue

        t_boot = int((now - start) * 1000)
        lat = HOME_LAT + dist / 111_320
        if now >= hb_next:
            base = M.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | (M.MAV_MODE_FLAG_SAFETY_ARMED if armed else 0)
            mav.mav.heartbeat_send(M.MAV_TYPE_FIXED_WING, M.MAV_AUTOPILOT_ARDUPILOTMEGA,
                                   base, 10 if armed else 0, M.MAV_STATE_ACTIVE)
            mav.mav.system_time_send(int((GPS_EPOCH + now - start) * 1e6), t_boot)
            hb_next = now + 1
        mav.mav.global_position_int_send(t_boot, int(lat * 1e7), int(HOME_LON * 1e7),
                                         int((150 + alt) * 1000), int(alt * 1000),
                                         int(args.speed * 100), 0, 0, 0)
        time.sleep(0.2)   # 5 Hz, like the real Cube

print(f"Done. Flew {dist:.0f} m. Survey leg {args.leg:.0f} m at {args.alt:.0f} m.")
