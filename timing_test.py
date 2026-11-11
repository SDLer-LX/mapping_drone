"""
Camera speed test - uses the SAME method as trigger.py
(one `gphoto2 --capture-image-and-download` command per photo).

Takes N photos back-to-back, times each one, and prints a summary
plus the fastest the drone can fly for a given trigger distance.

Run:
    cd ~/mapping_drone
    python3 timing_test.py            # 10 shots (default)
    python3 timing_test.py 20         # 20 shots
"""
import os
import subprocess
import sys
import time
from datetime import datetime

N_SHOTS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
TRIGGER_DIST = 10      # metres between photos (same as trigger.py)
TIMEOUT = 60           # seconds before a shot counts as failed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_NAME = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = os.path.join(BASE_DIR, "timing_test", RUN_NAME)
RESULTS_FILE = os.path.join(OUT_DIR, "timing_results.txt")
os.makedirs(OUT_DIR, exist_ok=True)

lines = []


def log(text=""):
    print(text, flush=True)
    lines.append(text)


# Stop the desktop from grabbing the camera
subprocess.run(["pkill", "-f", "gvfs-gphoto2"], capture_output=True)
time.sleep(1)

log(f"Camera speed test - {N_SHOTS} shots, saving to {OUT_DIR}")
log("-" * 60)

times = []
sizes = []
failures = 0
test_start = time.perf_counter()

for i in range(1, N_SHOTS + 1):
    filename = os.path.join(OUT_DIR, f"shot_{i}.jpg")
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            ["gphoto2", "--capture-image-and-download", "--force-overwrite",
             "--filename", filename],
            capture_output=True, text=True, timeout=TIMEOUT,
        )
        ok = result.returncode == 0 and os.path.exists(filename)
        err = "" if ok else (result.stderr.strip() or "no file saved")
    except subprocess.TimeoutExpired:
        ok, err = False, f"timed out after {TIMEOUT}s"
    dt = time.perf_counter() - t0

    if ok:
        mb = os.path.getsize(filename) / 1e6
        times.append(dt)
        sizes.append(mb)
        log(f"Shot {i:2d}: {dt:5.2f} s   {mb:4.1f} MB")
    else:
        failures += 1
        log(f"Shot {i:2d}: FAILED after {dt:.2f} s -> {err.splitlines()[-1] if err else ''}")

total = time.perf_counter() - test_start

log("-" * 60)
log(f"Success: {len(times)}/{N_SHOTS}   Failed: {failures}")
log(f"Total test time: {total:.1f} s")

if times:
    # Ignore the first shot for the "typical" numbers - the camera is waking up
    steady = times[1:] if len(times) > 1 else times
    avg = sum(steady) / len(steady)
    log(f"Time per photo (excluding first): avg {avg:.2f} s | "
        f"min {min(steady):.2f} s | max {max(steady):.2f} s")
    log(f"First shot: {times[0]:.2f} s")
    log(f"Average file size: {sum(sizes)/len(sizes):.1f} MB")
    log()
    log(f"With a photo every {TRIGGER_DIST} m:")
    log(f"  Max flight speed (average case): {TRIGGER_DIST/avg:.1f} m/s")
    log(f"  Safe flight speed (slowest shot): {TRIGGER_DIST/max(steady):.1f} m/s")
else:
    log("No successful shots - check camera is on, USB Connection = PC Remote, focus = MF.")

with open(RESULTS_FILE, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nResults saved to {RESULTS_FILE}")