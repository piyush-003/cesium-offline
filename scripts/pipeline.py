"""
Pipeline — orchestrates the full build process.
"""

import os
import sys
import time
import subprocess
from pathlib import Path


class Pipeline:
    def __init__(self, project_dir, bounds, name, max_zoom=16,
                 skip_imagery=False, skip_dem=False, skip_buildings=False,
                 port=8085, workers=32):
        self.project_dir = Path(project_dir)
        self.bounds = bounds
        self.name = name
        self.max_zoom = max_zoom
        self.skip_imagery = skip_imagery
        self.skip_dem = skip_dem
        self.skip_buildings = skip_buildings
        self.port = port
        self.workers = workers

        # Subdirectory layout
        self.tiles_dir = self.project_dir / "tiles"
        self.imagery_dir = self.tiles_dir / "imagery"
        self.terrain_dir = self.tiles_dir / "terrain"
        self.dem_path = self.project_dir / "dem.tif"
        self.buildings_path = self.project_dir / "buildings.geojson"

        for d in [self.tiles_dir, self.imagery_dir, self.terrain_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def step(self, n, total, title):
        print(f"\n{'─'*60}")
        print(f"  Step {n}/{total}: {title}")
        print(f"{'─'*60}")

    def run(self):
        steps = []
        if not self.skip_imagery:
            steps.append(("Download satellite imagery (zoom 1–16)", self.download_imagery))
        if not self.skip_dem:
            steps.append(("Download & prepare DEM", self.download_dem))
        if not self.skip_buildings:
            steps.append(("Download OSM buildings", self.download_buildings))
        steps.append(("Generate terrain tiles (CTB)", self.generate_terrain))
        steps.append(("Link CesiumJS", self.link_cesium))
        steps.append(("Link CesiumJS", self.link_cesium))
        steps.append(("Generate viewer HTML", self.generate_html))
        steps.append(("Start server", self.start_server))

        total = len(steps)
        for i, (title, fn) in enumerate(steps, 1):
            self.step(i, total, title)
            fn()

        # After serving starts, offer higher zoom download
        # (server is blocking so we handle this inside start_server)

    # ─────────────────────────────────────────────
    # STEP: Download imagery
    # ─────────────────────────────────────────────
    def download_imagery(self):
        from scripts.imagery import download_tiles
        lat_min = self.bounds["lat_min"]
        lon_min = self.bounds["lon_min"]
        lat_max = self.bounds["lat_max"]
        lon_max = self.bounds["lon_max"]

        # Check what's already there
        existing = list(self.imagery_dir.glob("**/*.jpg"))
        if existing:
            print(f"  Found {len(existing)} existing imagery tiles.")

        print(f"  Downloading zoom levels 1–{self.max_zoom} ...")
        print(f"  Using {self.workers} parallel workers")
        download_tiles(
            lat_min=lat_min, lon_min=lon_min,
            lat_max=lat_max, lon_max=lon_max,
            output_dir=self.imagery_dir,
            min_zoom=1,
            max_zoom=self.max_zoom,
            workers=self.workers,
        )
        print(f"  ✅ Imagery download complete (zoom 1–{self.max_zoom})")

    # ─────────────────────────────────────────────
    # STEP: Download DEM
    # ─────────────────────────────────────────────
    def download_dem(self):
        from scripts.dem import download_dem
        if self.dem_path.exists():
            print(f"  ✅ DEM already exists at {self.dem_path}, skipping download.")
            return
        download_dem(
            lat_min=self.bounds["lat_min"],
            lon_min=self.bounds["lon_min"],
            lat_max=self.bounds["lat_max"],
            lon_max=self.bounds["lon_max"],
            output_path=self.dem_path,
        )

    # ─────────────────────────────────────────────
    # STEP: Download OSM buildings
    # ─────────────────────────────────────────────
    def download_buildings(self):
        from scripts.buildings import download_buildings
        if self.buildings_path.exists():
            size = self.buildings_path.stat().st_size
            print(f"  ✅ Buildings GeoJSON already exists ({size/1024:.0f} KB), skipping.")
            return
        download_buildings(
            lat_min=self.bounds["lat_min"],
            lon_min=self.bounds["lon_min"],
            lat_max=self.bounds["lat_max"],
            lon_max=self.bounds["lon_max"],
            output_path=self.buildings_path,
        )

    # ─────────────────────────────────────────────
    # STEP: Generate terrain tiles
    # ─────────────────────────────────────────────
    def generate_terrain(self):
        from scripts.terrain import generate_terrain_tiles
        layer_json = self.terrain_dir / "layer.json"
        if layer_json.exists() and any(self.terrain_dir.rglob("*.terrain")):
            print(f"  ✅ Terrain tiles already exist, skipping generation.")
            return
        if not self.dem_path.exists():
            print(f"  ⚠️  DEM not found at {self.dem_path}, skipping terrain generation.")
            return
        generate_terrain_tiles(
            dem_path=self.dem_path,
            output_dir=self.terrain_dir,
        )

    # ─────────────────────────────────────────────
    # STEP: Symlink CesiumJS
    # ─────────────────────────────────────────────
    def link_cesium(self):
        cesium_link = self.project_dir / "Cesium"
        if cesium_link.exists() or cesium_link.is_symlink():
            return
        # Search common locations
        candidates = [
            "/home/botlab/piyush/CesiumJS",
            "/home/botlab/CesiumJS",
            str(Path.home() / "CesiumJS"),
        ]
        for c in candidates:
            if Path(c).exists():
                cesium_link.symlink_to(c)
                print(f"  ✅ Linked CesiumJS from {c}")
                return
        print(f"  ⚠️  CesiumJS not found. Manually run:")
        print(f"     ln -sf /path/to/CesiumJS {cesium_link}")

    # ─────────────────────────────────────────────
    # STEP: Symlink CesiumJS
    # ─────────────────────────────────────────────
    def link_cesium(self):
        cesium_link = self.project_dir / "Cesium"
        if cesium_link.exists() or cesium_link.is_symlink():
            return
        # Search common locations
        candidates = [
            "/home/botlab/piyush/CesiumJS",
            "/home/botlab/CesiumJS",
            str(Path.home() / "CesiumJS"),
        ]
        for c in candidates:
            if Path(c).exists():
                cesium_link.symlink_to(c)
                print(f"  ✅ Linked CesiumJS from {c}")
                return
        print(f"  ⚠️  CesiumJS not found. Manually run:")
        print(f"     ln -sf /path/to/CesiumJS {cesium_link}")

    # ─────────────────────────────────────────────
    # STEP: Generate HTML viewer
    # ─────────────────────────────────────────────
    def generate_html(self):
        from scripts.htmlgen import generate_viewer
        generate_viewer(
            project_dir=self.project_dir,
            bounds=self.bounds,
            name=self.name,
            max_zoom=self.max_zoom,
        )

    # ─────────────────────────────────────────────
    # STEP: Start server (with offer for higher zoom)
    # ─────────────────────────────────────────────
    def start_server(self):
        from scripts.server import start_server_with_upgrade_offer
        start_server_with_upgrade_offer(
            project_dir=self.project_dir,
            bounds=self.bounds,
            current_max_zoom=self.max_zoom,
            port=self.port,
            workers=self.workers,
        )