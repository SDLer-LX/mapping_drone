from pymavlink import mavutil
import json

REDO_FILE = "/home/lillianxu_88/mapping_drone/redo_waypoints.jsonl"

def load_redos():
    try:
        with open(REDO_FILE, "r") as f:
            return [json.loads(line) for line in f]
    except FileNotFoundError:
        return []

def upload_mission(mav, waypoints):
    mav.mav.mission_count_send(
        mav.target_system,
        mav.target_component,
        len(waypoints) + 1
    )

    for i in range(len(waypoints) + 1):
        msg = mav.recv_match(type='MISSION_REQUEST_INT', blocking=True, timeout=5)
        if msg is None:
            print("Cube stopped asking for waypoints")
            return False

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
    if msg:
        print("Mission uploaded!")
        return True
    return False

if __name__ == "__main__":
    mav = mavutil.mavlink_connection('/dev/ttyACM0', baud=115200)
    mav.wait_heartbeat()
    print("Connected")

    redos = load_redos()
    if redos:
        print(f"Uploading {len(redos)} waypoints")
        upload_mission(mav, redos)
    else:
        print("No redo waypoints")
