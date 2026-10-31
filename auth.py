"""
PulseBeat Authentication Module
Handles Spotify OAuth 2.0 with offline access, automatic token refresh,
and a self-contained local callback server. Zero external dependencies.
"""

import os
import json
import time
import base64
import urllib.parse
import urllib.request
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".token_cache.json")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

SCOPES = [
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
    "playlist-read-private",
    "playlist-read-collaborative"
]


def load_env() -> dict:
    config = {
        "SPOTIFY_CLIENT_ID": "",
        "SPOTIFY_CLIENT_SECRET": "",
        "SPOTIFY_REDIRECT_URI": "http://localhost:8888/callback",
        "DASHBOARD_PORT": "8888"
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip().strip('"').strip("'")
    return config


class CallbackServer(BaseHTTPRequestHandler):
    auth_code = None

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if "code" in params:
            CallbackServer.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>PulseBeat Connected</title>
                <style>
                    body {
                        background: #121212;
                        color: #ffffff;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .card {
                        background: #1e1e1e;
                        border: 1px solid #282828;
                        border-radius: 16px;
                        padding: 40px;
                        text-align: center;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                        max-width: 420px;
                    }
                    h1 { color: #1DB954; margin-bottom: 8px; font-size: 24px; }
                    p { color: #b3b3b3; font-size: 14px; line-height: 1.5; }
                    .badge {
                        display: inline-block;
                        background: #1DB954;
                        color: #000;
                        font-weight: bold;
                        padding: 6px 14px;
                        border-radius: 20px;
                        margin-top: 15px;
                        font-size: 13px;
                    }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>PulseBeat Connected</h1>
                    <p>Authorization code received. Token exchange complete.</p>
                    <p>You can close this tab and return to your terminal.</p>
                    <span class="badge">Active Tracking Ready</span>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Authorization failed or denied.")

    def log_message(self, format, *args):
        # Silence default HTTP server logging
        return


def save_tokens(token_data: dict):
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600) - 60
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


def load_cached_tokens() -> dict:
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    payload = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }).encode()
    
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=payload,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        if "refresh_token" not in data:
            data["refresh_token"] = refresh_token
        save_tokens(data)
        return data


def get_access_token() -> str:
    tokens = load_cached_tokens()
    env = load_env()
    client_id = env.get("SPOTIFY_CLIENT_ID")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET")
    
    if not tokens or "refresh_token" not in tokens:
        raise ValueError("No Spotify authentication found. Please run 'python main.py auth' first.")
    
    # Check expiry
    if time.time() >= tokens.get("expires_at", 0):
        print("[Auth] Access token expired, refreshing with Spotify...")
        tokens = refresh_access_token(client_id, client_secret, tokens["refresh_token"])
    
    return tokens["access_token"]


def authenticate_interactive():
    env = load_env()
    client_id = env.get("SPOTIFY_CLIENT_ID")
    client_secret = env.get("SPOTIFY_CLIENT_SECRET")
    redirect_uri = env.get("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback")
    
    if not client_id or not client_secret or "your_client_id" in client_id:
        print("\n" + "="*60)
        print("  SPOTIFY SETUP REQUIRED")
        print("="*60)
        print("1. Go to https://developer.spotify.com/dashboard")
        print("2. Create an App (name it 'PulseBeat Analytics')")
        print(f"3. In App Settings, add Redirect URI: {redirect_uri}")
        print("4. Copy Client ID and Client Secret into your .env file or enter them now:")
        print("="*60 + "\n")
        
        entered_id = input("Enter Spotify Client ID: ").strip()
        entered_secret = input("Enter Spotify Client Secret: ").strip()
        
        if not entered_id or not entered_secret:
            print("Client credentials cannot be empty.")
            return False
            
        # Save to .env
        env_content = f"""# Spotify API Credentials
SPOTIFY_CLIENT_ID={entered_id}
SPOTIFY_CLIENT_SECRET={entered_secret}
SPOTIFY_REDIRECT_URI={redirect_uri}
POLL_INTERVAL_ACTIVE=25
POLL_INTERVAL_IDLE=60
DASHBOARD_PORT=8888
"""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(env_content)
        client_id = entered_id
        client_secret = entered_secret

    # Parse port for local redirect server
    parsed_redirect = urllib.parse.urlparse(redirect_uri)
    port = parsed_redirect.port or 8888
    
    server = HTTPServer(("127.0.0.1", port), CallbackServer)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.daemon = True
    server_thread.start()
    
    auth_params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(SCOPES),
        "show_dialog": "true"
    }
    auth_url = f"https://accounts.spotify.com/authorize?{urllib.parse.urlencode(auth_params)}"
    
    print("\nOpening your browser to authorize PulseBeat with Spotify...")
    print(f"If browser does not open, visit this URL:\n{auth_url}\n")
    webbrowser.open(auth_url)
    
    print("Waiting for Spotify authorization callback...")
    server_thread.join(timeout=120)
    
    if not CallbackServer.auth_code:
        print("Timed out or failed to receive authorization code.")
        return False
        
    code = CallbackServer.auth_code
    print("Code received! Exchanging for tokens...")
    
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
            print("Successfully authenticated with Spotify! Tokens cached safely.")
            return True
    except Exception as e:
        print(f"Error exchanging tokens: {e}")
        return False
