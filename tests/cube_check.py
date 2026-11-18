"""
Quick read-only check of the Cube connection, using the SAME code as trigger.py.
Shows whether the Cube sends what trigger.py needs, with no ground station connected.

Run (the auto-start service must be stopped first, it holds the port):
    sudo systemctl stop mapping-drone
    ~/venv-drone/bin/python tests/cube_check.py    # 20 s
    sudo systemctl start mapping-drone
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # so lib/ and trigger.py can be imported
import sys
import time
from datetime import datetime, timezone

from pymavlink import mavutil

import trigger   # uses the same connection code as the real flight script

SECS = float(sys.argv[1]) if len(sys.argv) > 1 else 20
FIX = {0: "no GPS", 1: "no fix", 2: "2D", 3: "3D", 4: "DGPS", 5: "RTK float", 6: "RTK fixed"}

mav = trigger.connect_mavlink()
trigger.request_streams(mav)
print(f"Listening {SECS:.0f} s ...", flush=True)

counts = {}
last = {}
end = time.time() + SECS
while time.time() < end:
    m = mav.recv_match(blocking=True, timeout=1)
    if not m:
        continue
    t = m.get_type()
    counts[t] = counts.get(t, 0) + 1
    last[t] = m

print()
hb = last.get("HEARTBEAT")
if hb:
    armed = bool(hb.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
    print(f"HEARTBEAT          OK   mode {mavutil.mode_string_v10(hb)}, armed: {armed}")
else:
    print("HEARTBEAT          MISSING")

n = counts.get("GLOBAL_POSITION_INT", 0)
p = last.get("GLOBAL_POSITION_INT")
print(f"GLOBAL_POSITION_INT {'OK  ' if n else 'MISSING'} {n / SECS:.1f}/s"
      + (f"   lat {p.lat/1e7:.7f} lon {p.lon/1e7:.7f} alt {p.relative_alt/1000:.1f} m" if p else ""))
if p and p.lat == 0 and p.lon == 0:
    print("                         (0,0 = no GPS fix yet - trigger.py waits for a fix)")

st = last.get("SYSTEM_TIME")
if st and st.time_unix_usec > 1_600_000_000 * 1_000_000:
    print(f"SYSTEM_TIME        OK   GPS time {datetime.fromtimestamp(st.time_unix_usec/1e6, timezone.utc)}")
elif st:
    print("SYSTEM_TIME        received, but no GPS time yet (needs a GPS fix)")
else:
    print("SYSTEM_TIME        MISSING")

g = last.get("GPS_RAW_INT")
if g:
    print(f"GPS                {FIX.get(g.fix_type, g.fix_type)}, {g.satellites_visible} satellites")

s = last.get("SYS_STATUS")
if s:
    print(f"Battery            {s.voltage_battery/1000:.2f} V")

msgs = [t for t in last if t.startswith("STATUSTEXT")]
for t in msgs:
    print(f"Cube says: {last[t].text}")
print("\nAll message types seen:", ", ".join(f"{k}({v})" for k, v in sorted(counts.items())))
