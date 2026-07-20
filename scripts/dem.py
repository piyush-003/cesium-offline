"""
dem.py — Download and prepare a DEM using SRTM1 from AWS skadi (30m resolution).
Proven working method — same source as Kashmir project.

CRITICAL LESSONS LEARNED:
- Use SRTM1 from AWS skadi (3601x3601 per tile = 30m resolution)
- Convert to Int16 (NOT Float32) — CTB requires Int16
- Do NOT add gdaladdo overviews — they cause CTB to generate tiny/low-quality tiles
- Use gdalbuildvrt to merge tiles (not gdal_merge.py which resamples)
"""

import math
import os
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


def download_dem(lat_min, lon_min, lat_max, lon_max, output_path):
    output_path = Path(output_path)
    tmp_dir = output_path.parent / "_dem_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    lat_tiles = range(math.floor(lat_min), math.ceil(lat_max))
    lon_tiles = range(math.floor(lon_min), math.ceil(lon_max))

    hgt_files = []

    for lat in lat_tiles:
        for lon in lon_tiles:
            lat_str = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
            lon_str = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
            tile_id = f"{lat_str}{lon_str}"
            hgt_path = tmp_dir / f"{tile_id}.hgt"

            if hgt_path.exists() and hgt_path.stat().st_size > 20000000:
                print(f"  Already have {tile_id}.hgt, skipping")
                hgt_files.append(str(hgt_path))
                continue

            lat_dir = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
            url = f"https://s3.amazonaws.com/elevation-tiles-prod/skadi/{lat_dir}/{tile_id}.hgt.gz"
            gz_path = tmp_dir / f"{tile_id}.hgt.gz"

            print(f"  Downloading {tile_id} from AWS skadi...")
            try:
                r = requests.get(url, stream=True, timeout=300)
                if r.status_code == 200:
                    with open(gz_path, "wb") as f:
                        downloaded = 0
                        for chunk in r.iter_content(chunk_size=65536):
                            f.write(chunk)
                            downloaded += len(chunk)
                            print(f"    {downloaded/1024/1024:.1f} MB", end="\r")
                    print(f"  Downloaded {tile_id} ({gz_path.stat().st_size/1024/1024:.1f} MB)")
                    subprocess.run(["gunzip", "-f", str(gz_path)], check=True)
                    hgt_files.append(str(hgt_path))
                else:
                    raise RuntimeError(f"HTTP {r.status_code}")
            except Exception as e:
                raise RuntimeError(f"Failed to download {tile_id}: {e}")

    if not hgt_files:
        raise RuntimeError("No DEM tiles downloaded!")

    # Verify SRTM1 resolution
    result = subprocess.run(["gdalinfo", hgt_files[0]], capture_output=True, text=True)
    if "3601" in result.stdout:
        print(f"  Confirmed SRTM1 30m resolution (3601x3601)")
    else:
        print(f"  WARNING: unexpected resolution")

    # Merge via VRT (preserves full resolution, no resampling)
    print(f"  Merging {len(hgt_files)} tiles via VRT...")
    vrt_path = tmp_dir / "merged.vrt"
    subprocess.run(["gdalbuildvrt", str(vrt_path)] + hgt_files,
                   check=True, capture_output=True)

    # Crop to bounds
    print(f"  Cropping to bounds...")
    cropped_path = tmp_dir / "cropped.tif"
    subprocess.run([
        "gdalwarp",
        "-te", str(lon_min), str(lat_min), str(lon_max), str(lat_max),
        "-t_srs", "EPSG:4326",
        str(vrt_path), str(cropped_path)
    ], check=True, capture_output=True)

    # Convert to Int16 — REQUIRED for CTB to produce good tiles
    # WARNING: Do NOT add gdaladdo overviews after this step
    print(f"  Converting to Int16 (required for CTB quality)...")
    subprocess.run([
        "gdal_translate", "-ot", "Int16", "-a_nodata", "-32768",
        str(cropped_path), str(output_path)
    ], check=True, capture_output=True)

    result = subprocess.run(["gdalinfo", "-stats", str(output_path)],
                            capture_output=True, text=True)
    for line in result.stdout.split("\n"):
        if "Minimum" in line or "Size is" in line:
            print(f"  {line.strip()}")

    print(f"  DEM ready: {output_path}")