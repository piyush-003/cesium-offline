"""
terrain.py — Generate Cesium terrain tiles from DEM using Docker CTB.

CRITICAL LESSONS LEARNED:
- Input DEM must be Int16 (not Float32)
- Do NOT add gdaladdo overviews to DEM before CTB — they make tiles tiny/flat
- layer.json must use scheme: tms
- Server must serve tiles with Content-Encoding: gzip
- No x/y coordinate transformation needed for standard CTB output
  (Cesium requests match CTB tile coordinates directly)
"""

import json
import os
import subprocess
from pathlib import Path

# On Windows/WSL, the real working docker binary is docker.exe
DOCKER = "/Docker/host/bin/docker.exe" if os.path.exists("/Docker/host/bin/docker.exe") else "docker"


def to_docker_mount_path(path: Path) -> str:
    """
    Convert a WSL path like /mnt/c/Users/foo/bar to /c/Users/foo/bar
    which is the format docker.exe expects for -v volume mounts from WSL.
    """
    s = str(path)
    if s.startswith("/mnt/") and len(s) > 6:
        # /mnt/c/... → /c/...
        return s[4:]
    return s


def check_docker_ctb():
    print(f"  Using docker binary: {DOCKER}")
    try:
        result = subprocess.run(
            [DOCKER, "images", "-q", "homme/cesium-terrain-builder"],
            capture_output=True, text=True, check=True
        )
        if result.stdout.strip():
            return True
        print("  Pulling homme/cesium-terrain-builder...")
        subprocess.run([DOCKER, "pull", "homme/cesium-terrain-builder"], check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  Docker check failed: {e}")
        return False


def generate_terrain_tiles(dem_path, output_dir):
    dem_path = Path(dem_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not check_docker_ctb():
        raise RuntimeError("Docker or homme/cesium-terrain-builder not available.")

    data_dir = dem_path.parent

    # Check DEM is Int16
    result = subprocess.run(["gdalinfo", str(dem_path)], capture_output=True, text=True)
    if "Int16" not in result.stdout:
        raise RuntimeError(
            f"DEM must be Int16 type. Run: gdal_translate -ot Int16 {dem_path} {dem_path.stem}_int16.tif"
        )

    # Check no overviews
    if "Overview" in result.stdout:
        print("  WARNING: DEM has overviews — these will cause low-quality terrain tiles!")
        print("  Removing overviews by creating clean copy...")
        clean_path = dem_path.parent / f"{dem_path.stem}_noov.tif"
        subprocess.run([
            "gdal_translate", str(dem_path), str(clean_path)
        ], check=True, capture_output=True)
        dem_path = clean_path
        print(f"  Using clean DEM: {dem_path}")

    # Get relative path for Docker mount
    try:
        rel_output = output_dir.relative_to(data_dir)
        container_output = f"/data/{rel_output}"
    except ValueError:
        container_output = "/data/terrain_output"
        import shutil
        tmp = data_dir / "terrain_output"
        tmp.mkdir(exist_ok=True)

    dem_filename = dem_path.name
    mount_src = to_docker_mount_path(data_dir)
    # container_output must use forward slashes
    container_output_posix = container_output.replace("\\", "/")
    print(f"  Running CTB via Docker ({DOCKER})...")
    print(f"  DEM: {dem_path}")
    print(f"  Mount: {mount_src} -> /data")

    cmd = [
        DOCKER, "run", "--rm",
        "-v", f"{mount_src}:/data",
        "homme/cesium-terrain-builder",
        "ctb-tile", "-o", container_output_posix,
        f"/data/{dem_filename}"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("  ── docker stdout ──")
        print(result.stdout)
        print("  ── docker stderr ──")
        print(result.stderr)
        raise RuntimeError(
            f"CTB failed (exit {result.returncode}): "
            f"{(result.stderr or result.stdout).strip()[:500]}"
        )
    if result.stdout.strip():
        print(result.stdout)

    # If we used tmp output, move it
    tmp = data_dir / "terrain_output"
    if tmp.exists() and tmp != output_dir:
        import shutil
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.move(str(tmp), str(output_dir))

    terrain_files = list(output_dir.rglob("*.terrain"))
    print(f"  Generated {len(terrain_files)} terrain tiles")

    # Detect zoom levels
    zoom_levels = set()
    for tf in terrain_files:
        try:
            z = int(tf.parts[-3])
            zoom_levels.add(z)
        except:
            pass
    max_zoom = max(zoom_levels) if zoom_levels else 11
    min_zoom = min(zoom_levels) if zoom_levels else 0
    print(f"  Zoom levels: {min_zoom}-{max_zoom}")

    # Verify tile quality at max zoom
    sample = next(output_dir.rglob("*.terrain"), None)
    if sample:
        import gzip, struct
        try:
            with gzip.open(sample, 'rb') as f:
                data = f.read()
            heights = struct.unpack('<4225H', data[:8450])
            mn = min(heights)/65535*10000-1000
            mx = max(heights)/65535*10000-1000
            size = sample.stat().st_size
            print(f"  Sample tile: {size} bytes, elevation {mn:.0f}m-{mx:.0f}m")
            if size < 500:
                print(f"  WARNING: Tiles are very small ({size}b). Check DEM quality.")
            elif size > 2000:
                print(f"  Tile quality looks good!")
        except Exception as e:
            print(f"  Could not verify tile: {e}")

    # Write layer.json
    layer = {
        "tilejson": "2.2.0",
        "name": "Terrain",
        "description": "Generated by CesiumOffline",
        "version": "1.0.0",
        "minzoom": min_zoom,
        "maxzoom": max_zoom,
        "tiles": ["{z}/{x}/{y}.terrain"],
        "format": "heightmap-1.0",
        "scheme": "tms"
    }
    with open(output_dir / "layer.json", "w") as f:
        json.dump(layer, f, indent=4)

    print(f"  Terrain tiles ready at {output_dir}")
    return max_zoom