"""Where everything is saved. All generated files go under output/.

Set OUTPUT_DIR to send them somewhere else, e.g. for simulations:
    OUTPUT_DIR=output/sim python3 trigger.py
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.abspath(os.path.join(ROOT, os.environ.get("OUTPUT_DIR", "output")))

PHOTOS = os.path.join(OUTPUT, "photos")                     # photos/flight_001/shot_1.jpg ...
FLIGHT_LOG = os.path.join(OUTPUT, "flight_log.jsonl")        # one line per shot / arm / disarm
TRIGGER_LOG = os.path.join(OUTPUT, "trigger_output.log")     # what trigger.py printed
TIMING = os.path.join(OUTPUT, "timing_test")                 # tests/timing_test.py results
REDO_FILE = os.path.join(OUTPUT, "redo_waypoints.jsonl")     # lib/redo_list.py

os.makedirs(OUTPUT, exist_ok=True)
