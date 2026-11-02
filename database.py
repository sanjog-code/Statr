"""
Statr Database Layer
SQLite storage for tracks, playlists, playback events, and analytical queries.
"""

import sqlite3
import os
import shutil
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "statr.db")
LEGACY_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pulsebeat.db")

# Seamless migration from legacy pulsebeat.db
if not os.path.exists(DB_FILE) and os.path.exists(LEGACY_DB):
    try:
        shutil.copy2(LEGACY_DB, DB_FILE)
    except Exception:
        DB_FILE = LEGACY_DB


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Tracks master table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                track_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                artists TEXT NOT NULL,
                album TEXT,
                duration_ms INTEGER,
                popularity INTEGER,
                image_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Playlists master table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                playlist_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner TEXT,
                image_url TEXT,
                track_count INTEGER DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Listening and skip events log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS listening_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL,
                context_type TEXT,
                context_uri TEXT,
                context_name TEXT,
                played_at DATETIME NOT NULL,
                played_ms INTEGER NOT NULL,
                is_skip INTEGER DEFAULT 0,
                device_name TEXT,
                device_type TEXT,
                FOREIGN KEY (track_id) REFERENCES tracks(track_id)
            )
        """)

        # Indexes for fast dashboard aggregations
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_played_at ON listening_events(played_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_track_id ON listening_events(track_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_context_uri ON listening_events(context_uri)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_is_skip ON listening_events(is_skip)")
        conn.commit()


def save_track(track_id: str, name: str, artists: str, album: str, duration_ms: int, popularity: int = 0, image_url: str = ""):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO tracks (track_id, name, artists, album, duration_ms, popularity, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(track_id) DO UPDATE SET
                name = excluded.name,
                artists = excluded.artists,
                album = excluded.album,
                duration_ms = excluded.duration_ms,
                popularity = excluded.popularity,
                image_url = CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE tracks.image_url END
        """, (track_id, name, artists, album, duration_ms, popularity, image_url))
        conn.commit()


