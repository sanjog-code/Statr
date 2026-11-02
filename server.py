"""
Statr Local Web Server & Analytics API
Serves the dark-mode analytics dashboard and REST API endpoints
using Python's standard library. Zero external dependencies.
"""

import os
import json
import base64
import time
import urllib.parse
import urllib.request
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional, Dict, Any

import database
from auth import load_env, save_tokens, CONFIG_FILE


from poller import SpotifyPoller
import threading

poller_instance = None
poller_thread = None

def ensure_poller_running():
    global poller_instance, poller_thread
    from auth import load_cached_tokens
    tokens = load_cached_tokens()
    if tokens and tokens.get("refresh_token") and (poller_thread is None or not poller_thread.is_alive()):
        try:
            poller_instance = SpotifyPoller()
            poller_thread = threading.Thread(target=poller_instance.start, daemon=True)
            poller_thread.start()
            print("[Daemon] Embedded background Spotify poller activated.")
        except Exception as e:
            print(f"[Daemon] Could not start poller: {e}")

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

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

        elif path == "/api/albums":
            albums = database.get_top_albums(days=days, limit=limit)
            self._send_json(albums)
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

        elif path == "/api/obscurity":
            obs = database.get_obscurity_metrics(days=days)
            self._send_json(obs)
            return

        elif path == "/api/fanrating":
            fan = database.get_fan_rating(days=days)
            self._send_json(fan)
            return

        elif path == "/api/auth/login":
            env = load_env()
            client_id = env.get("SPOTIFY_CLIENT_ID", "").strip()
            redirect_uri = env.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback").strip()
            if not client_id or "your_client_id" in client_id:
                self._send_json({"error": "unconfigured", "message": "Spotify Client ID not configured yet"}, status=400)
                return
            from auth import SCOPES
            auth_params = {
                "client_id": client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "scope": " ".join(SCOPES),
                "show_dialog": "false"
            }
            auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(auth_params)}"
            self.send_response(302)
            self.send_header("Location", auth_url)
            self.end_headers()
            return

        elif path == "/api/me":
            try:
                from auth import get_access_token
                token = get_access_token()
                req = urllib.request.Request("https://api.spotify.com/v1/me", headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req) as resp:
                    profile = json.loads(resp.read().decode())
                    
                now_playing = None
                try:
                    req_np = urllib.request.Request("https://api.spotify.com/v1/me/player", headers={"Authorization": f"Bearer {token}"})
                    with urllib.request.urlopen(req_np) as np_resp:
                        if np_resp.status == 200:
                            np_data = json.loads(np_resp.read().decode())
                            if np_data and np_data.get("is_playing") and np_data.get("item"):
                                item = np_data["item"]
                                now_playing = {
                                    "name": item.get("name"),
                                    "artists": ", ".join(a["name"] for a in item.get("artists", [])),
                                    "progress_ms": np_data.get("progress_ms"),
                                    "duration_ms": item.get("duration_ms"),
                                    "device": np_data.get("device", {}).get("name", "Device")
                                }
                except Exception:
                    pass
                    
                self._send_json({
                    "authenticated": True,
                    "display_name": profile.get("display_name", "Spotify User"),
                    "id": profile.get("id"),
                    "email": profile.get("email"),
                    "avatar": profile.get("images", [{}])[0].get("url", "") if profile.get("images") else "",
                    "daemon_active": poller_thread is not None and poller_thread.is_alive(),
                    "now_playing": now_playing
                })
                return
            except Exception as e:
                self._send_json({"authenticated": False, "error": str(e)})
                return

        elif path == "/api/status":
            env = load_env()
            has_client = bool(env.get("SPOTIFY_CLIENT_ID") and "your_client_id" not in env.get("SPOTIFY_CLIENT_ID", ""))
            token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token_cache.json")
            token_cached = os.path.exists(token_file)
            summary = database.get_summary_stats()
            self._send_json({
                "configured": has_client,
                "authenticated": token_cached,
                "database_ready": True,
                "total_events": summary.get("total_events", 0),
                "client_id": env.get("SPOTIFY_CLIENT_ID", "")[:6] + "..." if has_client else ""
            })
            return

        # OAuth Callback endpoint (Handles Spotify Redirect URI)
        elif path == "/callback":
            code = query.get("code", [None])[0]
            error = query.get("error", [None])[0]

            if code:
                env = load_env()
                client_id = env.get("SPOTIFY_CLIENT_ID", "")
                client_secret = env.get("SPOTIFY_CLIENT_SECRET", "")
                redirect_uri = env.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
                
                success = False
                if client_id and client_secret and "your_client_id" not in client_id:
                    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
                    payload = urllib.parse.urlencode({
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": redirect_uri
                    }).encode()
                    req = urllib.request.Request(
                        "https://accounts.spotify.com/api/token",
                        data=payload,
                        headers={
                            "Authorization": f"Basic {auth_header}",
                            "Content-Type": "application/x-www-form-urlencoded"
                        }
                    )
                    try:
                        with urllib.request.urlopen(req) as resp:
                            data = json.loads(resp.read().decode())
                            save_tokens(data)
                            success = True
                    except Exception as e:
                        print(f"[OAuth] Code exchange error: {e}")

                html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Statr Connected</title>
                    <style>
                        body {{
                            background: #07080a;
                            color: #ffffff;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            height: 100vh;
                            margin: 0;
                        }}
                        .card {{
                            background: rgba(22, 25, 35, 0.85);
                            border: 1px solid rgba(255, 255, 255, 0.12);
                            border-radius: 20px;
                            padding: 40px;
                            text-align: center;
                            box-shadow: 0 20px 50px rgba(0,0,0,0.7);
                            max-width: 440px;
                        }}
                        h1 {{ font-size: 22px; margin-bottom: 12px; color: #30D158; }}
                        p {{ color: #94A3B8; font-size: 14px; line-height: 1.5; }}
                        .btn {{
                            display: inline-block;
                            background: #FA2D48;
                            color: #FFFFFF;
                            text-decoration: none;
                            padding: 12px 24px;
                            border-radius: 980px;
                            font-weight: 700;
                            font-size: 14px;
                            margin-top: 20px;
                        }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>{"Spotify Connected!" if success else "Authorization Code Received"}</h1>
                        <p>{"Your Spotify tokens have been exchanged and cached securely. Background ingestion is ready." if success else "The authorization code was captured. Returning to Statr..."}</p>
                        <a href="/?code={code}" class="btn">Open Dashboard</a>
                    </div>
                    <script>
                        setTimeout(() => {{
                            window.location.href = '/?code={code}';
                        }}, 1200);
                    </script>
                </body>
                </html>
                """
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
                return
            elif error:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h3>Spotify Authorization Denied: {error}</h3><p><a href='/'>Return to Statr</a></p>".encode("utf-8"))
                return

        # Fallback to serving static dashboard files from WEB_DIR
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except Exception:
            payload = {}

        if path == "/api/seed":
            from main import cmd_demo_data
            cmd_demo_data()
            summary = database.get_summary_stats()
            self._send_json({
                "success": True,
                "message": "Demo data populated successfully",
                "summary": summary
            })
            return

        elif path == "/api/reset":
            database.clear_database()
            self._send_json({
                "success": True,
                "message": "Database cleared successfully"
            })
            return

        elif path == "/api/auth/token":
            access_token = payload.get("access_token")
            if not access_token:
                self._send_json({"error": "access_token required"}, status=400)
                return
            save_tokens(payload)
            ensure_poller_running()
            self._send_json({"success": True, "message": "Tokens saved and poller activated"})
            return

        elif path == "/api/auth/disconnect":
            from auth import clear_cached_tokens
            clear_cached_tokens()
            if poller_instance:
                poller_instance.running = False
            self._send_json({"success": True, "message": "Disconnected from Spotify"})
            return

        elif path == "/api/config":
            client_id = payload.get("client_id", "").strip()
            client_secret = payload.get("client_secret", "").strip()
            redirect_uri = payload.get("redirect_uri", "http://localhost:8888/callback").strip()

            if not client_id or not client_secret:
                self._send_json({"error": "client_id and client_secret are required"}, status=400)
                return

            env_content = f"""# Spotify API Credentials
SPOTIFY_CLIENT_ID={client_id}
SPOTIFY_CLIENT_SECRET={client_secret}
SPOTIFY_REDIRECT_URI={redirect_uri}
POLL_INTERVAL_ACTIVE=25
POLL_INTERVAL_IDLE=60
DASHBOARD_PORT=8888
"""
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(env_content)

            self._send_json({"success": True, "message": "Credentials saved to .env"})
            return

        self._send_json({"error": "Endpoint not found"}, status=404)

    def log_message(self, format, *args):
        # Mute spammy HTTP asset requests in console
        return


def start_server(port: int = 8888):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, DashboardHandler)
    ensure_poller_running()
    print(f"[Dashboard] Serving Web Analytics UI at http://localhost:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    database.init_db()
    start_server(8888)
