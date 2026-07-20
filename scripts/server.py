"""
server.py — Node.js HTTP server for Cesium offline viewer.

CRITICAL LESSONS LEARNED about CTB terrain tile serving:
- CTB generates tiles with NO x/y coordinate transformation needed
- Cesium requests tiles at same x/y as CTB stores them (direct match)
- Tiles ARE gzip compressed — must serve with Content-Encoding: gzip
- layer.json scheme=tms is correct
- The server tries direct match first, then small offsets as fallback
"""

import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


SERVER_JS_TEMPLATE = r"""
const http = require("http");
const fs = require("fs");
const path = require("path");
const PORT = {port};
const PROJECT_DIR = {project_dir_json};

const MIME = {{
  ".html": "text/html",
  ".js":   "application/javascript",
  ".css":  "text/css",
  ".json": "application/json",
  ".jpg":  "image/jpeg",
  ".png":  "image/png",
  ".terrain": "application/octet-stream",
  ".geojson": "application/json",
}};

http.createServer((req, res) => {{
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Headers", "*");

  let urlPath = req.url.split("?")[0];

  // Terrain tile handler
  const terrainMatch = urlPath.match(/^\/tiles\/terrain\/(\d+)\/(\d+)\/(\d+)\.terrain$/);
  if (terrainMatch) {{
    const z  = parseInt(terrainMatch[1]);
    const cx = parseInt(terrainMatch[2]);
    const cy = parseInt(terrainMatch[3]);
    const base = path.join(PROJECT_DIR, "tiles", "terrain");
    const yMax = Math.pow(2, z) - 1;

    // CTB stores tiles at same coordinates Cesium requests.
    // Try direct match first, then small offsets for edge cases.
    const candidates = [
      [cx, cy],
      [cx, yMax - cy],
      [cx, cy + 1],
      [cx, cy - 1],
      [cx, yMax - cy + 1],
      [cx, yMax - cy - 1],
    ];

    const tryNext = (i) => {{
      if (i >= candidates.length) {{
        res.writeHead(404); res.end("Not found");
        return;
      }}
      const [tx, ty] = candidates[i];
      if (ty < 0) {{ tryNext(i+1); return; }}
      const filePath = path.join(base, String(z), String(tx), ty + ".terrain");
      fs.readFile(filePath, (err, data) => {{
        if (err) {{ tryNext(i + 1); return; }}
        // Tiles are gzip compressed — must set Content-Encoding
        res.writeHead(200, {{
          "Content-Type": "application/octet-stream",
          "Content-Encoding": "gzip"
        }});
        res.end(data);
      }});
    }};
    tryNext(0);
    return;
  }}

  // Serve all other files from project directory
  const filePath = path.join(PROJECT_DIR, urlPath === "/" ? "index.html" : urlPath);
  fs.readFile(filePath, (err, data) => {{
    if (err) {{
      res.writeHead(404); res.end("Not found: " + urlPath);
      return;
    }}
    const ext  = path.extname(filePath);
    const mime = MIME[ext] || "application/octet-stream";
    res.writeHead(200, {{ "Content-Type": mime }});
    res.end(data);
  }});

}}).listen(PORT, "0.0.0.0", () => {{
  console.log("\\n  CesiumOffline server running at http://0.0.0.0:" + PORT);
  console.log("  Open: http://localhost:" + PORT + "/index.html\\n");
}});
"""


def _write_server_js(project_dir, port):
    project_dir = Path(project_dir)
    server_path = project_dir / "server.js"
    js = SERVER_JS_TEMPLATE.format(
        port=port,
        project_dir_json=json.dumps(str(project_dir))
    )
    server_path.write_text(js)
    return server_path


def start_server(project_dir, port=8085):
    project_dir = Path(project_dir)
    server_path = _write_server_js(project_dir, port)
    print(f"\n  Starting server on port {port}...")
    print(f"  URL: http://localhost:{port}/index.html")
    print(f"  Press Ctrl+C to stop\n")

    def open_browser():
        time.sleep(2)
        webbrowser.open(f"http://localhost:{port}/index.html")
    threading.Thread(target=open_browser, daemon=True).start()

    try:
        subprocess.run(["node", str(server_path)], check=True)
    except KeyboardInterrupt:
        print("\n  Server stopped.")
    except FileNotFoundError:
        raise RuntimeError("Node.js not found. Install: sudo apt install nodejs")


def start_server_with_upgrade_offer(project_dir, bounds, current_max_zoom,
                                     port=8085, workers=32):
    project_dir = Path(project_dir)
    server_path = _write_server_js(project_dir, port)

    print(f"\n  Starting server on port {port}...")

    server_proc = subprocess.Popen(
        ["node", str(server_path)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    time.sleep(1.5)
    if server_proc.poll() is not None:
        out, err = server_proc.communicate()
        raise RuntimeError(f"Server failed: {err.decode()}")

    print(f"  Server running at http://localhost:{port}/index.html")
    webbrowser.open(f"http://localhost:{port}/index.html")

    if current_max_zoom < 22:
        print(f"\n  Viewer open with zoom level {current_max_zoom}.")
        print(f"  Higher zoom available: {current_max_zoom+1}-22 (better detail, slower download)")

        try:
            answer = input(f"\n  Download higher zoom imagery? (yes/no or zoom level e.g. '19'): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "no"

        if answer in ("yes", "y") or answer.isdigit():
            next_zoom = int(answer) if answer.isdigit() else min(current_max_zoom + 2, 22)

            def bg_download():
                from scripts.imagery import download_tiles
                print(f"\n  Downloading zoom {current_max_zoom+1}-{next_zoom} in background...")
                download_tiles(
                    lat_min=bounds["lat_min"], lon_min=bounds["lon_min"],
                    lat_max=bounds["lat_max"], lon_max=bounds["lon_max"],
                    output_dir=project_dir / "tiles" / "imagery",
                    min_zoom=current_max_zoom + 1,
                    max_zoom=next_zoom,
                    workers=workers,
                )
                print(f"\n  Background download complete (zoom {next_zoom})")
                print(f"  Refresh browser to see higher resolution imagery.")

                # Update HTML max zoom
                html_path = project_dir / "index.html"
                if html_path.exists():
                    content = html_path.read_text()
                    content = content.replace(
                        f"maximumLevel: {current_max_zoom}",
                        f"maximumLevel: {next_zoom}"
                    )
                    html_path.write_text(content)

            threading.Thread(target=bg_download, daemon=True).start()

    print("\n  Server running. Press Ctrl+C to stop.\n")
    try:
        server_proc.wait()
    except KeyboardInterrupt:
        server_proc.terminate()
        print("\n  Server stopped.")