import json

REDO_FILE = "/home/lillianxu_88/mapping_drone/redo_waypoints.jsonl"

def save_redo(lat, lon, alt, reason=""):
    entry = {"lat": lat, "lon": lon, "alt": alt, "reason": reason}
    with open(REDO_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
        f.flush()
    print(f"Redo saved: {lat}, {lon} - {reason}")

def load_redos():
    try:
        with open(REDO_FILE, "r") as f:
            return [json.loads(line) for line in f]
    except FileNotFoundError:
        return []

def clear_redos():
    open(REDO_FILE, "w").close()
