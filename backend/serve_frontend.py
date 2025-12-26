"""Simple HTTP server to serve the frontend on port 8080."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys
from pathlib import Path

# Determine the frontend directory dynamically
# Try to find frontend directory relative to this script
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent

# Check if frontend exists at project_root
frontend_dir = project_root / 'frontend'
if not frontend_dir.exists():
    # Fallback to hardcoded path for backward compatibility
    frontend_dir = Path('/home/developer/AutoAltText/frontend')
    if not frontend_dir.exists():
        print("Error: Frontend directory not found!")
        print(f"Tried: {project_root / 'frontend'}")
        print(f"Tried: {frontend_dir}")
        sys.exit(1)

os.chdir(str(frontend_dir))
print(f"Serving frontend from: {frontend_dir}")
server = HTTPServer(('0.0.0.0', 8080), SimpleHTTPRequestHandler)
print("Frontend server running at http://localhost:8080")
print("Open http://localhost:8080/home.html in your browser")
server.serve_forever()
