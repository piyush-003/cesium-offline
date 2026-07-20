# CesiumOffline — Offline 3D Map Builder

Build a **fully offline Cesium 3D map viewer** from just a bounding box.  
One command downloads satellite imagery, elevation data, and OSM buildings — then serves a local 3D viewer with terrain and buildings, no internet required.

---

## Screenshots

> **Projects dashboard with embedded 3D viewer**

![CesiumOffline Dashboard](docs/screenshots/dashboard.png)

> **Kashmir — 3D terrain with satellite imagery and OSM buildings**

![Kashmir 3D View](docs/screenshots/kashmir_terrain.png)

---

## Features

- **Satellite imagery** — Downloaded from Google Maps (zoom 1–20)
- **3D terrain** — SRTM 30m elevation via Cesium Terrain Builder (Docker)
- **OSM buildings** — OpenStreetMap building footprints with heights
- **Embedded viewer** — Split-panel UI with fullscreen toggle, no separate browser tab
- **Offline-first** — Everything runs locally, no API keys needed
- **Web UI** — React frontend to manage projects, track build progress, open viewer

---

## Requirements

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.8+ | pre-installed |
| Node.js | 16+ | `sudo apt install nodejs` |
| GDAL | any | `sudo apt install gdal-bin` |
| Docker | any | `sudo apt install docker.io` |
| CTB image | latest | `docker pull homme/cesium-terrain-builder` |

**On Windows (WSL2):** Docker Desktop must be running with WSL integration enabled for your distro (`Settings → Resources → WSL Integration → Ubuntu → ON`).

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/yourusername/cesium-offline.git
cd cesium-offline

pip3 install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
```

### 2. Build a map

```bash
python3 serve.py --skip-build
```

Open `http://localhost:8000` → click **+ New Build** → enter bounds and a name → **Start Build**.

Or use the CLI directly:

```bash
python3 run.py \
  --bounds "34.08154,73.58274,34.52480,74.13570" \
  --name kashmir
```

Bounds format: `lat_min, lon_min, lat_max, lon_max`

### 3. View the map

Once built, click **⊞ View Map** on any project card.  
The 3D viewer opens in a split panel — fullscreen toggle is in the top-right of the viewer.

> **Note:** The Cesium viewer is served by a separate Node.js server on port 8088.  
> Run it in a second terminal:
> ```bash
> python3 run.py --name kashmir --serve-only
> ```

---

## CesiumJS Setup

CesiumJS is **not included** in this repo (it's 66MB). Download it once and place it in your project:

```bash
cd projects/kashmir
wget https://github.com/CesiumGS/cesium/releases/download/1.115/Cesium-1.115.zip
sudo apt install unzip
unzip Cesium-1.115.zip -d Cesium
```

Or symlink a shared copy across all projects:

```bash
ln -s /path/to/CesiumJS projects/kashmir/Cesium
```

---

## Controls

| Action | Mouse | Touchpad / Laptop |
|--------|-------|-------------------|
| Pan | Left drag | One-finger drag |
| Tilt / Rotate | Right drag | Ctrl + drag |
| Zoom | Scroll wheel | Two-finger pinch or scroll |
| Fly to coords | Type `lat, lon` in search box → Enter | Same |

---

## CLI Reference

```bash
# Full build from scratch
python3 run.py --bounds "lat_min,lon_min,lat_max,lon_max" --name myproject

# Higher zoom imagery (slower but more detail)
python3 run.py --bounds "..." --name myproject --max-zoom 19

# Skip steps (reuse existing data)
python3 run.py --bounds "..." --name myproject --skip-imagery
python3 run.py --bounds "..." --name myproject --skip-dem
python3 run.py --bounds "..." --name myproject --skip-buildings

# Just serve an existing project
python3 run.py --name myproject --serve-only

# Custom port
python3 run.py --bounds "..." --name myproject --port 9000
```

---

## Project Structure

```
cesium-offline/
├── run.py               ← CLI entry point
├── serve.py             ← FastAPI + React UI server
├── requirements.txt
├── setup.sh             ← One-time dependency installer
├── scripts/
│   ├── pipeline.py      ← Orchestrates the full build
│   ├── imagery.py       ← Google Maps tile downloader
│   ├── dem.py           ← SRTM elevation downloader
│   ├── buildings.py     ← OSM building downloader
│   ├── terrain.py       ← CTB terrain tile generator
│   ├── htmlgen.py       ← Cesium viewer HTML generator
│   └── server.py        ← Node.js terrain tile server
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   └── package.json
├── api/
│   └── main.py          ← FastAPI REST API
└── projects/            ← Generated data (gitignored)
    └── kashmir/
        ├── index.html
        ├── dem.tif
        ├── buildings.geojson
        └── tiles/
            ├── imagery/
            └── terrain/
```

---

## How It Works

### Imagery
- Downloaded from Google Maps satellite (`lyrs=s`) using 32 parallel workers
- WebMercator tiling scheme, zoom 1–16 by default
- Skips existing tiles automatically on re-run

### Terrain
- SRTM1 30m DEM downloaded from AWS skadi
- Converted to Int16 (required by CTB)
- Processed by `homme/cesium-terrain-builder` Docker image
- Served with gzip `Content-Encoding` and TMS Y-flip handling

### Buildings
- Downloaded from OpenStreetMap via Overpass API
- Height from `height` tag or `building:levels × 3m`
- Rendered using `CLAMP_TO_GROUND + RELATIVE_TO_GROUND` for reliable terrain anchoring

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Input/output error` on `docker` | Docker Desktop not running, or WSL integration off — enable it in Docker Desktop → Settings → Resources → WSL Integration |
| Terrain appears flat | Check `projects/<name>/tiles/terrain/layer.json` exists |
| Green/striped area outside map | Normal at low zoom — zoom into the AOI bounds |
| Buildings floating | Normal for 30m DEM — the `-2.0m` offset reduces this |
| CesiumJS not found | Download and place at `projects/<name>/Cesium/` — see CesiumJS Setup above |
| Server won't start | Check Node.js: `node --version` |

---

## License

MIT — use freely.
