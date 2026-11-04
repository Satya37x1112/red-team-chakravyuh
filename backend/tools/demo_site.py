"""Fragile demo target for the DDoS lab — a tiny single-threaded HTTP site.

Runs on 127.0.0.1:3000 by default. It is deliberately easy to overwhelm:
single-threaded, a small accept backlog, and a little per-request work. Point the
Locust DDoS path at it and watch it stop answering new connections under load.

Authorized, isolated-lab use only. Run with:  python demo_site.py [port]
"""
from __future__ import annotations

import socketserver
import sys
import time
from http.server import BaseHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000

_PAGE = (
    "<!doctype html><html><head><meta charset=utf-8>"
    "<title>Demo Site :{port}</title></head>"
    "<body style=\"font-family:system-ui;background:#0b0f17;color:#e5e7eb;text-align:center;padding:4rem\">"
    "<h1>Demo site is UP</h1><p>Running on 127.0.0.1:{port} - a fragile single-threaded target.</p>"
    "</body></html>"
)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        time.sleep(0.03)  # simulate a little work so the server saturates under load
        body = _PAGE.format(port=PORT).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # quiet
        pass


class FragileServer(socketserver.TCPServer):
    # Single-threaded (no ThreadingMixIn) and a small accept queue, so a flood of
    # concurrent connections fills the backlog and new clients get refused/time out.
    allow_reuse_address = True
    request_queue_size = 5


if __name__ == "__main__":
    print(f"demo site listening on http://127.0.0.1:{PORT}  (single-threaded, fragile)")
    with FragileServer(("127.0.0.1", PORT), Handler) as httpd:
        httpd.serve_forever()
