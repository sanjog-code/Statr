"""
PulseBeat Local Web Server & Analytics API
Serves the dark-mode analytics dashboard and REST API endpoints
using Python's standard library. Zero external dependencies.
"""

import os
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional

import database
from auth import load_env

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def _send_json(self, data: any, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Parse 'days' parameter
        days_param = query.get("days", [None])[0]
        days: Optional[int] = int(days_param) if days_param and days_param.isdigit() else None
        limit_param = query.get("limit", [10])[0]
        limit = int(limit_param) if str(limit_param).isdigit() else 10

        # REST API Routes
        if path == "/api/summary":
            stats = database.get_summary_stats(days=days)
            self._send_json(stats)
            return

        elif path == "/api/tracks":
            tracks = database.get_top_tracks(days=days, limit=limit)
            self._send_json(tracks)
            return

        elif path == "/api/artists":
            artists = database.get_top_artists(days=days, limit=limit)
            self._send_json(artists)
            return

        elif path == "/api/playlists":
            playlists = database.get_playlist_analytics(days=days)
            self._send_json(playlists)
            return

        elif path == "/api/hourly":
            hourly = database.get_hourly_heatmap(days=days)
            self._send_json(hourly)
            return

        elif path == "/api/recent":
            recent = database.get_recent_events(limit=limit if limit <= 100 else 30)
            self._send_json(recent)
            return

        elif path == "/api/status":
            env = load_env()
            has_client = bool(env.get("SPOTIFY_CLIENT_ID") and "your_client_id" not in env.get("SPOTIFY_CLIENT_ID", ""))
            token_cached = os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token_cache.json"))
            self._send_json({
                "configured": has_client,
                "authenticated": token_cached,
                "database_ready": True
            })
            return

        # Fallback to serving static dashboard files from WEB_DIR
        return super().do_GET()

    def log_message(self, format, *args):
        # Mute spammy HTTP asset requests in console
        return


def start_server(port: int = 8888):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"[Dashboard] Serving Web Analytics UI at http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    database.init_db()
    start_server(8888)
