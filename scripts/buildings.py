"""
buildings.py — Download OSM building footprints for the AOI using Overpass API.
Outputs a GeoJSON file with height properties.
"""

import json
import sys
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 180  # seconds


def download_buildings(lat_min, lon_min, lat_max, lon_max, output_path):
    """Download OSM buildings and save as GeoJSON."""
    output_path = Path(output_path)

    query = f"""
[out:json][timeout:{OVERPASS_TIMEOUT}];
(
  way["building"]({lat_min},{lon_min},{lat_max},{lon_max});
  relation["building"]({lat_min},{lon_min},{lat_max},{lon_max});
);
out body;
>;
out skel qt;
"""

    print(f"  Querying Overpass API for buildings...")
    print(f"  Bounds: {lat_min},{lon_min} → {lat_max},{lon_max}")

    # Try multiple Overpass endpoints with retries
    ENDPOINTS = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    ]
    raw = None
    for attempt in range(3):
        for endpoint in ENDPOINTS:
            try:
                print(f"  Trying {endpoint} (attempt {attempt+1})...")
                r = requests.post(endpoint, data={"data": query},
                                  timeout=OVERPASS_TIMEOUT + 30)
                r.raise_for_status()
                raw = r.json()
                break
            except Exception as e:
                print(f"  ⚠️  Failed: {e}")
                import time; time.sleep(5)
        if raw is not None:
            break
    if raw is None:
        raise RuntimeError("All Overpass API endpoints failed after 3 attempts.")

    # Parse OSM elements into GeoJSON
    print(f"  Processing {len(raw.get('elements', []))} OSM elements...")

    nodes = {}
    ways = []

    for el in raw.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])
        elif el["type"] == "way" and "tags" in el:
            if "building" in el["tags"]:
                ways.append(el)

    features = []
    for way in ways:
        if "nodes" not in way:
            continue
        coords = [nodes[n] for n in way["nodes"] if n in nodes]
        if len(coords) < 3:
            continue
        # Close the ring
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        tags = way.get("tags", {})

        # Determine height
        height = 10  # default
        if "height" in tags:
            try:
                height = float(tags["height"].replace("m", "").strip())
            except:
                pass
        elif "building:levels" in tags:
            try:
                height = float(tags["building:levels"]) * 3.0
            except:
                pass

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [coords]
            },
            "properties": {
                "height": height,
                "building": tags.get("building", "yes"),
                "name": tags.get("name", ""),
                "osm_id": way["id"]
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(output_path, "w") as f:
        json.dump(geojson, f)

    size_kb = output_path.stat().st_size / 1024
    print(f"  ✅ Buildings saved: {len(features)} buildings → {output_path} ({size_kb:.0f} KB)")