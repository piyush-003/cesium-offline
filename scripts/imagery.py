"""
imagery.py — Download Google Maps satellite tiles.
Uses 32 parallel workers, skips existing tiles automatically.
"""

import math
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

GOOGLE_URL = "https://mt{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def deg2tile(lat, lon, zoom):
    """Convert lat/lon to tile x/y at given zoom."""
    lat_r = math.radians(lat)
    n = 2 ** zoom
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(lat_r)) / math.pi) / 2 * n)
    return x, y


def download_tile(z, x, y, output_dir):
    """Download a single tile. Returns 'skip', 'ok', or 'fail'."""
    path = Path(output_dir) / str(z) / str(x) / f"{y}.jpg"
    if path.exists() and path.stat().st_size > 500:
        return "skip"
    path.parent.mkdir(parents=True, exist_ok=True)
    server = (x + y) % 4  # rotate between mt0-mt3
    url = GOOGLE_URL.format(s=server, x=x, y=y, z=z)
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            path.write_bytes(r.content)
            return "ok"
        return f"http_{r.status_code}"
    except Exception as e:
        return f"err_{str(e)[:40]}"


def download_tiles(lat_min, lon_min, lat_max, lon_max,
                   output_dir, min_zoom=1, max_zoom=16, workers=32):
    """
    Download all tiles for the bounding box across zoom levels.
    Skips existing tiles automatically.
    """
    output_dir = Path(output_dir)
    total_saved = 0
    total_skipped = 0
    total_failed = 0
    lock = threading.Lock()

    for z in range(min_zoom, max_zoom + 1):
        x1, y1 = deg2tile(lat_max, lon_min, z)  # top-left
        x2, y2 = deg2tile(lat_min, lon_max, z)  # bottom-right

        # Build task list
        all_tiles = [(z, x, y) for x in range(x1, x2 + 1) for y in range(y1, y2 + 1)]
        pending = [(z, x, y) for z, x, y in all_tiles
                   if not (output_dir / str(z) / str(x) / f"{y}.jpg").exists()]

        total_z = len(all_tiles)
        skip_z = total_z - len(pending)
        print(f"  Zoom {z:2d}: {total_z:6d} tiles total | "
              f"{skip_z:6d} already done | {len(pending):6d} to download")

        if not pending:
            total_skipped += skip_z
            continue

        done = 0
        z_saved = 0
        z_failed = 0
        start = time.time()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(download_tile, z, x, y, output_dir): (z, x, y)
                       for z, x, y in pending}
            for future in as_completed(futures):
                result = future.result()
                done += 1
                with lock:
                    if result == "ok":
                        z_saved += 1
                        total_saved += 1
                    elif result == "skip":
                        total_skipped += 1
                    else:
                        z_failed += 1
                        total_failed += 1

                if done % 200 == 0 or done == len(pending):
                    elapsed = time.time() - start
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (len(pending) - done) / rate if rate > 0 else 0
                    print(f"    → {done}/{len(pending)} "
                          f"({100*done//len(pending)}%) "
                          f"| {z_saved} saved | {z_failed} failed "
                          f"| {rate:.0f} t/s | ETA {eta:.0f}s", end="\r")

        elapsed = time.time() - start
        print(f"\n  Zoom {z} done: {z_saved} saved, {z_failed} failed "
              f"in {elapsed:.1f}s")

    print(f"\n  ✅ Imagery complete: {total_saved} downloaded, "
          f"{total_skipped} skipped, {total_failed} failed")