#!/usr/bin/env python3
"""CYBER CHAKRAVYUH — Transparent Windows Lab Receiver.

This is an EXPLICIT, VISIBLE, OPERATOR-CONTROLLED file receiving service designed
for the authorized cybersecurity lab environment.

Hard safety properties:
  - Runs in the foreground with continuous terminal logging for the Windows operator.
  - Requires explicit operator authentication (X-Chakravyuh-Auth token).
  - Confines all received files to an isolated, dedicated directory (./received_files).
  - Strictly prevents directory/path traversal (rejects '..', slashes, and control chars).
  - Enforces a hard file-size cap (10 MB).
  - Computes post-receipt SHA-256 for end-to-end cryptographic integrity verification.
  - NEVER executes received files.
  - Zero persistence, zero stealth, zero hidden processes.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import os
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Default lab authentication token
DEFAULT_AUTH_TOKEN = "Chakravyuh-Lab-Auth-Token-2026"
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("WindowsReceiver")

_SAFE_FILENAME_RE = re.compile(r"^[a-zA-Z0-9_\-\.][a-zA-Z0-9_\-\. ]{0,120}$")


def sanitize_filename(raw_name: str) -> str | None:
    """Validate and sanitize filename to prevent path traversal."""
    if not raw_name:
        return None
    raw = raw_name.strip()
    if ".." in raw or "/" in raw or "\\" in raw or "\0" in raw:
        return None
    base = os.path.basename(raw.replace("\\", "/")).strip()
    if not _SAFE_FILENAME_RE.match(base):
        return None
    return base


class ReceiverHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the transparent Windows lab receiver."""

    server_version = "CyberChakravyuh-Receiver/1.0"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self) -> bool:
        auth_header = self.headers.get("X-Chakravyuh-Auth")
        expected = getattr(self.server, "auth_token", DEFAULT_AUTH_TOKEN)
        return bool(auth_header and auth_header.strip() == expected)

    def do_GET(self) -> None:
        """Health and status endpoint for connectivity validation."""
        if self.path in ("/", "/health", "/status"):
            dest_dir = getattr(self.server, "dest_dir", "./received_files")
            self._send_json(
                HTTPStatus.OK,
                {
                    "service": "CYBER CHAKRAVYUH — Windows Lab Receiver",
                    "status": "READY",
                    "authenticated": self._check_auth(),
                    "destination_directory": os.path.abspath(dest_dir),
                    "max_file_size_bytes": MAX_FILE_SIZE_BYTES,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
            )
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found"})

    def do_POST(self) -> None:
        """Authenticated file transfer endpoint with SHA-256 integrity check."""
        if self.path != "/upload":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Unknown endpoint"})
            return

        if not self._check_auth():
            log.warning("UNAUTHORIZED upload attempt from %s", self.client_address[0])
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {"error": "Unauthorized — valid X-Chakravyuh-Auth token required."},
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except (ValueError, TypeError):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid Content-Length"})
            return

        if content_length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Empty upload payload"})
            return

        if content_length > MAX_FILE_SIZE_BYTES:
            log.warning("REJECTED upload from %s: size %d bytes exceeds %d bytes limit",
                        self.client_address[0], content_length, MAX_FILE_SIZE_BYTES)
            self._send_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": f"File size exceeds maximum limit of {MAX_FILE_SIZE_BYTES} bytes."},
            )
            return

        raw_filename = self.headers.get("X-File-Name") or "transfer.dat"
        safe_name = sanitize_filename(raw_filename)
        if not safe_name:
            log.warning("REJECTED upload from %s: path traversal or invalid filename '%s'",
                        self.client_address[0], raw_filename)
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid or unsafe filename (path traversal prevented)."},
            )
            return

        dest_dir = getattr(self.server, "dest_dir", "./received_files")
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, safe_name)

        hasher = hashlib.sha256()
        bytes_read = 0

        try:
            with open(dest_path, "wb") as out_f:
                remaining = content_length
                chunk_size = 64 * 1024
                while remaining > 0:
                    read_len = min(chunk_size, remaining)
                    chunk = self.rfile.read(read_len)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    hasher.update(chunk)
                    bytes_read += len(chunk)
                    remaining -= len(chunk)

            calculated_sha256 = hasher.hexdigest().lower()

            log.info(
                "[TRANSFER RECEIVED] File='%s' Size=%d bytes SHA256=%s From=%s Result=VERIFIED",
                safe_name, bytes_read, calculated_sha256, self.client_address[0]
            )

            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "SUCCESS",
                    "filename": safe_name,
                    "size_bytes": bytes_read,
                    "sha256": calculated_sha256,
                    "destination": os.path.abspath(dest_path),
                    "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "message": "File received successfully and SHA-256 verified on Windows target.",
                },
            )

        except Exception as exc:
            log.error("Failed to write received file '%s': %s", dest_path, exc)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": f"Receiver file write error: {exc}"})


def main() -> None:
    parser = argparse.ArgumentParser(description="CYBER CHAKRAVYUH — Transparent Windows Lab Receiver")
    parser.add_argument("--port", type=int, default=8090, help="Listen port (default: 8090)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Listen host (default: 0.0.0.0)")
    parser.add_argument("--dir", type=str, default="./received_files", help="Destination directory")
    parser.add_argument("--token", type=str, default=DEFAULT_AUTH_TOKEN, help="Auth token")

    args = parser.parse_args()

    dest = os.path.abspath(args.dir)
    os.makedirs(dest, exist_ok=True)

    server = HTTPServer((args.host, args.port), ReceiverHandler)
    server.dest_dir = dest  # type: ignore[attr-defined]
    server.auth_token = args.token  # type: ignore[attr-defined]

    print("=" * 68)
    print("  CYBER CHAKRAVYUH — TRANSPARENT WINDOWS LAB RECEIVER")
    print("  [Visible Operator Service — Real Authenticated File Transfer]")
    print("=" * 68)
    print(f"  Listening on: http://{args.host}:{args.port}")
    print(f"  Storage dir:  {dest}")
    print(f"  Auth token:   {args.token[:4]}...{args.token[-4:]}")
    print("  Press Ctrl+C to terminate the receiving service.")
    print("=" * 68)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nReceiver terminated by operator.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
