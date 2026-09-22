"""Music library scanning - genres, albums, songs, cover art.

Pure functions, no Flask/web dependency, so they're easy to test standalone.
Mirrors the folder convention already used by the desktop app (app.py):
    MUSIC_DIR/<genre lowercase>/<album folder>/*.mp3 (+ optional metadata.json, cover.jpg)
"""
import os
from io import BytesIO
from PIL import Image, ImageDraw
from mutagen.id3 import ID3, APIC, TIT2, TPE1
import json

# Same override pattern as the desktop app - lets Termux point this at its own storage.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get(
    "MYFAV_DATA_DIR",
    os.path.join(os.path.dirname(BASE_DIR), "..", "MyFavoriteThingsData"),
)
DATA_DIR = os.path.abspath(DATA_DIR)
MUSIC_DIR = os.path.join(DATA_DIR, "music")

os.makedirs(MUSIC_DIR, exist_ok=True)

COVER_FILENAMES = ["cover.jpg", "cover.png", "album.jpg", "folder.jpg"]


def safe_join(base, *parts):
    """Joins path parts onto base, refusing anything that escapes base
    (blocks '..' traversal and absolute-path injection from URL segments)."""
    base = os.path.abspath(base)
    candidate = os.path.abspath(os.path.join(base, *parts))
    if os.path.commonpath([base, candidate]) != base:
        raise ValueError("path escapes base directory")
    return candidate


def list_genres():
    if not os.path.isdir(MUSIC_DIR):
        return []
    return sorted(
        d.upper() for d in os.listdir(MUSIC_DIR)
        if os.path.isdir(os.path.join(MUSIC_DIR, d))
    )


def _read_album_meta(album_path):
    meta = {"title": os.path.basename(album_path).upper(), "artist": "Unknown Artist"}
    json_path = os.path.join(album_path, "metadata.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r") as f:
                meta.update(json.load(f))
            return meta
        except Exception:
            pass
    try:
        mp3s = [f for f in os.listdir(album_path) if f.lower().endswith(".mp3")]
        if mp3s:
            audio = ID3(os.path.join(album_path, mp3s[0]))
            if "TIT2" in audio: meta["title"] = str(audio["TIT2"])
            if "TPE1" in audio: meta["artist"] = str(audio["TPE1"])
    except Exception:
        pass
    return meta


def _has_cover(album_path):
    if any(os.path.exists(os.path.join(album_path, f)) for f in COVER_FILENAMES):
        return True
    try:
        for f in os.listdir(album_path):
            if f.lower().endswith(".mp3"):
                audio = ID3(os.path.join(album_path, f))
                if any(isinstance(tag, APIC) for tag in audio.values()):
                    return True
    except Exception:
        pass
    return False


def list_albums(genre):
    genre_path = safe_join(MUSIC_DIR, genre.lower())
    if not os.path.isdir(genre_path):
        return []
    albums = []
    for folder in sorted(os.listdir(genre_path)):
        album_path = os.path.join(genre_path, folder)
        if not os.path.isdir(album_path):
            continue
        meta = _read_album_meta(album_path)
        albums.append({
            "folder": folder,
            "title": meta["title"],
            "artist": meta["artist"],
            "has_cover": _has_cover(album_path),
        })
    return albums


def list_songs(genre, album):
    album_path = safe_join(MUSIC_DIR, genre.lower(), album)
    if not os.path.isdir(album_path):
        return []
    return sorted(
        f for f in os.listdir(album_path)
        if f.lower().endswith((".mp3", ".m4a"))
    )


def get_song_path(genre, album, filename):
    path = safe_join(MUSIC_DIR, genre.lower(), album, filename)
    if not os.path.isfile(path):
        return None
    return path


def _default_cover_bytes():
    img = Image.new("RGB", (300, 300), color="#4a7c59")
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 292, 292], outline="white", width=3)
    d.text((90, 140), "NO COVER", fill="white")
    buf = BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue(), "image/jpeg"


def get_cover_bytes(genre, album):
    album_path = safe_join(MUSIC_DIR, genre.lower(), album)
    if not os.path.isdir(album_path):
        return _default_cover_bytes()

    for fname in COVER_FILENAMES:
        fpath = os.path.join(album_path, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, "rb") as f:
                    data = f.read()
                mime = "image/png" if fname.endswith(".png") else "image/jpeg"
                return data, mime
            except Exception:
                pass

    try:
        for f in os.listdir(album_path):
            if f.lower().endswith(".mp3"):
                audio = ID3(os.path.join(album_path, f))
                for tag in audio.values():
                    if isinstance(tag, APIC):
                        return tag.data, tag.mime or "image/jpeg"
    except Exception:
        pass

    return _default_cover_bytes()


def create_genre(name):
    name = name.strip()
    if not name:
        raise ValueError("genre name required")
    path = safe_join(MUSIC_DIR, name.lower())
    os.makedirs(path, exist_ok=True)


def create_album(genre, album, artist, title):
    path = safe_join(MUSIC_DIR, genre.lower(), album)
    os.makedirs(path, exist_ok=True)
    meta_path = os.path.join(path, "metadata.json")
    if not os.path.exists(meta_path):
        with open(meta_path, "w") as f:
            json.dump({"title": title or album, "artist": artist or "Unknown Artist"}, f)


def save_uploaded_song(genre, album, filename, file_stream):
    """filename is the ORIGINAL browser-supplied name - never trust it directly
    as a path; only its extension is used, the rest is re-derived safely."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".mp3", ".m4a"):
        raise ValueError("unsupported file type")
    safe_name = "".join(c for c in os.path.splitext(filename)[0] if c.isalnum() or c in (" ", "-", "_")).strip()
    safe_name = safe_name or "track"
    album_path = safe_join(MUSIC_DIR, genre.lower(), album)
    os.makedirs(album_path, exist_ok=True)
    dest = os.path.join(album_path, safe_name + ext)
    base = dest
    counter = 1
    while os.path.exists(dest):
        dest = f"{os.path.splitext(base)[0]}_{counter}{ext}"
        counter += 1
    file_stream.save(dest)
