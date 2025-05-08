from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import hashlib
import json
import sqlite3
from pathlib import Path
import yt_dlp
import os
import shutil
import uuid
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
MUSIC_DIR = Path(r"C:\Users\Ashwa\Music\music")
IMAGES_DIR = Path(r"C:\Users\Ashwa\Desktop\echo-main\static\images")
IMAGES_DIR.mkdir(exist_ok=True)
app.mount("/music", StaticFiles(directory=MUSIC_DIR), name="music")
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# In-memory user storage (use a database in production)
USERS_FILE = Path("users.json")
if USERS_FILE.exists():
    try:
        with open(USERS_FILE, "r") as f:
            content = f.read().strip()
            if content:
                users = json.loads(content)
            else:
                users = {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse users.json: {e}. Initializing with empty users dictionary.")
        users = {}
else:
    users = {}
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)
        logger.debug("Created empty users.json")
    except Exception as e:
        logger.error(f"Failed to create users.json: {e}")
        raise

def save_users():
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)
        logger.debug(f"Successfully saved users to {USERS_FILE}: {users}")
    except Exception as e:
        logger.error(f"Failed to save users to {USERS_FILE}: {e}")
        raise

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Database setup for songs and playlists
DB_PATH = Path("songs.db")
DEFAULT_IMAGE = "default.jpg"

