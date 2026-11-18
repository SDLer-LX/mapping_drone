"""
Camera speed test - uses the SAME camera code as trigger.py (camera.py).

Takes N photos back-to-back, times each one, and prints a summary
plus the fastest the drone can fly for a given trigger distance.
Results are written to the file after EVERY shot, so a crash or Ctrl+C
still leaves a results file.

Run:
    cd ~/mapping_drone
    python3 tests/timing_test.py            # 10 shots (default)
    python3 tests/timing_test.py 20         # 20 shots
    python3 tests/timing_test.py 20 2.5     # 20 shots, one every 2.5 s (like flying)
"""
import os, sys; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # so lib/ and trigger.py can be imported
import os
import sys
import time
from datetime import datetime

from lib import paths
from lib.camera import Camera

N_SHOTS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
INTERVAL = float(sys.argv[2]) if len(sys.argv) > 2 else 0   # 0 = back-to-back
TRIGGER_DIST = 10      # metres between photos (same as trigger.py)

RUN_NAME = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = os.path.join(paths.TIMING, RUN_NAME)
RESULTS_FILE = os.path.join(OUT_DIR, "timing_results.txt")
os.makedirs(OUT_DIR, exist_ok=True)

results_f = open(RESULTS_FILE, "w")


def log(text=""):
    print(text, flush=True)
    results_f.write(text + "\n")
    results_f.flush()


def summary(times, sizes, failures, retried, attempted, total, camera):
    log("-" * 60)
    log(f"Success: {len(times)}/{attempted}   Failed: {failures}   "
        f"Needed a retry: {retried}   Reconnects: {camera.reconnects}")
    log(f"Total test time: {total:.1f} s")
    if not times:
        log("No successful shots - check camera is on, USB Connection = PC Remote, focus = MF.")
        return
    # Ignore the first shot for the "typical" numbers - the camera is waking up
    steady = times[1:] if len(times) > 1 else times
    avg = sum(steady) / len(steady)
    log(f"Time per photo (excluding first): avg {avg:.2f} s | "
        f"min {min(steady):.2f} s | max {max(steady):.2f} s")
    log(f"First shot: {times[0]:.2f} s")
    log(f"Average file size: {sum(sizes)/len(sizes):.1f} MB")
    log(f"Camera battery: {camera.battery()}")
    log()
    log(f"With a photo every {TRIGGER_DIST} m:")
    log(f"  Max flight speed (average case): {TRIGGER_DIST/avg:.1f} m/s")
    log(f"  Safe flight speed (slowest shot): {TRIGGER_DIST/max(steady):.1f} m/s")


def main():
    camera = Camera(log=log)
    log(f"Camera speed test - {N_SHOTS} shots"
        + (f", one every {INTERVAL:.1f} s" if INTERVAL else ", back-to-back")
        + f", saving to {OUT_DIR}")
    camera.connect()
    log("-" * 60)

    times, sizes = [], []
    failures = retried = attempted = 0
    test_start = time.perf_counter()
    try:
        for i in range(1, N_SHOTS + 1):
            attempted = i
            t0 = time.perf_counter()
            ok, files, err, attempts = camera.capture(os.path.join(OUT_DIR, f"shot_{i}"))
            dt = time.perf_counter() - t0
            if attempts > 1:
                retried += 1
            if ok:
                mb = sum(os.path.getsize(p) for p in files) / 1e6
                times.append(dt)
                sizes.append(mb)
                names = ", ".join(os.path.basename(p) for p in files)
                note = f"  (attempt {attempts})" if attempts > 1 else ""
                log(f"Shot {i:2d}: {dt:5.2f} s   {mb:4.1f} MB   {names}{note}")
            else:
                failures += 1
                log(f"Shot {i:2d}: FAILED after {dt:.2f} s, {attempts} tries -> {err}")
            if INTERVAL and i < N_SHOTS:
                time.sleep(max(0, INTERVAL - dt))
    except KeyboardInterrupt:
        log("\nStopped early (Ctrl+C).")
    finally:
        summary(times, sizes, failures, retried, attempted,
                time.perf_counter() - test_start, camera)
        camera.close()
        results_f.close()
        print(f"\nResults saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()
