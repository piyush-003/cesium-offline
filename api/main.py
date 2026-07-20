"""
CesiumOffline FastAPI — REST API for managing offline 3D map builds.
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from typing import Optional
import asyncio
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

# Add parent dir to path so we can import scripts
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

app = FastAPI(
    title="CesiumOffline API",
    description="Build fully offline 3D Cesium map viewers from coordinates",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECTS_DIR = ROOT / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

# In-memory build status store
build_status: dict[str, dict] = {}


# ─── Models ────────────────────────────────────────────────────────────────────

class BuildRequest(BaseModel):
    name: str
    lat_min: float
    lon_min: float
    lat_max: float
    lon_max: float
    max_zoom: int = 16
    skip_imagery: bool = False
    skip_dem: bool = False
    skip_buildings: bool = False

    @field_validator("name")
    @classmethod
    def name_alphanumeric(cls, v):
        import re
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Name must be alphanumeric (underscores and hyphens allowed)")
        return v.lower()

    @field_validator("max_zoom")
    @classmethod
    def zoom_range(cls, v):
        if not (1 <= v <= 22):
            raise ValueError("max_zoom must be between 1 and 22")
        return v


class ProjectStatus(BaseModel):
    name: str
    status: str  # idle | running | done | error
    step: str
    step_number: int
    total_steps: int
    progress: int  # 0-100
    message: str
    error: Optional[str] = None
    created_at: float
    bounds: Optional[dict] = None


# ─── Background build task ─────────────────────────────────────────────────────

def run_build(req: BuildRequest):
    name = req.name
    bounds = {
        "lat_min": req.lat_min,
        "lon_min": req.lon_min,
        "lat_max": req.lat_max,
        "lon_max": req.lon_max,
    }

    def update(step, step_number, total, progress, message):
        build_status[name].update({
            "status": "running",
            "step": step,
            "step_number": step_number,
            "total_steps": total,
            "progress": progress,
            "message": message,
            "error": None,
        })

    def fail(error):
        build_status[name].update({
            "status": "error",
            "error": error,
            "progress": build_status[name].get("progress", 0),
        })

    try:
        project_dir = PROJECTS_DIR / name
        project_dir.mkdir(parents=True, exist_ok=True)

        steps = []
        if not req.skip_imagery:
            steps.append("Download satellite imagery")
        if not req.skip_dem:
            steps.append("Download DEM elevation")
        if not req.skip_buildings:
            steps.append("Download OSM buildings")
        steps += ["Generate terrain tiles", "Generate viewer HTML"]
        total = len(steps)
        step_idx = 0

        # Step: Imagery
        if not req.skip_imagery:
            step_idx += 1
            update("Download satellite imagery", step_idx, total, 5, f"Fetching zoom 1–{req.max_zoom}...")
            from scripts.imagery import download_tiles
            download_tiles(
                lat_min=req.lat_min, lon_min=req.lon_min,
                lat_max=req.lat_max, lon_max=req.lon_max,
                output_dir=project_dir / "tiles" / "imagery",
                min_zoom=1, max_zoom=req.max_zoom, workers=32,
            )
            update("Download satellite imagery", step_idx, total, int(step_idx / total * 100), "Imagery complete")

        # Step: DEM
        if not req.skip_dem:
            step_idx += 1
            update("Download DEM elevation", step_idx, total, int(step_idx / total * 100) - 10, "Downloading SRTM tiles...")
            dem_path = project_dir / "dem.tif"
            if not dem_path.exists():
                from scripts.dem import download_dem
                download_dem(
                    lat_min=req.lat_min, lon_min=req.lon_min,
                    lat_max=req.lat_max, lon_max=req.lon_max,
                    output_path=dem_path,
                )
            update("Download DEM elevation", step_idx, total, int(step_idx / total * 100), "DEM ready")

        # Step: Buildings
        if not req.skip_buildings:
            step_idx += 1
            update("Download OSM buildings", step_idx, total, int(step_idx / total * 100) - 10, "Querying Overpass API...")
            buildings_path = project_dir / "buildings.geojson"
            if not buildings_path.exists():
                from scripts.buildings import download_buildings
                download_buildings(
                    lat_min=req.lat_min, lon_min=req.lon_min,
                    lat_max=req.lat_max, lon_max=req.lon_max,
                    output_path=buildings_path,
                )
            update("Download OSM buildings", step_idx, total, int(step_idx / total * 100), "Buildings ready")

        # Step: Terrain
        step_idx += 1
        update("Generate terrain tiles", step_idx, total, int(step_idx / total * 100) - 10, "Running CTB via Docker...")
        dem_path = project_dir / "dem.tif"
        terrain_dir = project_dir / "tiles" / "terrain"
        terrain_dir.mkdir(parents=True, exist_ok=True)
        layer_json = terrain_dir / "layer.json"
        if not layer_json.exists() or not any(terrain_dir.rglob("*.terrain")):
            if dem_path.exists():
                from scripts.terrain import generate_terrain_tiles
                generate_terrain_tiles(dem_path=dem_path, output_dir=terrain_dir)
        update("Generate terrain tiles", step_idx, total, int(step_idx / total * 100), "Terrain tiles ready")

        # Step: HTML
        step_idx += 1
        update("Generate viewer HTML", step_idx, total, 95, "Writing index.html...")
        from scripts.htmlgen import generate_viewer
        generate_viewer(
            project_dir=project_dir,
            bounds=bounds,
            name=name,
            max_zoom=req.max_zoom,
        )

        # Save metadata
        meta = {
            "name": name,
            "bounds": bounds,
            "max_zoom": req.max_zoom,
            "created_at": build_status[name]["created_at"],
        }
        with open(project_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)

        build_status[name].update({
            "status": "done",
            "step": "Complete",
            "step_number": total,
            "total_steps": total,
            "progress": 100,
            "message": "Build complete — viewer ready",
            "error": None,
        })

    except Exception as e:
        fail(str(e))


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/projects")
def list_projects():
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        meta = {}
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)

        # Figure out status
        status = build_status.get(d.name, {})
        has_html = (d / "index.html").exists()
        has_imagery = any((d / "tiles" / "imagery").rglob("*.jpg")) if (d / "tiles" / "imagery").exists() else False
        has_terrain = any((d / "tiles" / "terrain").rglob("*.terrain")) if (d / "tiles" / "terrain").exists() else False
        has_buildings = (d / "buildings.geojson").exists()

        projects.append({
            "name": d.name,
            "bounds": meta.get("bounds"),
            "max_zoom": meta.get("max_zoom", 16),
            "created_at": meta.get("created_at", 0),
            "status": status.get("status", "done" if has_html else "idle"),
            "progress": status.get("progress", 100 if has_html else 0),
            "has_imagery": has_imagery,
            "has_terrain": has_terrain,
            "has_buildings": has_buildings,
            "has_viewer": has_html,
        })
    return projects


@app.post("/api/projects", status_code=202)
def create_project(req: BuildRequest, background_tasks: BackgroundTasks):
    name = req.name

    # Check if already running
    existing = build_status.get(name, {})
    if existing.get("status") == "running":
        raise HTTPException(409, f"Build already running for '{name}'")

    build_status[name] = {
        "status": "running",
        "step": "Initializing",
        "step_number": 0,
        "total_steps": 1,
        "progress": 0,
        "message": "Starting build...",
        "error": None,
        "created_at": time.time(),
        "bounds": {
            "lat_min": req.lat_min,
            "lon_min": req.lon_min,
            "lat_max": req.lat_max,
            "lon_max": req.lon_max,
        },
    }

    background_tasks.add_task(run_build, req)
    return {"name": name, "status": "started"}


@app.get("/api/projects/{name}/status")
def get_status(name: str):
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists() and name not in build_status:
        raise HTTPException(404, f"Project '{name}' not found")

    status = build_status.get(name, {
        "status": "done" if (project_dir / "index.html").exists() else "idle",
        "step": "Complete",
        "step_number": 1,
        "total_steps": 1,
        "progress": 100 if (project_dir / "index.html").exists() else 0,
        "message": "Ready",
        "error": None,
        "created_at": 0,
        "bounds": None,
    })
    return status


@app.delete("/api/projects/{name}")
def delete_project(name: str):
    project_dir = PROJECTS_DIR / name
    if not project_dir.exists():
        raise HTTPException(404, f"Project '{name}' not found")

    status = build_status.get(name, {})
    if status.get("status") == "running":
        raise HTTPException(409, "Cannot delete a project that is currently building")

    shutil.rmtree(project_dir)
    build_status.pop(name, None)
    return {"deleted": name}


# ─── Serve React frontend ───────────────────────────────────────────────────────

FRONTEND_DIST = ROOT / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(404)
        index = FRONTEND_DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(404, "Frontend not built yet. Run: cd frontend && npm run build")
