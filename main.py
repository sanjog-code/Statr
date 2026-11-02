"""
Statr CLI — Real-Time Spotify Listening & Playlist Analytics
Commands:
  run        - Runs both the active ingestion daemon & web dashboard concurrently.
  auth       - Connect and authorize your Spotify developer account.
  daemon     - Runs only the continuous Spotify playback tracker.
  dashboard  - Launches the web analytics UI on http://localhost:8888.
  stats      - Prints an instant ASCII analytics summary to the terminal.
  demo-data  - Populates realistic listening & playlist demo data for instant testing.
"""

import sys
import os
import time
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
import random

import database
from auth import authenticate_interactive, load_env
from poller import SpotifyPoller
from server import start_server


def cmd_stats():
    database.init_db()
    summary = database.get_summary_stats()
    playlists = database.get_playlist_analytics()
    top_artists = database.get_top_artists(limit=5)
    top_tracks = database.get_top_tracks(limit=5)

    print("\n" + "="*60)
    print("           STATR ANALYTICS SUMMARY")
    print("="*60)
    print(f"Total Listening Time : {summary['total_played_hours']} hrs ({summary['total_played_minutes']} mins)")
    print(f"Completed Scrobbles  : {summary['total_listens']}")
    print(f"Detected Skips       : {summary['total_skips']}")
    print(f"Skip Rate            : {summary['skip_rate_pct']}%")
    print(f"Unique Tracks Heard  : {summary['unique_tracks']}")
    print(f"Unique Artists       : {summary['unique_artists']}")
    print("-" * 60)
    
    print("\n[Top Playlists & Health]")
    if playlists:
        for p in playlists[:5]:
            print(f"  * {p['playlist_name']:<25} | Plays: {p['total_plays']:<3} | Skips: {p['total_skips']:<3} | Health: {p['health_score']}/100")
    else:
        print("  No playlist sessions recorded yet.")

    print("\n[Top Artists]")
    if top_artists:
        for i, a in enumerate(top_artists, 1):
            print(f"  {i}. {a['artists']:<25} ({a['play_count']} plays, {a['skip_count']} skips)")
    else:
        print("  No artist records yet.")

    print("\n[Top Tracks]")
    if top_tracks:
        for i, t in enumerate(top_tracks, 1):
            print(f"  {i}. {t['name']:<25} by {t['artists']:<20} ({t['play_count']} plays)")
    else:
        print("  No track records yet.")
    print("=" * 60 + "\n")


