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
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing (restrict in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Define paths relative to the project directory for portability
BASE_DIR = Path(__file__).parent
MUSIC_DIR = BASE_DIR / "music"
IMAGES_DIR = BASE_DIR / "static" / "images"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/music", StaticFiles(directory=MUSIC_DIR), name="music")
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

DB_PATH = BASE_DIR / "songs.db"  # Standardize on songs.db
DEFAULT_IMAGE = "default.jpg"

# In-memory user storage (use a database in production)
USERS_FILE = BASE_DIR / "users.json"
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

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )''')
    
    # Create playlists table with user_id
    c.execute('''CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        user_id TEXT NOT NULL,
        image_path TEXT DEFAULT '/static/images/default.jpg',
        FOREIGN KEY (user_id) REFERENCES users(username)
    )''')
    
    # Create songs table with user_id
    c.execute('''CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        playlist TEXT NOT NULL,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        artist TEXT NOT NULL,
        url TEXT NOT NULL,
        filename TEXT,
        lyrics_text TEXT,
        position INTEGER,
        FOREIGN KEY (user_id) REFERENCES users(username)
    )''')
    
    # Create lyrics table (if not already present)
    c.execute('''CREATE TABLE IF NOT EXISTS lyrics (
        song_id INTEGER,
        timestamp REAL,
        line TEXT,
        FOREIGN KEY (song_id) REFERENCES songs(id)
    )''')
    
    conn.commit()
    conn.close()
    logger.debug("Database initialized with user-specific tables")

def migrate_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if playlists table exists and get its columns
    c.execute("PRAGMA table_info(playlists)")
    columns = [col[1] for col in c.fetchall()]
    
    # If image column exists but image_path doesn't, rename image to image_path
    if 'image' in columns and 'image_path' not in columns:
        try:
            c.execute("ALTER TABLE playlists RENAME COLUMN image TO image_path")
            logger.debug("Renamed column 'image' to 'image_path' in playlists table")
        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to rename 'image' to 'image_path': {e}")
    
    # If image_path column doesn't exist, add it
    if 'image_path' not in columns:
        try:
            c.execute("ALTER TABLE playlists ADD COLUMN image_path TEXT DEFAULT '/static/images/default.jpg'")
            logger.debug("Added 'image_path' column to playlists table")
        except sqlite3.OperationalError as e:
            logger.warning(f"Failed to add 'image_path' column: {e}")
    
    # Check if songs table has all required columns
    c.execute("PRAGMA table_info(songs)")
    song_columns = [col[1] for col in c.fetchall()]
    
    # Add missing columns to songs table if they don't exist
    if 'filename' not in song_columns:
        c.execute("ALTER TABLE songs ADD COLUMN filename TEXT")
        logger.debug("Added 'filename' column to songs table")
    if 'lyrics_text' not in song_columns:
        c.execute("ALTER TABLE songs ADD COLUMN lyrics_text TEXT")
        logger.debug("Added 'lyrics_text' column to songs table")
    
    conn.commit()
    conn.close()
    logger.debug("Database migration completed")

def index_songs(username="Ash"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Ensure the user exists in the users table
    c.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", (username, hash_password("default_password")))
    
    # Create user-specific directory
    user_dir = MUSIC_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Seed playlists
    playlists = ["Chill Hits", "Rock Classics", "Pop Party"]
    for playlist_name in playlists:
        c.execute("SELECT COUNT(*) FROM playlists WHERE name = ? AND user_id = ?", (playlist_name, username))
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO playlists (name, user_id, image_path) VALUES (?, ?, ?)", 
                      (playlist_name, username, f"/static/images/{DEFAULT_IMAGE}"))
            logger.debug(f"Added playlist {playlist_name} for user {username} to database")
            (user_dir / playlist_name).mkdir(parents=True, exist_ok=True)

    # Seed songs (using YouTube URLs)
    songs_data = [
        ("Chill Hits", username, "Song 1", "Artist 1", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", 1),
        ("Rock Classics", username, "Song 2", "Artist 2", "https://www.youtube.com/watch?v=3tmd-ClpJxA", 1),
        ("Pop Party", username, "Song 3", "Artist 3", "https://www.youtube.com/watch?v=OPf0YbXqDm0", 1),
    ]

    for playlist, user_id, title, artist, url, position in songs_data:
        c.execute("SELECT COUNT(*) FROM songs WHERE url = ? AND user_id = ?", (url, user_id))
        if c.fetchone()[0] == 0:
            playlist_dir = user_dir / playlist
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
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    downloaded_file = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
                    filename = f"{user_id}/{playlist}/{downloaded_file.name}"
                    os.rename(downloaded_file, playlist_dir / downloaded_file.name)
                    c.execute("INSERT INTO songs (playlist, user_id, title, artist, url, filename, position) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (playlist, user_id, title, artist, url, filename, position))
                    logger.debug(f"Indexed song: {title} in playlist {playlist} for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to download initial song {title}: {e}")
                continue

    conn.commit()
    conn.close()

def parse_lyrics(lyrics_text: str) -> List[Dict[str, float | str]]:
    lines = lyrics_text.split('\n')
    parsed_lyrics = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\[(\d{2}):(\d{2}\.\d{2})\](.*)$', line)
        if match:
            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()
            time = minutes * 60 + seconds
            if 0 <= time < 3600:  # Ensure time is reasonable (less than 1 hour)
                parsed_lyrics.append({"time": time, "text": text})
            else:
                logger.warning(f"Invalid timestamp {time} seconds in line: {line}, skipping")
        else:
            logger.warning(f"Unrecognized line format, skipping: {line}")
    # Sort by timestamp to ensure correct order
    parsed_lyrics.sort(key=lambda x: x["time"])
    return parsed_lyrics

# Initialize database, migrate, and index songs on startup
init_db()
migrate_db()
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
        logger.debug(f"Login successful for username: {username}, redirecting to /index")
        response = RedirectResponse(url="/index", status_code=303)
        response.set_cookie(key="session_username", value=username, httponly=True, max_age=3600, samesite="Lax")
        return response
    logger.warning(f"Login failed for username: {username} - Invalid credentials")
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials, try again"})

@app.get("/index", response_class=HTMLResponse)
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
async def get_songs(request: Request):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.debug("Unauthorized access to /songs, returning empty list")
        return JSONResponse(content=[])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, artist, url, playlist, position, lyrics_text FROM songs WHERE user_id = ? ORDER BY playlist, position", (username,))
    songs = []
    for row in c.fetchall():
        lyrics = row[6]
        if lyrics:
            try:
                lyrics_data = json.loads(lyrics)
                for lyric in lyrics_data:
                    if not isinstance(lyric.get("time"), (int, float)) or lyric["time"] < 0 or lyric["time"] >= 3600:
                        logger.warning(f"Invalid time value {lyric.get('time')} for song id {row[0]}, resetting to 0")
                        lyric["time"] = 0
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse lyrics for song id {row[0]}: {e}")
                lyrics_data = None
        else:
            lyrics_data = None
        songs.append({
            "id": row[0],
            "title": row[1],
            "artist": row[2],
            "url": row[3],
            "playlist": row[4],
            "position": row[5],
            "lyrics": lyrics_data
        })
    conn.close()
    logger.debug(f"Fetched {len(songs)} songs for user {username}")
    return JSONResponse(content=songs)

@app.get("/playlists")
async def get_playlists(request: Request):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.debug("Unauthorized access to /playlists, returning empty list")
        return {"playlists": []}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, image_path, id FROM playlists WHERE user_id = ?", (username,))
    playlists = [{"name": row[0], "image": row[1], "id": row[2]} for row in c.fetchall()]
    conn.close()
    logger.debug(f"Fetched {len(playlists)} playlists for user {username}")
    return {"playlists": playlists}

@app.get("/song/{song_id}")
async def get_song(song_id: int, request: Request):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning(f"Unauthorized access to /song/{song_id}")
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    song = c.fetchone()
    conn.close()
    if not song or not song[0]:
        logger.warning(f"Song with id {song_id} not found for user {username}")
        raise HTTPException(status_code=404, detail="Song not found")
    file_path = MUSIC_DIR / song[0]
    if not file_path.exists():
        logger.warning(f"Song file {file_path} not found on disk")
        raise HTTPException(status_code=404, detail="Song file not found on disk")
    logger.debug(f"Serving song file: {file_path} for user {username}")
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
    
    # Create user-specific directory on signup
    user_dir = MUSIC_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)
    
    logger.debug(f"Created user directory: {user_dir} for user {username}")
    response = RedirectResponse(url="/login", status_code=303)
    response.set_cookie(key="session_username", value=username, httponly=True, max_age=3600, samesite="Lax")
    return response

@app.post("/create_playlist")
async def create_playlist(request: Request, playlist_name: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized playlist creation attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not playlist_name.strip():
        logger.warning("Attempted to create playlist with empty name")
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
        logger.warning(f"Playlist {playlist_name} already exists for user {username}")
        return JSONResponse(status_code=400, content={"message": f"Playlist {playlist_name} already exists"})
    c.execute("INSERT INTO playlists (name, image_path, user_id) VALUES (?, ?, ?)", 
              (playlist_name, f"/static/images/{DEFAULT_IMAGE}", username))
    conn.commit()
    conn.close()
    logger.debug(f"Created playlist: {playlist_name} for user {username}")
    return {"message": f"Playlist {playlist_name} created"}

@app.post("/update_playlist_image")
async def update_playlist_image(request: Request, playlist_id: int = Form(...), image: UploadFile = File(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized playlist image update attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT image_path, name FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    existing_playlist = c.fetchone()
    if not existing_playlist:
        conn.close()
        logger.warning(f"Playlist with id {playlist_id} not found for user {username}")
        raise HTTPException(status_code=404, detail="Playlist not found")
    if existing_playlist[0] and not existing_playlist[0].endswith(DEFAULT_IMAGE):
        old_image_path = IMAGES_DIR / Path(existing_playlist[0]).name
        if old_image_path.exists():
            try:
                os.remove(old_image_path)
                logger.debug(f"Removed old playlist image: {old_image_path}")
            except OSError as e:
                logger.warning(f"Failed to remove old playlist image {old_image_path}: {e}")
    file_extension = image.filename.split('.')[-1].lower()
    image_filename = f"{uuid.uuid4()}.{file_extension}"
    image_path = IMAGES_DIR / image_filename
    try:
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    except Exception as e:
        logger.error(f"Failed to save playlist image {image_filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save playlist image")
    c.execute("UPDATE playlists SET image_path = ? WHERE id = ?", (f"/static/images/{image_filename}", playlist_id))
    conn.commit()
    conn.close()
    logger.debug(f"Updated image for playlist {existing_playlist[1]} for user {username}")
    return {"message": f"Image updated for playlist {existing_playlist[1]}"}

@app.post("/rename_playlist")
async def rename_playlist(request: Request, playlist_id: int = Form(...), new_name: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized playlist rename attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not new_name.strip():
        logger.warning("Attempted to rename playlist to empty name")
        return JSONResponse(status_code=400, content={"message": "New playlist name cannot be empty"})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    old_name_row = c.fetchone()
    if not old_name_row:
        conn.close()
        logger.warning(f"Playlist with id {playlist_id} not found for user {username}")
        raise HTTPException(status_code=404, detail="Playlist not found")
    old_name = old_name_row[0]
    c.execute("SELECT COUNT(*) FROM playlists WHERE name = ? AND user_id = ?", (new_name, username))
    if c.fetchone()[0] > 0:
        conn.close()
        logger.warning(f"Playlist name {new_name} already exists for user {username}")
        return JSONResponse(status_code=400, content={"message": f"Playlist name {new_name} already exists"})
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
                    try:
                        shutil.move(str(song_file), str(target_path))
                        logger.debug(f"Moved song file {song_file} to {target_path}")
                    except OSError as e:
                        logger.warning(f"Failed to move song file {song_file}: {e}")
                relative_filename = f"{username}/{new_name}/{song_file.name}"
                c.execute("UPDATE songs SET filename = ? WHERE filename = ?", 
                         (relative_filename, f"{username}/{old_name}/{song_file.name}"))
            try:
                old_playlist_dir.rmdir()
                logger.debug(f"Removed old playlist directory: {old_playlist_dir}")
            except OSError as e:
                logger.warning(f"Failed to remove old playlist directory {old_playlist_dir}: {e}")
        else:
            try:
                old_playlist_dir.rename(new_playlist_dir)
                logger.debug(f"Renamed playlist directory from {old_playlist_dir} to {new_playlist_dir}")
            except OSError as e:
                logger.warning(f"Failed to rename playlist directory {old_playlist_dir}: {e}")
    conn.commit()
    conn.close()
    logger.debug(f"Renamed playlist from {old_name} to {new_name} for user {username}")
    return {"message": f"Playlist renamed from {old_name} to {new_name}"}

@app.post("/add_song")
async def add_song(request: Request, playlist_name: str = Form(...), youtube_url: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized song addition attempt")
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
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            downloaded_file = Path(ydl.prepare_filename(info)).with_suffix('.mp3')
            filename = f"{username}/{playlist_name}/{downloaded_file.name}"
            os.rename(downloaded_file, playlist_dir / downloaded_file.name)  # Ensure file is in user-specific directory
    except Exception as e:
        logger.error(f"Failed to download song: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download song: {str(e)}")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT MAX(position) FROM songs WHERE playlist = ? AND user_id = ?", (playlist_name, username))
    max_position = c.fetchone()[0] or -1
    title = info.get('title', 'Unknown Title')
    artist = info.get('uploader', 'Unknown Artist').replace(" - Topic", "")
    c.execute("INSERT INTO songs (title, artist, url, filename, playlist, position, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (title, artist, youtube_url, filename, playlist_name, max_position + 1, username))
    conn.commit()
    conn.close()
    logger.debug(f"Added song {title} to playlist {playlist_name} for user {username}")
    return {"message": f"Added {title} to {playlist_name}"}

@app.post("/delete_playlist")
async def delete_playlist(request: Request, playlist_id: int = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized playlist deletion attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, image_path FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    playlist = c.fetchone()
    if not playlist:
        conn.close()
        logger.warning(f"Playlist with id {playlist_id} not found for user {username}")
        raise HTTPException(status_code=404, detail="Playlist not found")
    playlist_name = playlist[0]
    playlist_dir = MUSIC_DIR / username / playlist_name
    if playlist_dir.exists():
        try:
            shutil.rmtree(playlist_dir)
            logger.debug(f"Removed playlist directory: {playlist_dir}")
        except OSError as e:
            logger.warning(f"Failed to remove playlist directory {playlist_dir}: {e}")
    if playlist[1] and not playlist[1].endswith(DEFAULT_IMAGE):
        image_path = IMAGES_DIR / Path(playlist[1]).name
        if image_path.exists():
            try:
                os.remove(image_path)
                logger.debug(f"Removed playlist image: {image_path}")
            except OSError as e:
                logger.warning(f"Failed to remove playlist image {image_path}: {e}")
    c.execute("DELETE FROM playlists WHERE id = ? AND user_id = ?", (playlist_id, username))
    c.execute("DELETE FROM songs WHERE playlist = ? AND user_id = ?", (playlist_name, username))
    conn.commit()
    conn.close()
    logger.debug(f"Deleted playlist {playlist_name} for user {username}")
    return {"message": f"Deleted playlist {playlist_name}"}

@app.post("/delete_song")
async def delete_song(request: Request, song_id: int = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized song deletion attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT filename FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    song = c.fetchone()
    if not song:
        conn.close()
        logger.warning(f"Song with id {song_id} not found for user {username}")
        raise HTTPException(status_code=404, detail="Song not found")
    if song[0]:  # Check if filename exists
        file_path = MUSIC_DIR / song[0]
        if file_path.exists():
            try:
                os.remove(file_path)
                logger.debug(f"Removed song file: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to remove song file {file_path}: {e}")
    c.execute("DELETE FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    conn.commit()
    conn.close()
    logger.debug(f"Deleted song with id {song_id} for user {username}")
    return {"message": "Song deleted"}

@app.post("/rearrange_playlist")
async def rearrange_playlist(request: Request, playlist_name: str = Form(...), song_ids: str = Form(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized playlist rearrangement attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        song_ids = [int(id) for id in song_ids.split(",")]
    except ValueError as e:
        logger.warning(f"Invalid song_ids format: {song_ids}, error: {e}")
        raise HTTPException(status_code=400, detail="Invalid song_ids format")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for position, song_id in enumerate(song_ids):
        c.execute("UPDATE songs SET position = ? WHERE id = ? AND playlist = ? AND user_id = ?", 
                 (position, song_id, playlist_name, username))
    conn.commit()
    conn.close()
    logger.debug(f"Rearranged playlist {playlist_name} for user {username}")
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

@app.post("/upload_lyrics")
async def upload_lyrics(request: Request, song_id: int = Form(...), lyrics_file: UploadFile = File(...)):
    username = request.cookies.get("session_username")
    if not username or username not in users:
        logger.warning("Unauthorized lyrics upload attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        lyrics_text = await lyrics_file.read()
        lyrics_text = lyrics_text.decode('utf-8')
    except Exception as e:
        logger.warning(f"Failed to read lyrics file for song_id {song_id}: {str(e)}")
        return JSONResponse(status_code=400, content={"success": False, "message": "Failed to read the lyrics file"})
    if not lyrics_text.strip():
        logger.warning(f"Empty lyrics file uploaded for song_id {song_id}")
        return JSONResponse(status_code=400, content={"success": False, "message": "Lyrics file cannot be empty"})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM songs WHERE id = ? AND user_id = ?", (song_id, username))
    if not c.fetchone():
        conn.close()
        logger.warning(f"Song with id {song_id} not found for user {username}")
        raise HTTPException(status_code=404, detail="Song not found")
    parsed_lyrics = parse_lyrics(lyrics_text)
    lyrics_json = json.dumps(parsed_lyrics)
    c.execute("UPDATE songs SET lyrics_text = ? WHERE id = ? AND user_id = ?", (lyrics_json, song_id, username))
    conn.commit()
    conn.close()
    logger.debug(f"Updated lyrics for song_id {song_id} from uploaded file for user {username}")
    return JSONResponse({
        "success": True,
        "message": "Lyrics uploaded successfully",
        "lyrics": parsed_lyrics
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True, log_level="debug")