from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import sqlite3
import os
import shutil
import logging
import yt_dlp
import urllib.parse
from typing import List, Dict
from pathlib import Path

app = FastAPI()

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/music", StaticFiles(directory="Music"), name="music")

# Initialize database
def init_db():
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                artist TEXT,
                filename TEXT,
                playlist TEXT,
                position INTEGER
            )''')
            c.execute('''CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                image TEXT
            )''')
            conn.commit()
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

init_db()

# Create necessary directories
os.makedirs("Music", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

# Index songs from Music directory
def index_songs():
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("DELETE FROM songs")
            for playlist in os.listdir("Music"):
                playlist_path = os.path.join("Music", playlist)
                if os.path.isdir(playlist_path):
                    position = 0
                    for song_file in os.listdir(playlist_path):
                        if song_file.endswith(".mp3"):
                            title = song_file.replace(".mp3", "")
                            artist = "Unknown Artist"
                            filename = f"/music/{urllib.parse.quote(playlist)}/{urllib.parse.quote(song_file)}"
                            c.execute("INSERT INTO songs (title, artist, filename, playlist, position) VALUES (?, ?, ?, ?, ?)",
                                      (title, artist, filename, playlist, position))
                            position += 1
            conn.commit()
            logger.info("Songs indexed successfully")
    except Exception as e:
        logger.error(f"Error indexing songs: {e}")
        raise

index_songs()

# Routes
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    try:
        with open("index.html") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        logger.error("index.html not found")
        raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/songs")
async def get_songs():
    try:
        with sqlite3.connect('songs.db') as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, title, artist, filename AS url, playlist, position FROM songs ORDER BY playlist, position")
            songs = [dict(row) for row in c.fetchall()]
            logger.debug(f"Retrieved songs: {songs}")
            return {"songs": songs}
    except Exception as e:
        logger.error(f"Error retrieving songs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/playlists")
async def get_playlists():
    try:
        with sqlite3.connect('songs.db') as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT id, name, image FROM playlists")
            playlists = [{"id": row["id"], "name": row["name"], "image": row["image"] or "/static/images/default.jpeg"} for row in c.fetchall()]
            logger.debug(f"Retrieved playlists: {playlists}")
            return {"playlists": playlists}
    except Exception as e:
        logger.error(f"Error retrieving playlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create_playlist")
async def create_playlist(playlist_name: str = Form(...)):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO playlists (name, image) VALUES (?, ?)", (playlist_name, "/static/images/default.jpeg"))
            conn.commit()
            logger.info(f"Created playlist: {playlist_name}")
            return {"message": f"Playlist '{playlist_name}' created successfully"}
    except Exception as e:
        logger.error(f"Error creating playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_song")
async def add_song(playlist_name: str = Form(...), youtube_url: str = Form(...)):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM playlists WHERE name = ?", (playlist_name,))
            if not c.fetchone():
                raise HTTPException(status_code=400, detail="Playlist not found")
            
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': f'Music/{playlist_name}/%(title)s.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                filename = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")
                title = info.get('title', 'Unknown Title')
                artist = info.get('uploader', 'Unknown Artist')
            
            os.makedirs(f"Music/{playlist_name}", exist_ok=True)
            c.execute("SELECT MAX(position) FROM songs WHERE playlist = ?", (playlist_name,))
            position = (c.fetchone()[0] or -1) + 1
            c.execute("INSERT INTO songs (title, artist, filename, playlist, position) VALUES (?, ?, ?, ?, ?)",
                      (title, artist, f"/music/{urllib.parse.quote(playlist_name)}/{urllib.parse.quote(Path(filename).name)}", playlist_name, position))
            conn.commit()
            logger.info(f"Added song '{title}' to playlist '{playlist_name}'")
            return {"message": f"Song '{title}' added to playlist '{playlist_name}'"}
    except Exception as e:
        logger.error(f"Error adding song: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete_playlist")
async def delete_playlist(playlist_id: int = Form(...)):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,))
            playlist = c.fetchone()
            if not playlist:
                raise HTTPException(status_code=400, detail="Playlist not found")
            playlist_name = playlist[0]
            c.execute("DELETE FROM songs WHERE playlist = ?", (playlist_name,))
            c.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
            conn.commit()
            shutil.rmtree(f"Music/{playlist_name}", ignore_errors=True)
            logger.info(f"Deleted playlist: {playlist_name}")
            return {"message": f"Playlist '{playlist_name}' deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/delete_song")
async def delete_song(song_id: int = Form(...)):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("SELECT filename, playlist FROM songs WHERE id = ?", (song_id,))
            song = c.fetchone()
            if not song:
                raise HTTPException(status_code=400, detail="Song not found")
            filename, playlist = song
            c.execute("DELETE FROM songs WHERE id = ?", (song_id,))
            c.execute("UPDATE songs SET position = position - 1 WHERE playlist = ? AND position > (SELECT position FROM songs WHERE id = ?)", 
                      (playlist, song_id))
            conn.commit()
            try:
                os.remove(filename.lstrip("/music/"))
            except FileNotFoundError:
                logger.warning(f"Song file not found: {filename}")
            logger.info(f"Deleted song ID: {song_id}")
            return {"message": "Song deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting song: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_playlist_image")
async def update_playlist_image(playlist_id: int = Form(...), image: UploadFile = File(...)):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,))
            playlist = c.fetchone()
            if not playlist:
                raise HTTPException(status_code=400, detail="Playlist not found")
            playlist_name = playlist[0]
            image_path = f"static/images/{playlist_name}_{image.filename}"
            with open(image_path, "wb") as f:
                f.write(await image.read())
            c.execute("UPDATE playlists SET image = ? WHERE id = ?", (f"/static/images/{urllib.parse.quote(playlist_name)}_{urllib.parse.quote(image.filename)}", playlist_id))
            conn.commit()
            logger.info(f"Updated image for playlist: {playlist_name}")
            return {"message": "Playlist image updated successfully"}
    except Exception as e:
        logger.error(f"Error updating playlist image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rename_playlist")
async def rename_playlist(playlist_id: int = Form(...), new_name: str = Form(...)):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM playlists WHERE id = ?", (playlist_id,))
            old_name = c.fetchone()
            if not old_name:
                raise HTTPException(status_code=400, detail="Playlist not found")
            old_name = old_name[0]
            c.execute("SELECT name FROM playlists WHERE name = ?", (new_name,))
            if c.fetchone():
                raise HTTPException(status_code=400, detail="Playlist name already exists")
            c.execute("UPDATE playlists SET name = ? WHERE id = ?", (new_name, playlist_id))
            c.execute("UPDATE songs SET playlist = ? WHERE playlist = ?", (new_name, old_name))
            conn.commit()
            if os.path.exists(f"Music/{old_name}"):
                os.rename(f"Music/{old_name}", f"Music/{new_name}")
            logger.info(f"Renamed playlist from {old_name} to {new_name}")
            return {"message": f"Playlist renamed to '{new_name}'"}
    except Exception as e:
        logger.error(f"Error renaming playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rearrange_playlist")
async def rearrange_playlist(playlist_name: str = Form(...), song_ids: str = Form(...)):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            song_ids_list = song_ids.split(",")
            for position, song_id in enumerate(song_ids_list):
                c.execute("UPDATE songs SET position = ? WHERE id = ? AND playlist = ?", (position, int(song_id), playlist_name))
            conn.commit()
            logger.info(f"Rearranged playlist: {playlist_name}")
            return {"message": "Playlist rearranged successfully"}
    except Exception as e:
        logger.error(f"Error rearranging playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search_youtube")
async def search_youtube(query: str):
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            result = ydl.extract_info(f"ytsearch5:{query}", download=False)
            videos = [
                {
                    "title": entry.get('title', 'Unknown Title'),
                    "artist": entry.get('uploader', 'Unknown Artist'),
                    "url": entry.get('webpage_url', '')
                }
                for entry in result.get('entries', [])
            ]
            logger.debug(f"YouTube search results for '{query}': {videos}")
            return {"results": videos}
    except Exception as e:
        logger.error(f"Error searching YouTube: {e}")
        return {"results": []}

@app.get("/song/{song_id}")
async def serve_song(song_id: int):
    try:
        with sqlite3.connect('songs.db') as conn:
            c = conn.cursor()
            c.execute("SELECT filename FROM songs WHERE id = ?", (song_id,))
            song = c.fetchone()
            if not song:
                logger.error(f"Song ID {song_id} not found")
                raise HTTPException(status_code=404, detail="Song not found")
            song_path = song[0].lstrip("/music/")
            if not os.path.exists(song_path):
                logger.error(f"Song file not found: {song_path}")
                raise HTTPException(status_code=404, detail="Song file not found")
            logger.debug(f"Serving song: {song_path}")
            return FileResponse(song_path, media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Error serving song ID {song_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))