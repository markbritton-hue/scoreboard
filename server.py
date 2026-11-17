#!/usr/bin/env python3
"""Scoreboard server - serves static files and stores live settings in memory."""

import json, os, socket, sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 9000
live_data = {}

class Handler(SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split('?')[0] == '/local-live.json':
            body = json.dumps(live_data).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.split('?')[0] == '/local-live.json':
            global live_data
            length = int(self.headers.get('Content-Length', 0))
            try:
                live_data = json.loads(self.rfile.read(length))
            except Exception:
                self.send_response(400)
                self._cors()
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            self.wfile.write(b'{}')
        else:
            self.send_response(405)
            self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, fmt, *args):
        pass  # silence per-request logging

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        return s.getsockname()[0]
    except Exception:
        return 'localhost'
    finally:
        s.close()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    ip = get_lan_ip()
    print(f"Setup page:  http://localhost:{port}/setup.html")
    print(f"Overlay:     http://localhost:{port}/mascot.html")
    print(f"From another computer on this network, try: http://{ip}:{port}/mascot.html")
    print("Press Ctrl+C to stop.")
    HTTPServer(('0.0.0.0', port), Handler).serve_forever()
