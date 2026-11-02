"""
Statr Active Ingestion Daemon
Continuously polls Spotify playback state to capture complete playlist contexts,
detect skips vs completions, and maintain zero-loss listening history.
"""

import time
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from auth import get_access_token, load_env
import database


class SpotifyPoller:
    def __init__(self):
        env = load_env()
        self.active_interval = int(env.get("POLL_INTERVAL_ACTIVE", 25))
        self.idle_interval = int(env.get("POLL_INTERVAL_IDLE", 60))
        
        # State tracking
        self.current_track: Optional[Dict[str, Any]] = None
        self.track_start_time: Optional[datetime] = None
        self.max_progress_ms: int = 0
        self.last_context: Optional[Dict[str, str]] = None
        self.last_device: Optional[Dict[str, str]] = None
        self.running: bool = False
        self.playlist_cache: Dict[str, str] = {}  # id -> name

    def _api_get(self, url: str) -> Optional[Dict[str, Any]]:
        token = get_access_token()
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status == 204:
                    return None
                data = resp.read()
                return json.loads(data.decode("utf-8")) if data else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", 10))
                print(f"[Poller] Rate limited by Spotify. Backing off for {retry_after}s...")
                time.sleep(retry_after)
            elif e.code == 401:
                print("[Poller] Token invalid or expired during request. Retrying...")
            else:
                print(f"[Poller] API error {e.code}: {e.reason}")
            return None
        except Exception as e:
            print(f"[Poller] Network error: {e}")
            return None

    def _resolve_playlist_name(self, playlist_id: str) -> str:
        # Check in-memory cache
        if playlist_id in self.playlist_cache:
            return self.playlist_cache[playlist_id]
        
        # Check SQLite DB
        cached_name = database.get_playlist_name(playlist_id)
        if cached_name:
            self.playlist_cache[playlist_id] = cached_name
            return cached_name
            
        # Fetch from Spotify API
        data = self._api_get(f"https://api.spotify.com/v1/playlists/{playlist_id}?fields=id,name,owner,images,tracks.total")
        if data and "name" in data:
            name = data["name"]
            owner = data.get("owner", {}).get("display_name", "")
            images = data.get("images", [])
            image_url = images[0]["url"] if images else ""
            total_tracks = data.get("tracks", {}).get("total", 0)
            
            database.save_playlist(playlist_id, name, owner, image_url, total_tracks)
            self.playlist_cache[playlist_id] = name
            return name
            
        return "Unknown Playlist"

    def _flush_current_track(self):
        """Called when track transitions or playback stops to log the completed event."""
        if not self.current_track:
            return
            
        track_id = self.current_track["id"]
        duration_ms = self.current_track.get("duration_ms", 180000)
        track_name = self.current_track.get("name", "Unknown Track")
        artist_name = ", ".join(a["name"] for a in self.current_track.get("artists", []))
        
        # Skip detection threshold: Played for less than 30 seconds or less than 20% of duration
        is_skip = self.max_progress_ms < 30000 or (self.max_progress_ms / max(1, duration_ms) < 0.20)
        
        context_type = self.last_context.get("type", "unknown") if self.last_context else "direct"
        context_uri = self.last_context.get("uri", "") if self.last_context else ""
        context_name = self.last_context.get("name", "") if self.last_context else ""
        
        device_name = self.last_device.get("name", "Unknown Device") if self.last_device else "Unknown"
        device_type = self.last_device.get("type", "Device") if self.last_device else "Device"
        
        played_at_str = (self.track_start_time or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S")
        
        database.log_event(
            track_id=track_id,
            context_type=context_type,
            context_uri=context_uri,
            context_name=context_name,
            played_at=played_at_str,
            played_ms=self.max_progress_ms,
            is_skip=is_skip,
            device_name=device_name,
            device_type=device_type
        )
        
        seconds_heard = int(self.max_progress_ms / 1000)
        mins = seconds_heard // 60
        secs = seconds_heard % 60
        
        if is_skip:
            print(f"  ⏩ [SKIP DETECTED] '{track_name}' by {artist_name} (skipped at {mins}m {secs}s) [{context_name or context_type}]")
        else:
            print(f"  🎵 [LISTEN LOGGED] '{track_name}' by {artist_name} ({mins}m {secs}s) [{context_name or context_type}]")
            
        # Reset state
        self.current_track = None
        self.track_start_time = None
        self.max_progress_ms = 0

    def poll_once(self) -> bool:
        """Polls Spotify once. Returns True if music is playing, False if idle."""
        state = self._api_get("https://api.spotify.com/v1/me/player")
        
        if not state or not state.get("is_playing") or not state.get("item"):
            if self.current_track:
                # Playback was stopped / paused for extended period
                self._flush_current_track()
            return False
            
        item = state["item"]
        track_id = item.get("id")
        if not track_id:
            return False
            
        progress_ms = state.get("progress_ms", 0)
        duration_ms = item.get("duration_ms", 0)
        track_name = item.get("name", "Unknown")
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        album = item.get("album", {}).get("name", "")
        popularity = item.get("popularity", 0)
        images = item.get("album", {}).get("images", [])
        image_url = images[0]["url"] if images else ""
        
        # Save track metadata to master table
        database.save_track(track_id, track_name, artists, album, duration_ms, popularity, image_url)
        
        # Parse context (playlist / album / artist radio)
        context = state.get("context")
        context_type = context.get("type", "direct") if context else "direct"
        context_uri = context.get("uri", "") if context else ""
        context_name = ""
        
        if context_type == "playlist" and context_uri:
            playlist_id = context_uri.split(":")[-1]
            context_name = self._resolve_playlist_name(playlist_id)
        elif context_type == "album":
            context_name = album
        elif context_type == "artist":
            context_name = f"{artists} Radio"
        else:
            context_name = "Liked Songs / Library"
            
        # Parse device
        device = state.get("device", {})
        device_name = device.get("name", "Unknown")
        device_type = device.get("type", "Speaker")
        
        # Check track change
        if not self.current_track or self.current_track.get("id") != track_id:
            if self.current_track:
                self._flush_current_track()
                
            self.current_track = item
            self.track_start_time = datetime.now(timezone.utc)
            self.max_progress_ms = progress_ms
            self.last_context = {"type": context_type, "uri": context_uri, "name": context_name}
            self.last_device = {"name": device_name, "type": device_type}
            
            print(f"[Playing] '{track_name}' - {artists} on {device_name} (Context: {context_name})")
        else:
            # Continuing same track
            self.max_progress_ms = max(self.max_progress_ms, progress_ms)
            if context_name:
                self.last_context["name"] = context_name
                
        return True

    def start(self):
        self.running = True
        print("\n" + "="*60)
        print("  Statr Active Ingestion Daemon Running")
        print(f"  Active interval: {self.active_interval}s | Idle interval: {self.idle_interval}s")
        print("  Press Ctrl+C to stop.")
        print("="*60 + "\n")
        
        database.init_db()
        
        try:
            while self.running:
                is_playing = self.poll_once()
                interval = self.active_interval if is_playing else self.idle_interval
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\n[Poller] Shutting down...")
            if self.current_track:
                self._flush_current_track()
            print("[Poller] Stopped cleanly.")