def save_playlist(playlist_id: str, name: str, owner: str = "", image_url: str = "", track_count: int = 0):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO playlists (playlist_id, name, owner, image_url, track_count, last_updated)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(playlist_id) DO UPDATE SET
                name = excluded.name,
                owner = excluded.owner,
                image_url = CASE WHEN excluded.image_url != '' THEN excluded.image_url ELSE playlists.image_url END,
                track_count = excluded.track_count,
                last_updated = CURRENT_TIMESTAMP
        """, (playlist_id, name, owner, image_url, track_count))
        conn.commit()


def get_playlist_name(playlist_id: str) -> Optional[str]:
    with get_connection() as conn:
        row = conn.execute("SELECT name FROM playlists WHERE playlist_id = ?", (playlist_id,)).fetchone()
        return row["name"] if row else None


def log_event(track_id: str, context_type: str, context_uri: str, context_name: str, 
              played_at: str, played_ms: int, is_skip: bool, device_name: str, device_type: str):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO listening_events 
            (track_id, context_type, context_uri, context_name, played_at, played_ms, is_skip, device_name, device_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            track_id, context_type, context_uri, context_name,
            played_at, played_ms, 1 if is_skip else 0, device_name, device_type
        ))
        conn.commit()


def _get_date_filter(days: Optional[int]) -> str:
    if days is None or days <= 0:
        return ""
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    return f"AND played_at >= '{start_date}'"


def get_summary_stats(days: Optional[int] = None) -> Dict[str, Any]:
    filter_sql = _get_date_filter(days)
    with get_connection() as conn:
        query = f"""
            SELECT 
                COUNT(*) as total_events,
                SUM(CASE WHEN is_skip = 1 THEN 1 ELSE 0 END) as total_skips,
                SUM(CASE WHEN is_skip = 0 THEN 1 ELSE 0 END) as total_listens,
                SUM(CASE WHEN is_skip = 0 THEN played_ms ELSE 0 END) as total_played_ms,
                COUNT(DISTINCT track_id) as unique_tracks
            FROM listening_events
            WHERE 1=1 {filter_sql}
        """
        row = conn.execute(query).fetchone()
        
        total_events = row["total_events"] or 0
        total_skips = row["total_skips"] or 0
        total_listens = row["total_listens"] or 0
        total_played_ms = row["total_played_ms"] or 0
        unique_tracks = row["unique_tracks"] or 0
        
        skip_rate = round((total_skips / total_events * 100), 1) if total_events > 0 else 0.0
        total_minutes = round(total_played_ms / 60000, 1)
        total_hours = round(total_minutes / 60, 2)
        
        # Unique artists
        artist_query = f"""
            SELECT COUNT(DISTINCT t.artists) as unique_artists
            FROM listening_events e
            JOIN tracks t ON e.track_id = t.track_id
            WHERE e.is_skip = 0 {filter_sql}
        """
        artist_row = conn.execute(artist_query).fetchone()
        unique_artists = artist_row["unique_artists"] if artist_row else 0
        
        return {
            "total_events": total_events,
            "total_listens": total_listens,
            "total_skips": total_skips,
            "skip_rate_pct": skip_rate,
            "total_played_minutes": total_minutes,
            "total_played_hours": total_hours,
            "unique_tracks": unique_tracks,
            "unique_artists": unique_artists
        }


def get_top_tracks(days: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    filter_sql = _get_date_filter(days)
    with get_connection() as conn:
        query = f"""
            SELECT 
                t.track_id,
                t.name,
                t.artists,
                t.album,
                t.image_url,
                COUNT(*) as play_count,
                SUM(e.played_ms) as total_ms,
                SUM(CASE WHEN e.is_skip = 1 THEN 1 ELSE 0 END) as skip_count
            FROM listening_events e
            JOIN tracks t ON e.track_id = t.track_id
            WHERE 1=1 {filter_sql}
            GROUP BY t.track_id
            ORDER BY play_count DESC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_top_artists(days: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    filter_sql = _get_date_filter(days)
    with get_connection() as conn:
        query = f"""
            SELECT 
                t.artists,
                COUNT(*) as play_count,
                SUM(CASE WHEN e.is_skip = 0 THEN e.played_ms ELSE 0 END) as total_ms,
                SUM(CASE WHEN e.is_skip = 1 THEN 1 ELSE 0 END) as skip_count
            FROM listening_events e
            JOIN tracks t ON e.track_id = t.track_id
            WHERE 1=1 {filter_sql}
            GROUP BY t.artists
            ORDER BY play_count DESC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_playlist_analytics(days: Optional[int] = None) -> List[Dict[str, Any]]:
    filter_sql = _get_date_filter(days)
    with get_connection() as conn:
        query = f"""
            SELECT 
                e.context_uri,
                COALESCE(p.name, e.context_name, 'Unknown Playlist') as playlist_name,
                p.image_url,
                COUNT(*) as total_interactions,
                SUM(CASE WHEN e.is_skip = 0 THEN 1 ELSE 0 END) as total_plays,
                SUM(CASE WHEN e.is_skip = 1 THEN 1 ELSE 0 END) as total_skips,
                SUM(CASE WHEN e.is_skip = 0 THEN e.played_ms ELSE 0 END) as total_ms,
                COUNT(DISTINCT e.track_id) as unique_tracks_heard
            FROM listening_events e
            LEFT JOIN playlists p ON e.context_uri LIKE '%' || p.playlist_id
            WHERE e.context_type = 'playlist' {filter_sql}
            GROUP BY e.context_uri
            ORDER BY total_interactions DESC
        """
        rows = conn.execute(query).fetchall()
        results = []
        for r in rows:
            interactions = r["total_interactions"]
            skips = r["total_skips"]
            skip_rate = round((skips / interactions * 100), 1) if interactions > 0 else 0.0
            minutes = round(r["total_ms"] / 60000, 1)
            # Health Score formula
            health_score = max(0, min(100, int((1 - (skips / max(1, interactions))) * 100)))
            
            results.append({
                "context_uri": r["context_uri"],
                "playlist_name": r["playlist_name"],
                "image_url": r["image_url"],
                "total_interactions": interactions,
                "total_plays": r["total_plays"],
                "total_skips": skips,
                "skip_rate_pct": skip_rate,
                "total_minutes": minutes,
                "unique_tracks_heard": r["unique_tracks_heard"],
                "health_score": health_score
            })
        return results


def get_hourly_heatmap(days: Optional[int] = None) -> List[Dict[str, Any]]:
    filter_sql = _get_date_filter(days)
    with get_connection() as conn:
        query = f"""
            SELECT 
                strftime('%H', played_at) as hour,
                COUNT(*) as count,
                SUM(CASE WHEN is_skip = 1 THEN 1 ELSE 0 END) as skips
            FROM listening_events
            WHERE 1=1 {filter_sql}
            GROUP BY hour
            ORDER BY hour ASC
        """
        rows = conn.execute(query).fetchall()
        
        # Populate all 24 hours (00 to 23)
        hour_map = {f"{h:02d}": {"hour": f"{h:02d}", "count": 0, "skips": 0} for h in range(24)}
        for r in rows:
            if r["hour"] in hour_map:
                hour_map[r["hour"]]["count"] = r["count"]
                hour_map[r["hour"]]["skips"] = r["skips"]
        return list(hour_map.values())


def get_recent_events(limit: int = 30) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        query = """
            SELECT 
                e.id,
                e.played_at,
                e.played_ms,
                e.is_skip,
                e.context_name,
                e.context_type,
                e.device_name,
                t.name as track_name,
                t.artists,
                t.album,
                t.image_url,
                t.duration_ms
            FROM listening_events e
            JOIN tracks t ON e.track_id = t.track_id
            ORDER BY e.played_at DESC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_top_albums(days: Optional[int] = None, limit: int = 10) -> List[Dict[str, Any]]:
    filter_sql = _get_date_filter(days)
    with get_connection() as conn:
        query = f"""
            SELECT 
                COALESCE(NULLIF(t.album, ''), 'Singles & EPs') as name,
                t.artists as artist,
                COUNT(*) as play_count,
                ROUND(SUM(CASE WHEN e.is_skip = 0 THEN e.played_ms ELSE 0 END) / 60000.0, 1) as total_minutes,
                ROUND(SUM(CASE WHEN e.is_skip = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as completion_rate_pct,
                MAX(t.image_url) as image_url
            FROM listening_events e
            JOIN tracks t ON e.track_id = t.track_id
            WHERE 1=1 {filter_sql}
            GROUP BY t.album, t.artists
            ORDER BY play_count DESC
            LIMIT ?
        """
        rows = conn.execute(query, (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_obscurity_metrics(days: Optional[int] = None) -> Dict[str, Any]:
    filter_sql = _get_date_filter(days)
    with get_connection() as conn:
        row = conn.execute(f"""
            SELECT 
                AVG(t.popularity) as avg_popularity,
                COUNT(*) as total_tracks_played,
                SUM(CASE WHEN t.popularity < 50 THEN 1 ELSE 0 END) as deep_cuts_count
            FROM listening_events e
            JOIN tracks t ON e.track_id = t.track_id
            WHERE 1=1 {filter_sql}
        """).fetchone()
        
        avg_pop = row["avg_popularity"] if row and row["avg_popularity"] is not None else 62.0
        deep_cuts = row["deep_cuts_count"] if row and row["deep_cuts_count"] is not None else 0
        obscurity_score = max(5, min(95, int(100 - avg_pop)))
        mainstream_pct = 100 - obscurity_score
        
        if obscurity_score >= 70:
            label = "Underground Purist"
            genre = "Modular Synth & Ambient Textures"
        elif obscurity_score >= 55:
            label = "Cerebral Indie Explorer"
            genre = "Modern Indie & Dream Pop"
        elif obscurity_score >= 40:
            label = "Eclectic Tastemaker"
            genre = "Alternative Synthpop & Electronic"
        else:
            label = "Chart Pop Enthusiast"
            genre = "Contemporary Global Pop"
            
        return {
            "score_pct": obscurity_score,
            "label": label,
            "mainstream_pct": mainstream_pct,
            "deep_cuts_count": deep_cuts,
            "top_niche_genre": genre
        }


def get_fan_rating(days: Optional[int] = None) -> Dict[str, Any]:
    top_artists = get_top_artists(days=days, limit=1)
    if not top_artists:
        return {
            "primary_artist": "Top Artist",
            "tier": "Top 1% Listener",
            "score": 85,
            "rank_label": "Music Enthusiast",
            "badges": ["Eclectic Scrobbler", "Daily Flow", "Curator"]
        }
    top = top_artists[0]
    primary_name = top["artists"]
    plays = top["play_count"]
    skips = top["skip_count"]
    skip_rate = (skips / plays * 100) if plays > 0 else 0
    
    score = min(99, max(75, 80 + int(plays * 0.4) - int(skip_rate * 0.3)))
    if score >= 95:
        tier = "Top 0.1% Superfan"
        rank_label = "Elite Devotee"
    elif score >= 90:
        tier = "Top 0.5% Superfan"
        rank_label = "Heavy Rotation Master"
    else:
        tier = "Top 1% Listener"
        rank_label = "Loyal Listener"
        
    badges = ["Top 0.5% Global", "Zero-Skip Connoisseur", "Heavy Rotation Devotee"]
    if skip_rate < 15:
        badges.append("Front-to-Back Purist")
    return {
        "primary_artist": primary_name,
        "tier": tier,
        "score": score,
        "rank_label": rank_label,
        "badges": badges
    }


def clear_database():
    with get_connection() as conn:
        conn.execute("DELETE FROM listening_events")
        conn.execute("DELETE FROM playlists")
        conn.execute("DELETE FROM tracks")
        conn.commit()
