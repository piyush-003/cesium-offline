#!/bin/bash
# CesiumOffline — One-time setup script
# Run this once before using run.py

set -e

echo ""
echo "============================================"
echo "  CesiumOffline — Setup"
echo "============================================"
echo ""

# Check Python
python3 --version || { echo "ERROR: Python 3 required"; exit 1; }

# Check Node.js
if ! command -v node &>/dev/null; then
    echo "Installing Node.js..."
    sudo apt install -y nodejs
fi
echo "✅ Node.js: $(node --version)"

# Check GDAL
if ! command -v gdalinfo &>/dev/null; then
    echo "Installing GDAL..."
    sudo apt install -y gdal-bin python3-gdal
fi
echo "✅ GDAL: $(gdalinfo --version)"

# Check Docker
if ! command -v docker &>/dev/null; then
    echo "Installing Docker..."
    sudo apt install -y docker.io
    sudo usermod -aG docker $USER
    echo "⚠️  Added $USER to docker group. Please log out and back in."
fi
echo "✅ Docker: $(docker --version)"

# Pull CTB image
echo ""
echo "Pulling Cesium Terrain Builder Docker image..."
docker pull homme/cesium-terrain-builder
echo "✅ CTB image ready"

# Install Python deps
echo ""
echo "Installing Python dependencies..."
pip3 install -r requirements.txt
echo "✅ Python deps installed"

# Create projects directory
mkdir -p projects
echo "✅ projects/ directory ready"

echo ""
echo "============================================"
echo "  Setup complete!"
echo ""
echo "  Usage:"
echo '  python3 run.py --bounds "lat_min,lon_min,lat_max,lon_max" --name myproject'
echo ""
echo "  Example (Kashmir):"
echo '  python3 run.py --bounds "34.08154,73.58274,34.52480,74.13570" --name kashmir'
echo "============================================"
echo ""