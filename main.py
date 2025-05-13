from fastapi import FastAPI, HTTPException, Form, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import List, Dict
import hashlib
import json
import sqlite3
from pathlib import Path
import yt_dlp
import os
import shutil
import uuid
import logging
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Music Player API", description="A robust music player API with user-specific playlists and songs", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development (restrict in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Define paths relative to the project directory for portability
BASE_DIR = Path(__file__).parent
MUSIC_DIR = Path("C:/Users/Ashwa/Music/music")
IMAGES_DIR = BASE_DIR / "static" / "images"
DB_PATH = BASE_DIR / "songs.db"
DEFAULT_IMAGE = "default.jpg"

# Ensure directories exist
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# In-memory user storage (use a database in production)
USERS_FILE = BASE_DIR / "users.json"
users = {}
if USERS_FILE.exists():
    try:
        with open(USERS_FILE, "r") as f:
            content = f.read().strip()
            users = json.loads(content) if content else {}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse users.json: {e}. Initializing with empty users dictionary.")
        users = {}
else:
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)
    logger.debug("Created empty users.json")

def save_users():
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)
        logger.debug("Successfully saved users to users.json")
    except Exception as e:
        logger.error(f"Failed to save users to users.json: {e}")
        raise

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        email TEXT,
        broj TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        image_path TEXT DEFAULT '/static/images/default.jpg',
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist TEXT NOT NULL,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        artist TEXT NOT NULL,
        url TEXT,
        filename TEXT,
        lyrics_text TEXT,
        position INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS lyrics (
        song_id INTEGER,
        timestamp REAL,
        line TEXT,
        FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
    )''')
    conn.commit()
    conn.close()
    logger.debug("Database initialized with optimized schema")

def migrate_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Migration logic if needed in the future
    c.execute("PRAGMA table_info(playlists)")
    columns = [col[1] for col in c.fetchall()]
    if 'image_path' not in columns:
        c.execute("ALTER TABLE playlists ADD COLUMN image_path TEXT DEFAULT '/static/images/default.jpg'")
        logger.debug("Added 'image_path' column to playlists table")
    c.execute("PRAGMA table_info(songs)")
    song_columns = [col[1] for col in c.fetchall()]
    for col in [('filename', 'TEXT'), ('lyrics_text', 'TEXT'), ('position', 'INTEGER DEFAULT 0')]:
        if col[0] not in song_columns:
            c.execute(f"ALTER TABLE songs ADD COLUMN {col[0]} {col[1]}")
            logger.debug(f"Added '{col[0]}' column to songs table")
    conn.commit()
    conn.close()
    logger.debug("Database migration completed")

def init_user_data(username: str):
    # No preloaded playlists or songs - create only the user directory
    user_dir = MUSIC_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Initialized empty user directory for {username}")

def parse_lyrics(lyrics_text: str) -> List[Dict[str, float | str]]:
    lines = [line.strip() for line in lyrics_text.split('\n') if line.strip()]
    parsed_lyrics = []
    for line in lines:
        match = re.match(r'^\[(\d{2}):(\d{2}\.\d{2})\](.*)$', line)
        if match:
            minutes, seconds = int(match.group(1)), float(match.group(2))
            time = minutes * 60 + seconds
            if 0 <= time < 3600:
                parsed_lyrics.append({"time": time, "text": match.group(3).strip()})
            else:
                logger.warning(f"Invalid timestamp {time} seconds in line: {line}")
        else:
            logger.warning(f"Unrecognized line format, skipping: {line}")
    return sorted(parsed_lyrics, key=lambda x: x["time"])

# Initialize database and migrate on startup
init_db()
migrate_db()

# Routes
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("intro.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    logger.debug(f"Login attempt for username: {username}")
    hashed_password = hash_password(password)
    if username in users and users[username].get("password") == hashed_password:
        init_user_data(username)  # Create empty user directory
        response = RedirectResponse(url="/index", status_code=303)
        response.set_cookie(key="session_username", value=username, httponly=True, max_age=3600, samesite="Lax")
        return response
    logger.warning(f"Login failed for {username}: Invalid credentials")
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/index", response_class=HTMLResponse)
async def index(request: Request):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request, "username": username})

@app.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_username")
    return response

@app.get("/songs")
async def get_songs(request: Request):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        return JSONResponse(content=[])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, artist, url, playlist, position, lyrics_text FROM songs WHERE user_id = ? ORDER BY playlist, position", (username,))
    songs = [
        {
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "url": row[3],
            "playlist": row[4],
            "position": row[5],
            "lyrics": json.loads(row[6]) if row[6] else None
        } for row in c.fetchall()
    ]
    conn.close()
    logger.debug(f"Fetched {len(songs)} songs for {username}")
    return JSONResponse(content=songs)

@app.get("/playlists")
async def get_playlists(request: Request):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        return {"playlists": []}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, image_path, id FROM playlists WHERE user_id = ?", (username,))
    playlists = [{"name": row[0], "image": row[1], "id": row[2]} for row in c.fetchall()]
    conn.close()
    logger.debug(f"Fetched {len(playlists)} playlists for {username}")
    return {"playlists": playlists}

@app.get("/song/{song_id}")
async def get_song(song_id: int, request: Request):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    song = c.fetchone()
    conn.close()
    if not song or not song[0]:
        raise HTTPException(status_code=404, detail="Song not found")
    file_path = MUSIC_DIR / song[0]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Song file not found")
    logger.debug(f"Serving song {file_path} for {username}")
    return FileResponse(file_path, media_type="audio/mpeg", filename=file_path.name)

@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/signup")
async def signup(username: str = Form(...), password: str = Form(...), email: str = Form(...), broj: str = Form(...)):
    logger.debug(f"Signup attempt for username: {username}")
    if username in users:
        return JSONResponse(status_code=400, content={"message": "Username already exists"})
    if not username.strip() or not password.strip():
        return JSONResponse(status_code=400, content={"message": "Username and password cannot be empty"})
    hashed_password = hash_password(password)
    users[username] = {"password": hashed_password, "email": email, "broj": broj}
    save_users()
    init_user_data(username)  # Create empty user directory
    response = RedirectResponse(url="/login", status_code=303)
    response.set_cookie(key="session_username", value=username, httponly=True, max_age=3600, samesite="Lax")
    return response

@app.post("/create_playlist")
async def create_playlist(request: Request, playlist_name: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not playlist_name.strip():
        return JSONResponse(status_code=400, content={"message": "Playlist name cannot be empty"})
    user_dir = MUSIC_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    playlist_dir = user_dir / playlist_name
    playlist_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM playlists WHERE name = ? AND user_id = ?", (playlist_name, username))
    if c.fetchone()[0] > 0:
        conn.close()
        return JSONResponse(status_code=400, content={"message": f"Playlist {playlist_name} already exists"})
    c.execute("INSERT INTO playlists (name, user_id, image_path) VALUES (?, ?, ?)", 
              (playlist_name, username, f"/static/images/{DEFAULT_IMAGE}"))
    conn.commit()
    conn.close()
    logger.debug(f"Created playlist {playlist_name} for {username}")
    return {"message": f"Playlist {playlist_name} created"}

@app.post("/update_playlist_image")
async def update_playlist_image(request: Request, playlist_id: int = Form(...), image: UploadFile = File(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT image_path, name FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    existing_playlist = c.fetchone()
    if not existing_playlist:
        conn.close()
        raise HTTPException(status_code=404, detail="Playlist not found")
    if existing_playlist[0] and not existing_playlist[0].endswith(DEFAULT_IMAGE):
        old_image_path = IMAGES_DIR / Path(existing_playlist[0]).name
        if old_image_path.exists():
            os.remove(old_image_path)
            logger.debug(f"Removed old image {old_image_path}")
    file_extension = image.filename.split('.')[-1].lower()
    image_filename = f"{uuid.uuid4()}.{file_extension}"
    image_path = IMAGES_DIR / image_filename
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)
    c.execute("UPDATE playlists SET image_path = ? WHERE id = ?", (f"/static/images/{image_filename}", playlist_id))
    conn.commit()
    conn.close()
    logger.debug(f"Updated image for playlist {existing_playlist[1]} for {username}")
    return {"message": f"Image updated for playlist {existing_playlist[1]}"}

@app.post("/rename_playlist")
async def rename_playlist(request: Request, playlist_id: int = Form(...), new_name: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not new_name.strip():
        return JSONResponse(status_code=400, content={"message": "New playlist name cannot be empty"})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    old_name_row = c.fetchone()
    if not old_name_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Playlist not found")
    old_name = old_name_row[0]
    c.execute("SELECT COUNT(*) FROM playlists WHERE name = ? AND user_id = ?", (new_name, username))
    if c.fetchone()[0] > 0:
        conn.close()
        return JSONResponse(status_code=400, content={"message": f"Playlist {new_name} already exists"})
    user_dir = MUSIC_DIR / username
    old_playlist_dir = user_dir / old_name
    new_playlist_dir = user_dir / new_name
    c.execute("UPDATE playlists SET name = ? WHERE id = ? AND user_id = ?", (new_name, playlist_id, username))
    c.execute("UPDATE songs SET playlist = ? WHERE playlist = ? AND user_id = ?", (new_name, old_name, username))
    if old_playlist_dir.exists():
        if new_playlist_dir.exists():
            for song_file in old_playlist_dir.glob("*.mp3"):
                target_path = new_playlist_dir / song_file.name
                if not target_path.exists():
                    shutil.move(song_file, target_path)
                    logger.debug(f"Moved {song_file} to {target_path}")
                    c.execute("UPDATE songs SET filename = ? WHERE filename = ?", 
                             (f"{username}/{new_name}/{song_file.name}", f"{username}/{old_name}/{song_file.name}"))
            old_playlist_dir.rmdir()
            logger.debug(f"Removed old directory {old_playlist_dir}")
        else:
            old_playlist_dir.rename(new_playlist_dir)
            logger.debug(f"Renamed directory from {old_name} to {new_name}")
    conn.commit()
    conn.close()
    logger.debug(f"Renamed playlist from {old_name} to {new_name} for {username}")
    return {"message": f"Playlist renamed from {old_name} to {new_name}"}

@app.post("/add_song")
async def add_song(request: Request, playlist_name: str = Form(...), youtube_url: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_dir = MUSIC_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    playlist_dir = user_dir / playlist_name
    playlist_dir.mkdir(parents=True, exist_ok=True)

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
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=True)
        downloaded_file = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
        filename = f"{username}/{playlist_name}/{downloaded_file.name}"
        os.rename(downloaded_file, playlist_dir / downloaded_file.name)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(position) FROM songs WHERE playlist = ? AND user_id = ?", (playlist_name, username))
    max_position = c.fetchone()[0] or -1
    c.execute("INSERT INTO songs (title, artist, url, filename, playlist, position, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (info.get('title', 'Unknown Title'), info.get('uploader', 'Unknown Artist').replace(" - Topic", ""),
               youtube_url, filename, playlist_name, max_position + 1, username))
    conn.commit()
    conn.close()
    logger.debug(f"Added song {info.get('title')} to {playlist_name} for {username}")
    return {"message": f"Added {info.get('title')} to {playlist_name}"}

@app.post("/delete_playlist")
async def delete_playlist(request: Request, playlist_id: int = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, image_path FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    playlist = c.fetchone()
    if not playlist:
        conn.close()
        raise HTTPException(status_code=404, detail="Playlist not found")
    playlist_name = playlist[0]
    playlist_dir = MUSIC_DIR / username / playlist_name
    if playlist_dir.exists():
        shutil.rmtree(playlist_dir)
        logger.debug(f"Removed directory {playlist_dir}")
    if playlist[1] and not playlist[1].endswith(DEFAULT_IMAGE):
        image_path = IMAGES_DIR / Path(playlist[1]).name
        if image_path.exists():
            os.remove(image_path)
            logger.debug(f"Removed image {image_path}")
    c.execute("DELETE FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    conn.commit()
    conn.close()
    logger.debug(f"Deleted playlist {playlist_name} for {username}")
    return {"message": f"Deleted playlist {playlist_name}"}

@app.post("/delete_song")
async def delete_song(request: Request, song_id: int = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    song = c.fetchone()
    if not song:
        conn.close()
        raise HTTPException(status_code=404, detail="Song not found")
    if song[0]:
        file_path = MUSIC_DIR / song[0]
        if file_path.exists():
            os.remove(file_path)
            logger.debug(f"Removed file {file_path}")
    c.execute("DELETE FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    conn.commit()
    conn.close()
    logger.debug(f"Deleted song {song_id} for {username}")
    return {"message": "Song deleted"}

@app.post("/rearrange_playlist")
async def rearrange_playlist(request: Request, playlist_name: str = Form(...), song_ids: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        song_ids = [int(id) for id in song_ids.split(",") if id.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid song_ids format")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for position, song_id in enumerate(song_ids):
        c.execute("UPDATE songs SET position = ? WHERE id = ? AND playlist = ? AND user_id = ?", 
                 (position, song_id, playlist_name, username))
    conn.commit()
    conn.close()
    logger.debug(f"Rearranged {playlist_name} for {username}")
    return {"message": f"Rearranged {playlist_name}"}

@app.get("/search_youtube")
async def search_youtube(query: str):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch10',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch10:{query}", download=False)
        videos = result.get('entries', [])
        return {
            "results": [{"title": v['title'], "url": v['webpage_url'], "artist": v.get('uploader', 'Unknown')} for v in videos]
        }

@app.post("/upload_lyrics")
async def upload_lyrics(request: Request, song_id: int = Form(...), lyrics_file: UploadFile = File(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        raise HTTPException(status_code=401, detail="Unauthorized")
    lyrics_text = (await lyrics_file.read()).decode('utf-8').strip()
    if not lyrics_text:
        return JSONResponse(status_code=400, content={"success": False, "message": "Lyrics cannot be empty"})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Song not found")
    parsed_lyrics = parse_lyrics(lyrics_text)
    c.execute("UPDATE songs SET lyrics_text = ? WHERE id = ? AND user_id = ?", (json.dumps(parsed_lyrics), song_id, username))
    conn.commit()
    conn.close()
    logger.debug(f"Uploaded lyrics for song {song_id} for {username}")
    return JSONResponse({"success": True, "message": "Lyrics uploaded", "lyrics": parsed_lyrics})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True, log_level="debug")