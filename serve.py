#!/usr/bin/env python3
"""
serve.py — Start the CesiumOffline FastAPI server.

Usage:
    python3 serve.py              # production (serves built frontend)
    python3 serve.py --dev        # dev mode (hot reload)
    python3 serve.py --port 9000  # custom port
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def build_frontend():
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").exists():
        print("Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=frontend, check=True)
    print("Building frontend...")
    subprocess.run(["npm", "run", "build"], cwd=frontend, check=True)
    print("✅ Frontend built")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Development mode with hot reload")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--skip-build", action="store_true", help="Skip frontend build")
    args = parser.parse_args()

    if not args.dev and not args.skip_build:
        dist = ROOT / "frontend" / "dist"
        if not dist.exists():
            build_frontend()

    print(f"\n{'='*50}")
    print(f"  CesiumOffline API + UI")
    print(f"  http://localhost:{args.port}")
    print(f"  API docs: http://localhost:{args.port}/docs")
    print(f"{'='*50}\n")

    cmd = [
        sys.executable, "-m", "uvicorn",
        "api.main:app",
        "--host", "0.0.0.0",
        "--port", str(args.port),
    ]
    if args.dev:
        cmd.append("--reload")

    subprocess.run(cmd, cwd=ROOT)


if __name__ == "__main__":
    main()