def cmd_demo_data():
    """Generates realistic demo tracks, playlists, and listening history."""
    database.init_db()
    print("[Demo] Populating realistic listening & playlist demo data...")

    demo_playlists = [
        ("pl_deep_focus", "Deep Focus & Study", "Spotify", "https://images.unsplash.com/photo-1518770660439-4636190af475?w=100&q=80", 45),
        ("pl_gym_hype", "Gym High Energy", "Alex", "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=100&q=80", 80),
        ("pl_late_night", "Late Night Lofi Beats", "Chillhop", "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=100&q=80", 120),
        ("pl_indie_discoveries", "Indie Discoveries 2026", "Spotify", "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=100&q=80", 50),
    ]

    for pid, name, owner, img, count in demo_playlists:
        database.save_playlist(pid, name, owner, img, count)

    demo_tracks = [
        ("tr_1", "Midnight City", "M83", "Hurry Up, We're Dreaming", 243000, 85, "https://images.unsplash.com/photo-1614613535308-eb5fbd3d2c17?w=100&q=80"),
        ("tr_2", "Starboy", "The Weeknd, Daft Punk", "Starboy", 230000, 92, "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=100&q=80"),
        ("tr_3", "Resonance", "HOME", "Odyssey", 212000, 78, "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=100&q=80"),
        ("tr_4", "Levitating", "Dua Lipa", "Future Nostalgia", 203000, 90, "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=100&q=80"),
        ("tr_5", "Intro", "The xx", "xx", 127000, 82, "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?w=100&q=80"),
        ("tr_6", "After Dark", "Mr.Kitty", "Time", 259000, 84, "https://images.unsplash.com/photo-1470225620780-dba8ba36b745?w=100&q=80"),
        ("tr_7", "Blinding Lights", "The Weeknd", "After Hours", 200000, 96, "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=100&q=80"),
        ("tr_8", "Weightless", "Marconi Union", "Ambient Transmissions", 480000, 70, "https://images.unsplash.com/photo-1518770660439-4636190af475?w=100&q=80"),
        ("tr_9", "Can't Feel My Face", "The Weeknd", "Beauty Behind The Madness", 213000, 88, "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?w=100&q=80"),
        ("tr_10", "Get Lucky", "Daft Punk, Pharrell Williams", "Random Access Memories", 248000, 89, "https://images.unsplash.com/photo-1508700115892-45ecd05ae2ad?w=100&q=80")
    ]

    for tid, name, artists, album, dur, pop, img in demo_tracks:
        database.save_track(tid, name, artists, album, dur, pop, img)

    # Generate 14 days of realistic listening sessions
    now = datetime.now(timezone.utc)
    event_count = 0

    for day_offset in range(14, -1, -1):
        day_date = now - timedelta(days=day_offset)
        # Daily listens between 12 and 35 tracks
        daily_count = random.randint(15, 35)
        for _ in range(daily_count):
            # Select time with natural human clustering (morning 8-11, afternoon 14-17, night 20-23)
            hour_pool = [8, 9, 10, 14, 15, 16, 17, 20, 21, 22, 23]
            hour = random.choice(hour_pool)
            minute = random.randint(0, 59)
            event_time = day_date.replace(hour=hour, minute=minute, second=random.randint(0, 59))

            track = random.choice(demo_tracks)
            playlist = random.choice(demo_playlists)

            # Different playlists have different skip profiles:
            # Gym hype has higher skips, Deep focus has lower skips
            skip_prob = 0.38 if playlist[0] == "pl_gym_hype" else (0.10 if playlist[0] == "pl_deep_focus" else 0.22)
            is_skip = random.random() < skip_prob

            played_ms = random.randint(4000, 25000) if is_skip else random.randint(60000, track[4])

            database.log_event(
                track_id=track[0],
                context_type="playlist",
                context_uri=f"spotify:playlist:{playlist[0]}",
                context_name=playlist[1],
                played_at=event_time.strftime("%Y-%m-%d %H:%M:%S"),
                played_ms=played_ms,
                is_skip=is_skip,
                device_name=random.choice(["MacBook Pro", "iPhone 15 Pro", "Living Room Speaker"]),
                device_type=random.choice(["Computer", "Smartphone", "Speaker"])
            )
            event_count += 1

    print(f"[Demo] Successfully injected {event_count} realistic playback events across 4 playlists!")
    print("[Demo] Run 'python main.py dashboard' to explore the analytics UI now.")


def cmd_run():
    database.init_db()
    env = load_env()
    port = int(env.get("DASHBOARD_PORT", 8888))

    print("\n" + "="*60)
    print("  Starting Statr (Daemon + Web Dashboard)")
    print("="*60)

    # Start Web Dashboard server in background thread
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()

    # Open dashboard in browser after 1 second
    def _open():
        time.sleep(1.2)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()

    # Start Active Ingestion Poller in main thread
    poller = SpotifyPoller()
    poller.start()


def main():
    args = sys.argv[1:]
    command = args[0].lower() if args else "help"

    if command == "auth":
        authenticate_interactive()
    elif command == "daemon":
        poller = SpotifyPoller()
        poller.start()
    elif command == "dashboard":
        database.init_db()
        env = load_env()
        port = int(env.get("DASHBOARD_PORT", 8888))
        print(f"Opening dashboard at http://localhost:{port}...")
        webbrowser.open(f"http://localhost:{port}")
        start_server(port)
    elif command == "run":
        cmd_run()
    elif command == "stats":
        cmd_stats()
    elif command in ("demo-data", "mock", "seed"):
        cmd_demo_data()
    elif command in ("reset", "clear"):
        database.init_db()
        database.clear_database()
        print("[Statr] Database cleared successfully.")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
