"""Simple HTTP server to serve the frontend on port 8080."""
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

os.chdir('/home/developer/AutoAltText/frontend')
server = HTTPServer(('0.0.0.0', 8080), SimpleHTTPRequestHandler)
print("Frontend server running at http://localhost:8080")
print("Open http://localhost:8080/home.html in your browser")
server.serve_forever()
