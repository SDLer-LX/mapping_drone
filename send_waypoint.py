
def send_waypoint(mav, lat, lon, alt):
    """New Waypoint to be planned"""
    mav.mav.mission_item_int_send(
        mav.target_system,
        mav.target_component,
        0,  # sequence
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
        2,  # current = 2 means guided mode target
        1,  # autocontinue
        0, 0, 0, 0,  # params (unused for waypoint)
        int(lat * 1e7),
        int(lon * 1e7),
        alt
    )
    print(f"Sent waypoint: {lat}, {lon}, {alt}m")

def set_mode(mav, mode_name):
    """Change flight mode"""
    mode_id = mav.mode_mapping()[mode_name]
    mav.set_mode(mode_id)
    print(f"Mode set to {mode_name}")

