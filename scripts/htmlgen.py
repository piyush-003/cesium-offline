"""
htmlgen.py — Generate the Cesium viewer HTML.

CRITICAL LESSONS LEARNED:
- Use CLAMP_TO_GROUND + RELATIVE_TO_GROUND for buildings (not terrain sampling)
  Terrain sampling with heightmap-1.0 format is unreliable
- verticalExaggeration must be 1.0 (not 1.5+) to match real-world proportions
- depthTestAgainstTerrain = true to hide buildings behind terrain
- Buildings appear instantly (no slow settling) with CLAMP_TO_GROUND approach
"""

from pathlib import Path


def generate_viewer(project_dir, bounds, name, max_zoom=16):
    project_dir = Path(project_dir)
    output_path = project_dir / "index.html"

    lat_min = bounds["lat_min"]
    lon_min = bounds["lon_min"]
    lat_max = bounds["lat_max"]
    lon_max = bounds["lon_max"]
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2
    title = name.replace("_", " ").title()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title} — CesiumOffline</title>
  <script src="Cesium/Build/Cesium/Cesium.js"></script>
  <link href="Cesium/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <style>
    html, body, #cesiumContainer {{ width:100%; height:100%; margin:0; padding:0; overflow:hidden; background:#000; }}
    #loadingOverlay {{
      position:absolute; top:0; left:0; width:100%; height:100%;
      background:rgba(0,0,0,0.85); z-index:9999;
      display:flex; flex-direction:column;
      align-items:center; justify-content:center; color:white;
      font-family:monospace; font-size:14px; gap:16px;
    }}
    #loadingMsg {{ color:#4aff91; font-size:15px; }}
    #loadingBar {{ width:320px; height:5px; background:rgba(255,255,255,0.15); border-radius:3px; overflow:hidden; }}
    #loadingFill {{ height:100%; width:0%; background:#4aff91; border-radius:3px; transition:width 0.4s ease; }}
    #loadingSub {{ font-size:11px; color:#888; }}
    #status {{
      position:absolute; bottom:30px; left:10px; z-index:999;
      background:rgba(0,0,0,0.75); color:#4aff91;
      font-family:monospace; font-size:12px; padding:6px 12px; border-radius:4px;
    }}
    #panel {{
      position:absolute; top:10px; left:10px; z-index:999;
      background:rgba(15,15,15,0.88); padding:12px 14px;
      border-radius:8px; color:white; font-family:sans-serif; font-size:13px;
    }}
    .label {{ font-size:10px; color:#888; text-transform:uppercase; letter-spacing:1px; font-weight:bold; margin-bottom:6px; }}
    .info-row {{ font-size:11px; color:#4aff91; margin-bottom:3px; padding:4px 8px; background:rgba(0,80,0,0.3); border-radius:4px; border-left:3px solid #4aff91; }}
    #searchBox {{
      position:absolute; top:10px; right:10px; z-index:999;
      background:rgba(15,15,15,0.88); padding:10px 12px;
      border-radius:8px; display:flex; gap:8px; align-items:flex-start;
    }}
    #searchBox input {{
      background:rgba(255,255,255,0.1); border:1px solid #4aff91;
      color:white; padding:5px 10px; border-radius:4px;
      font-family:monospace; font-size:12px; width:200px; outline:none;
    }}
    #searchBox input::placeholder {{ color:#888; }}
    #searchBox button {{
      background:#4aff91; color:#000; border:none; padding:6px 14px;
      border-radius:4px; cursor:pointer; font-weight:bold; font-size:12px;
    }}
    #searchBox button:hover {{ background:#2ecc71; }}
    #searchError {{ color:#ff6b6b; font-size:11px; margin-top:4px; display:none; }}
  </style>
