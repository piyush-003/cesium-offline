#!/usr/bin/env python3
"""
CesiumOffline - One command to build a fully offline 3D map viewer.

Usage:
    python3 run.py --bounds "34.08154,73.58274,34.52480,74.13570" --name kashmir
    python3 run.py --bounds "34.08154,73.58274,34.52480,74.13570" --name kashmir --max-zoom 19
    python3 run.py --name kashmir --serve-only   # just start the server for existing project
"""

import argparse
import os
import sys
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="CesiumOffline — Build a fully offline 3D Cesium map from coordinates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full build from scratch
  python3 run.py --bounds "34.08154,73.58274,34.52480,74.13570" --name kashmir

  # Build with higher zoom (slower but better imagery)
  python3 run.py --bounds "34.08154,73.58274,34.52480,74.13570" --name kashmir --max-zoom 19

  # Only start server for existing project
  python3 run.py --name kashmir --serve-only

  # Skip imagery download (use existing tiles)
  python3 run.py --bounds "34.08154,73.58274,34.52480,74.13570" --name kashmir --skip-imagery

  # Skip DEM download (use existing DEM)
  python3 run.py --bounds "34.08154,73.58274,34.52480,74.13570" --name kashmir --skip-dem
        """
    )

    parser.add_argument("--bounds", type=str,
        help="Area bounds as 'lat_min,lon_min,lat_max,lon_max' e.g. '34.08,73.58,34.52,74.13'")
    parser.add_argument("--name", type=str, required=True,
        help="Project name (e.g. 'kashmir'). Output goes to projects/<name>/")
    parser.add_argument("--max-zoom", type=int, default=16,
        help="Max imagery zoom level to download immediately (default: 16). Higher = slower but better quality.")
    parser.add_argument("--serve-only", action="store_true",
        help="Skip all downloads, just start the server for an existing project")
    parser.add_argument("--skip-imagery", action="store_true",
        help="Skip imagery download (use existing tiles if present)")
    parser.add_argument("--skip-dem", action="store_true",
        help="Skip DEM download (use existing DEM if present)")
    parser.add_argument("--skip-buildings", action="store_true",
        help="Skip OSM buildings download")
    parser.add_argument("--port", type=int, default=8088,
        help="Port to serve on (default: 8085)")
    parser.add_argument("--workers", type=int, default=32,
        help="Number of parallel download workers (default: 32)")

    args = parser.parse_args()

    # Validate
    if not args.serve_only and not args.bounds:
        parser.error("--bounds is required unless using --serve-only")

    # Parse bounds
    bounds = None
    if args.bounds:
        try:
            parts = [float(x.strip()) for x in args.bounds.split(",")]
            if len(parts) != 4:
                raise ValueError
            bounds = {
                "lat_min": parts[0],
                "lon_min": parts[1],
                "lat_max": parts[2],
                "lon_max": parts[3]
            }
        except ValueError:
            parser.error("--bounds must be 4 comma-separated floats: lat_min,lon_min,lat_max,lon_max")

    # Project directory
    project_dir = Path(__file__).parent / "projects" / args.name
    project_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  CesiumOffline — Project: {args.name}")
    if bounds:
        print(f"  Bounds: {bounds['lat_min']},{bounds['lon_min']} → {bounds['lat_max']},{bounds['lon_max']}")
    print(f"  Directory: {project_dir}")
    print(f"{'='*60}\n")

    if args.serve_only:
        from scripts.server import start_server
        start_server(project_dir, args.port)
        return

    # Run pipeline
    from scripts.pipeline import Pipeline
    pipeline = Pipeline(
        project_dir=project_dir,
        bounds=bounds,
        name=args.name,
        max_zoom=args.max_zoom,
        skip_imagery=args.skip_imagery,
        skip_dem=args.skip_dem,
        skip_buildings=args.skip_buildings,
        port=args.port,
        workers=args.workers,
    )
    pipeline.run()

if __name__ == "__main__":
    main()