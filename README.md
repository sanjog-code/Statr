# Statr 🎧
### Real-Time Spotify Listening & Playlist Health Analytics

Statr is a lightweight, zero-dependency local daemon and analytics dashboard that continuously tracks your Spotify playback, preserves playlist context, detects track skips vs completed scrobbles, and gives you deep playlist health metrics.

---

## 🚀 Quick Start

### 1. Preview with Demo Data (Instant Test)
Before even configuring Spotify, you can populate realistic demo data and explore the web dashboard immediately:

```powershell
# Open terminal in the spotify-pulse directory:
# Open terminal in the statr repository directory:
cd statr

# Launch the Web Dashboard:
python main.py dashboard
```
> Or simply double-click `statr.bat dashboard`. It will open `http://localhost:8888` in your browser!

---

### 2. Connect Your Real Spotify Account

To track your live listening habits:

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and log in.
2. Click **Create App**:
   - **App Name:** `Statr Analytics`
   - **App Description:** `Personal real-time listening & playlist tracker`
   - **Redirect URI:** `http://localhost:8888/callback`
   - **Which API/SDKs are you planning to use:** Web API
3. Save the app, click **Settings**, and copy your **Client ID** and **Client Secret**.
4. In this folder, open `.env` (or copy `.env.example` to `.env`) and paste your credentials:
   ```env
   SPOTIFY_CLIENT_ID=your_actual_client_id
   SPOTIFY_CLIENT_SECRET=your_actual_client_secret
   SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
   ```
5. Run the authentication command:
   ```powershell
   python main.py auth
   ```
   A browser window will open automatically. Click **Agree** to connect your account. Once done, credentials are saved securely in `.token_cache.json`.

---

### 3. Run Tracking & Analytics

Run both the continuous background tracker and the dashboard simultaneously:

```powershell
python main.py run
```
> Or double-click `statr.bat`.

---

## 📊 Available CLI Commands

| Command | Description |
| :--- | :--- |
| `python main.py run` | Runs both the active tracking daemon and the web dashboard concurrently. |
| `python main.py auth` | Authenticates with Spotify via browser OAuth. |
| `python main.py dashboard` | Launches the web dashboard UI at `http://localhost:8888`. |
| `python main.py daemon` | Runs only the background ingestion poller (outputs live plays/skips to terminal). |
| `python main.py stats` | Prints an instant ASCII summary report to the terminal. |
| `python main.py demo-data` | Re-seeds realistic test listening sessions and playlist events. |

---

## 🧠 How Skip Detection & Playlist Health Work

* **Scrobble (Listen):** A track played for $\ge 30$ seconds (or $> 20\%$ of its duration).
* **Skip:** A track transitioned or skipped before 30 seconds. Associated directly with the playlist or album you were listening to.
* **Playlist Health Score:**
  $$PHS = 100 \times \left(1 - \frac{\text{Skips in Playlist}}{\text{Total Interactions}}\right)$$
  - **$\ge 75$:** Optimal Flow (high engagement, low skip friction)
  - **$40 - 74$:** Moderate Skips
  - **$< 40$:** Needs Pruning (high skip hotspot detected)