</head>
<body>
  <div id="loadingOverlay">
    <div id="loadingMsg">Initializing...</div>
    <div id="loadingBar"><div id="loadingFill"></div></div>
    <div id="loadingSub">Loading terrain and buildings</div>
  </div>
  <div id="cesiumContainer"></div>
  <div id="panel">
    <div class="label">Offline — {title}</div>
    <div class="info-row">CesiumJS — Local</div>
    <div class="info-row">Imagery — Local tiles (zoom 1-{max_zoom})</div>
    <div class="info-row">Buildings — OSM GeoJSON</div>
    <div class="info-row">Terrain — SRTM CTB heightmap</div>
  </div>
  <div id="searchBox">
    <div>
      <input id="coordInput" type="text" placeholder="lat, lon (e.g. {center_lat:.4f}, {center_lon:.4f})" />
      <div id="searchError">Invalid format. Use: lat, lon</div>
    </div>
    <button onclick="flyToCoords()">Go</button>
  </div>
  <div id="status">Loading...</div>

  <script>
  function setLoading(msg, pct, sub) {{
    document.getElementById("loadingMsg").textContent = msg;
    document.getElementById("loadingFill").style.width = pct + "%";
    if (sub) document.getElementById("loadingSub").textContent = sub;
  }}

  function flyToCoords() {{
    const val = document.getElementById("coordInput").value.trim();
    const err = document.getElementById("searchError");
    const parts = val.split(",").map(s => parseFloat(s.trim()));
    if (parts.length !== 2 || isNaN(parts[0]) || isNaN(parts[1])) {{
      err.style.display = "block"; return;
    }}
    err.style.display = "none";
    window.viewer.camera.flyTo({{
      destination: Cesium.Cartesian3.fromDegrees(parts[1], parts[0], 2000),
      orientation: {{ heading: 0, pitch: Cesium.Math.toRadians(-45), roll: 0 }},
      duration: 2
    }});
  }}

  document.addEventListener("DOMContentLoaded", () => {{
    document.getElementById("coordInput").addEventListener("keydown", e => {{
      if (e.key === "Enter") flyToCoords();
    }});
  }});

  function getBuildingColor(h) {{
    if (h >= 30) return new Cesium.Color(0.42, 0.42, 0.40, 1.0);
    if (h >= 20) return new Cesium.Color(0.47, 0.46, 0.44, 1.0);
    if (h >= 12) return new Cesium.Color(0.52, 0.51, 0.49, 1.0);
    return new Cesium.Color(0.57, 0.56, 0.53, 1.0);
  }}

  async function init() {{
    setLoading("Loading terrain...", 10, "Connecting to terrain server");

    let terrainProvider;
    try {{
      terrainProvider = await Cesium.CesiumTerrainProvider.fromUrl("tiles/terrain", {{
        requestVertexNormals: false,
        requestWaterMask: false
      }});
      setLoading("Terrain loaded", 30, "Setting up viewer");
    }} catch(e) {{
      console.warn("Terrain failed:", e);
      terrainProvider = new Cesium.EllipsoidTerrainProvider();
      setLoading("Terrain fallback (flat)", 30, "Using ellipsoid");
    }}

    const aoiRect = Cesium.Rectangle.fromDegrees({lon_min}, {lat_min}, {lon_max}, {lat_max});

    const imageryProvider = new Cesium.UrlTemplateImageryProvider({{
      url: "tiles/imagery/{{z}}/{{x}}/{{y}}.jpg",
      minimumLevel: 1,
      maximumLevel: {max_zoom},
      tilingScheme: new Cesium.WebMercatorTilingScheme(),
      rectangle: aoiRect,
      credit: "Satellite Imagery"
    }});

    window.viewer = new Cesium.Viewer("cesiumContainer", {{
      baseLayer:            false,
      terrainProvider:      terrainProvider,
      baseLayerPicker:      false,
      geocoder:             false,
      timeline:             false,
      animation:            false,
      navigationHelpButton: false,
    }});

    // Add satellite imagery clipped to AOI only
    window.viewer.imageryLayers.addImageryProvider(imageryProvider);

    // Real-world proportions — do NOT increase this
    window.viewer.scene.verticalExaggeration = 1.0;
    window.viewer.scene.globe.depthTestAgainstTerrain = true;

    // Dark globe base color outside imagery area — hides corrupt/empty tiles
    window.viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#0a0c10");
    // Hide sky/atmosphere outside AOI so it blends with the dark UI
    window.viewer.scene.skyAtmosphere.show = false;
    window.viewer.scene.skyBox.show = false;
    window.viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#0a0c10");

    window.viewer.camera.setView({{
      destination: Cesium.Cartesian3.fromDegrees({center_lon}, {center_lat}, 15000),
      orientation: {{ heading: 0, pitch: Cesium.Math.toRadians(-45), roll: 0 }}
    }});

    setLoading("Loading buildings...", 50, "Parsing GeoJSON");

    try {{
      const dataSource = await Cesium.GeoJsonDataSource.load(
        "buildings.geojson",
        {{ clampToGround: true }}
      );

      const entities = dataSource.entities.values;
      let count = 0;

      setLoading("Placing buildings...", 80, "Setting heights");

      for (const entity of entities) {{
        if (entity.polygon) {{
          const h = entity.properties?.height?.getValue() || 10;
          // CLAMP_TO_GROUND + RELATIVE_TO_GROUND is the reliable approach
          // for heightmap-1.0 terrain format
          entity.polygon.heightReference = Cesium.HeightReference.CLAMP_TO_GROUND;
          entity.polygon.extrudedHeightReference = Cesium.HeightReference.RELATIVE_TO_GROUND;
          entity.polygon.extrudedHeight = h;
          entity.polygon.height = undefined;
          entity.polygon.fill = true;
          entity.polygon.material = getBuildingColor(h);
          entity.polygon.outline = true;
          entity.polygon.outlineColor = new Cesium.Color(0.20, 0.20, 0.20, 1.0);
          entity.polygon.outlineWidth = 1;
          count++;
        }}
      }}

      window.viewer.dataSources.add(dataSource);

      setLoading("Ready!", 100, `${{count}} buildings loaded`);
      setTimeout(() => {{
        document.getElementById("loadingOverlay").style.display = "none";
      }}, 400);

      document.getElementById("status").textContent = `Offline — ${{count}} buildings`;

    }} catch(e) {{
      document.getElementById("loadingOverlay").style.display = "none";
      document.getElementById("status").textContent = "Error: " + e.message;
      console.error(e);
    }}
  }}

  init();
  </script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    print(f"  Viewer HTML written to {output_path}")
    return output_path