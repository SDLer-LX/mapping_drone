import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # so lib/ and trigger.py can be imported
from pymavlink import mavutil
import os

from lib.redo_list import load_redos

# Same settings as trigger.py
MAV_CONNECTION = os.environ.get("MAV_CONNECTION", "/dev/ttyACM0")
MAV_BAUD = int(os.environ.get("MAV_BAUD", "115200"))

def upload_mission(mav, waypoints):
    mav.mav.mission_count_send(
        mav.target_system,
        mav.target_component,
        len(waypoints) + 1
    )

    for _ in range(len(waypoints) + 1):
        # ArduPilot can ask with either message type; answer the item it asks for
        msg = mav.recv_match(type=['MISSION_REQUEST_INT', 'MISSION_REQUEST'], blocking=True, timeout=5)
        if msg is None:
            print("Cube stopped asking for waypoints")
            return False
        i = msg.seq

        if i == 0:
            wp = waypoints[0]
            current = 1
        else:
            wp = waypoints[i - 1]
            current = 0

        mav.mav.mission_item_int_send(
            mav.target_system,
            mav.target_component,
            i,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            current, 1,
            0, 0, 0, 0,
            int(wp['lat'] * 1e7),
            int(wp['lon'] * 1e7),
            wp['alt']
        )
        print(f"Sent waypoint {i}: {wp['lat']}, {wp['lon']}")

    msg = mav.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
    if msg and msg.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
        print("Mission uploaded!")
        return True
    print(f"Mission upload failed: {msg}")
    return False

if __name__ == "__main__":
    mav = mavutil.mavlink_connection(MAV_CONNECTION, baud=MAV_BAUD)
    mav.wait_heartbeat()
    print("Connected")

    redos = load_redos()
    if redos:
        print(f"Uploading {len(redos)} waypoints")
        upload_mission(mav, redos)
    else:
        print("No redo waypoints")