def init_db():
    if not DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist TEXT,
            filename TEXT NOT NULL UNIQUE,
            playlist TEXT,
            position INTEGER
        )''')
        c.execute('''CREATE TABLE playlists (
            name TEXT,
            image_path TEXT,
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )''')
        conn.commit()
        conn.close()
        logger.debug("Database initialized")

def index_songs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if not MUSIC_DIR.exists():
        MUSIC_DIR.mkdir(parents=True)
        logger.debug(f"Created music directory {MUSIC_DIR}")
    for playlist_dir in MUSIC_DIR.iterdir():
        if playlist_dir.is_dir():
            playlist_name = playlist_dir.name
            c.execute("SELECT COUNT(*) FROM playlists WHERE name = ?", (playlist_name,))
            if c.fetchone()[0] == 0:
                c.execute("INSERT INTO playlists (name, image_path) VALUES (?, ?)", (playlist_name, DEFAULT_IMAGE))
                logger.debug(f"Added playlist {playlist_name} to database")
            songs = sorted(playlist_dir.glob("*.mp3"))
            for position, file in enumerate(songs):
                filename = f"{playlist_name}/{file.name}"
                title = file.name.replace(".mp3", "").split(" - ")[0] if " - " in file.name else file.name.replace(".mp3", "")
                artist = file.name.split(" - ")[1].replace(".mp3", "") if " - " in file.name and len(file.name.split(" - ")) > 1 else "Unknown"
                c.execute("INSERT OR IGNORE INTO songs (title, artist, filename, playlist, position) VALUES (?, ?, ?, ?, ?)", 
                         (title, artist, filename, playlist_name, position))
                logger.debug(f"Indexed: {filename} in playlist {playlist_name} at position {position}")
    conn.commit()
    conn.close()

init_db()
index_songs()

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    logger.debug("Serving intro.html")
    return templates.TemplateResponse("intro.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    logger.debug("Serving login.html")
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    logger.debug(f"Login attempt with username: {username}")
    hashed_password = hash_password(password)
    if username in users and users[username]["password"] == hashed_password:
        logger.debug(f"Login successful for username: {username}, redirecting to /index.html")
        response = RedirectResponse(url="/index.html", status_code=303)
        response.set_cookie(key="session_username", value=username, httponly=True, max_age=3600, samesite="Lax")
        return response
    logger.warning(f"Login failed for username: {username} - Invalid credentials")
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials, try again"})

@app.get("/index.html", response_class=HTMLResponse)
async def index(request: Request):
    username = request.cookies.get("session_username")
    logger.debug(f"Session cookie username: {username}")
    if not username or username not in users:
        logger.debug("No valid session found, redirecting to /login")
        return RedirectResponse(url="/login", status_code=303)
    logger.debug(f"Serving index.html for user: {username}")
    return templates.TemplateResponse("index.html", {"request": request, "username": username})

@app.get("/logout")
async def logout(request: Request):
    logger.debug("Logging out user, redirecting to /login")
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_username")
    return response

@app.get("/songs")
async def get_songs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, artist, filename, playlist, position FROM songs ORDER BY playlist, position")
    songs = [{"id": row[0], "title": row[1], "artist": row[2], "url": f"/music/{row[3]}", "playlist": row[4], "position": row[5]} for row in c.fetchall()]
    conn.close()
    logger.debug(f"Fetched {len(songs)} songs")
    return {"songs": songs}

@app.get("/playlists")
async def get_playlists():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, image_path, id FROM playlists")
    playlists = [{"name": row[0], "image": f"/images/{row[1]}" if row[1] else f"/images/{DEFAULT_IMAGE}", "id": row[2]} for row in c.fetchall()]
    conn.close()
    logger.debug(f"Fetched {len(playlists)} playlists")
    return {"playlists": playlists}

@app.get("/song/{song_id}")
async def get_song(song_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM songs WHERE id = ?", (song_id,))
    song = c.fetchone()
    conn.close()
    if not song:
        logger.warning(f"Song with id {song_id} not found")
        raise HTTPException(status_code=404, detail="Song not found")
    file_path = MUSIC_DIR / song[0]
    if not file_path.exists():
        logger.warning(f"Song file {file_path} not found on disk")
        raise HTTPException(status_code=404, detail="Song file not found on disk")
    logger.debug(f"Serving song file: {file_path}")
    return FileResponse(file_path, media_type="audio/mpeg")

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    logger.debug("Serving login.html for signup")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/signup")
async def signup(username: str = Form(...), password: str = Form(...), email: str = Form(...), broj: str = Form(...)):
    logger.debug(f"Signup attempt with username: {username}")
    if username in users:
        logger.warning(f"Username {username} already exists")
        return JSONResponse(status_code=400, content={"message": "Username already exists"})
    if not username or not password:
        logger.warning("Signup failed due to empty username or password")
        return JSONResponse(status_code=400, content={"message": "Username and password cannot be empty"})
    hashed_password = hash_password(password)
    users[username] = {"password": hashed_password, "email": email, "broj": broj}
    save_users()
    logger.debug(f"Signup successful for username: {username}, redirecting to /login")
    return RedirectResponse(url="/login", status_code=303)

@app.post("/create_playlist")
async def create_playlist(playlist_name: str = Form(...)):
    if not playlist_name.strip():
        logger.warning("Attempted to create playlist with empty name")
        return JSONResponse(status_code=400, content={"message": "Playlist name cannot be empty"})
    playlist_dir = MUSIC_DIR / playlist_name
    playlist_dir.mkdir(exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM playlists WHERE name = ?", (playlist_name,))
    if c.fetchone()[0] > 0:
        conn.close()
        logger.warning(f"Playlist {playlist_name} already exists")
        return JSONResponse(status_code=400, content={"message": f"Playlist {playlist_name} already exists"})
    c.execute("INSERT INTO playlists (name, image_path) VALUES (?, ?)", (playlist_name, DEFAULT_IMAGE))
    conn.commit()
    conn.close()
    logger.debug(f"Created playlist: {playlist_name}")
    return {"message": f"Playlist {playlist_name} created"}

@app.post("/update_playlist_image")
async def update_playlist_image(playlist_id: int = Form(...), image: UploadFile = File(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT image_path, name FROM playlists WHERE id = ?", (playlist_id,))
    existing_playlist = c.fetchone()
    if not existing_playlist:
        conn.close()
        logger.warning(f"Playlist with id {playlist_id} not found")
        raise HTTPException(status_code=404, detail="Playlist not found")

    if existing_playlist[0] and existing_playlist[0] != DEFAULT_IMAGE:
        old_image_path = IMAGES_DIR / existing_playlist[0]
        if old_image_path.exists():
            os.remove(old_image_path)

    file_extension = image.filename.split('.')[-1].lower()
    image_filename = f"{uuid.uuid4()}.{file_extension}"
    image_path = IMAGES_DIR / image_filename
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    c.execute("UPDATE playlists SET image_path = ? WHERE id = ?", (image_filename, playlist_id))
    conn.commit()
    conn.close()
    logger.debug(f"Updated image for playlist {existing_playlist[1]}")
    return {"message": f"Image updated for playlist {existing_playlist[1]}"}

@app.post("/rename_playlist")
async def rename_playlist(playlist_id: int = Form(...), new_name: str = Form(...)):
    if not new_name.strip():
        logger.warning("Attempted to rename playlist to empty name")
        return JSONResponse(status_code=400, content={"message": "New playlist name cannot be empty"})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,))
    old_name_row = c.fetchone()
    if not old_name_row:
        conn.close()
        logger.warning(f"Playlist with id {playlist_id} not found")
        raise HTTPException(status_code=404, detail="Playlist not found")
    old_name = old_name_row[0]

    c.execute("SELECT COUNT(*) FROM playlists WHERE name = ?", (new_name,))
    if c.fetchone()[0] > 0:
        conn.close()
        logger.warning(f"Playlist name {new_name} already exists")
        return JSONResponse(status_code=400, content={"message": f"Playlist name {new_name} already exists"})

    playlist_dir = MUSIC_DIR / old_name
    new_playlist_dir = MUSIC_DIR / new_name

    c.execute("UPDATE playlists SET name = ? WHERE id = ?", (new_name, playlist_id))
    c.execute("UPDATE songs SET playlist = ? WHERE playlist = ?", (new_name, old_name))

    if playlist_dir.exists():
        if new_playlist_dir.exists():
            for song_file in playlist_dir.glob("*.mp3"):
                target_path = new_playlist_dir / song_file.name
                if not target_path.exists():
                    shutil.move(str(song_file), str(target_path))
                relative_filename = f"{new_name}/{song_file.name}"
                c.execute("UPDATE songs SET filename = ? WHERE filename = ?", 
                         (relative_filename, f"{old_name}/{song_file.name}"))
            try:
                playlist_dir.rmdir()
            except OSError:
                pass
        else:
            playlist_dir.rename(new_playlist_dir)

    conn.commit()
    conn.close()
    logger.debug(f"Renamed playlist from {old_name} to {new_name}")
    return {"message": f"Playlist renamed from {old_name} to {new_name}"}

@app.post("/add_song")
async def add_song(playlist_name: str = Form(...), youtube_url: str = Form(...)):
    playlist_dir = MUSIC_DIR / playlist_name
    playlist_dir.mkdir(exist_ok=True)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(playlist_dir / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            downloaded_file = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
            filename = f"{playlist_name}/{downloaded_file.name}"
            title = info.get('title', 'Unknown Title')
            artist = info.get('uploader', 'Unknown Artist').replace(" - Topic", "")
            os.rename(downloaded_file, playlist_dir / downloaded_file.name)  # Ensure file is in correct directory

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT MAX(position) FROM songs WHERE playlist = ?", (playlist_name,))
        max_position = c.fetchone()[0] or -1
        c.execute("INSERT INTO songs (title, artist, filename, playlist, position) VALUES (?, ?, ?, ?, ?)",
                  (title, artist, filename, playlist_name, max_position + 1))
        conn.commit()
        conn.close()
        logger.debug(f"Added song {title} to playlist {playlist_name}")
        return {"message": f"Added {title} to {playlist_name}"}
    except Exception as e:
        logger.error(f"Failed to download song: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download song: {str(e)}")

@app.post("/delete_playlist")
async def delete_playlist(playlist_id: int = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, image_path FROM playlists WHERE id = ?", (playlist_id,))
    playlist = c.fetchone()
    if not playlist:
        conn.close()
        logger.warning(f"Playlist with id {playlist_id} not found")
        raise HTTPException(status_code=404, detail="Playlist not found")
    playlist_name = playlist[0]

    playlist_dir = MUSIC_DIR / playlist_name
    if playlist_dir.exists():
        shutil.rmtree(playlist_dir)
    
    if playlist[1] and playlist[1] != DEFAULT_IMAGE:
        image_path = IMAGES_DIR / playlist[1]
        if image_path.exists():
            os.remove(image_path)
    
    c.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    c.execute("DELETE FROM songs WHERE playlist = ?", (playlist_name,))
    conn.commit()
    conn.close()
    logger.debug(f"Deleted playlist {playlist_name}")
    return {"message": f"Deleted playlist {playlist_name}"}

@app.post("/delete_song")
async def delete_song(song_id: int = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM songs WHERE id = ?", (song_id,))
    song = c.fetchone()
    if not song:
        logger.warning(f"Song with id {song_id} not found")
        raise HTTPException(status_code=404, detail="Song not found")
    file_path = MUSIC_DIR / song[0]
    if file_path.exists():
        os.remove(file_path)
    c.execute("DELETE FROM songs WHERE id = ?", (song_id,))
    conn.commit()
    conn.close()
    logger.debug(f"Deleted song with id {song_id}")
    return {"message": "Song deleted"}

@app.post("/rearrange_playlist")
async def rearrange_playlist(playlist_name: str = Form(...), song_ids: str = Form(...)):
    song_ids = [int(id) for id in song_ids.split(",")]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for position, song_id in enumerate(song_ids):
        c.execute("UPDATE songs SET position = ? WHERE id = ? AND playlist = ?", (position, song_id, playlist_name))
    conn.commit()
    conn.close()
    logger.debug(f"Rearranged playlist {playlist_name}")
    return {"message": f"Rearranged playlist {playlist_name}"}

@app.get("/search_youtube")
async def search_youtube(query: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch10',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(f"ytsearch10:{query}", download=False)
            videos = result.get('entries', [])
            logger.debug(f"YouTube search returned {len(videos)} results for query: {query}")
            return {
                "results": [{"title": v['title'], "url": v['webpage_url'], "artist": v.get('uploader', 'Unknown')} for v in videos]
            }
    except Exception as e:
        logger.error(f"Failed to search YouTube: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search YouTube: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True, log_level="debug")