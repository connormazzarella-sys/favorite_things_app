import os
import sys
import shutil
import json
import random
import threading
import subprocess
import re
import colorsys
import requests
from urllib.parse import urljoin
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, colorchooser
from datetime import datetime
import pygame
from PIL import Image, ImageTk, ImageSequence, ImageDraw
from io import BytesIO
from tkinterdnd2 import TkinterDnD, DND_FILES, DND_TEXT

# --- EXTERNAL LIBRARIES ---
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1

# Hide Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# --- CONFIGURATION ---
# When frozen by PyInstaller, __file__ points into a temp extraction folder,
# not the real exe location, so data/binaries would be lost between runs.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("MYFAV_DATA_DIR", os.path.join(BASE_DIR, "MyFavoriteThingsData"))

THEME = {
    "bg": "#ffffff",
    "card": "#f8f9fa",
    "accent": "#4a7c59",
    "vibrant_green": "#2ecc71",
    "entry_bg": "#eafaf1",
    "text": "#1a1a1a",
    "btn": "#f5f5f5",
    "paper": "#fffcf5",
    "lines": "#e0d9c5",
    "highlight": "#dcedc8"
}

# --- THEME STARTING POINTS ---
# Purely optional color presets offered when the user creates a new theme in
# the Theme tab - the user always picks, edits, names, and saves their own
# themes; these are just convenient seasonal starting palettes, not imposed.
THEME_PRESETS = {
    # Dark mode is auto-derived from whichever theme is active (see make_dark_variant),
    # so presets only need to cover distinct light-mode starting points - no more
    # separate "X Light" / "X Dark" pairs needed.
    "Blank (current colors)": {},
    "Winter": {"bg": "#ffffff", "text": "#1a1a1a", "accent": "#3b6e8f", "entry_bg": "#eaf3fa", "highlight": "#cfe8f3"},
    "Spring": {"bg": "#ffffff", "text": "#1a1a1a", "accent": "#5ea16a", "entry_bg": "#eafaf0", "highlight": "#d7f2c2"},
    "Summer": {"bg": "#ffffff", "text": "#1a1a1a", "accent": "#e08e2b", "entry_bg": "#fff8e6", "highlight": "#ffe6a8"},
    "Autumn": {"bg": "#ffffff", "text": "#1a1a1a", "accent": "#b5651d", "entry_bg": "#fdf0e1", "highlight": "#f2d19e"},
    # A couple of well-known, freely-published editor palettes (colors aren't
    # copyrightable - these are just widely-used, publicly documented hex values)
    "Nord": {"bg": "#2e3440", "text": "#eceff4", "accent": "#88c0d0", "entry_bg": "#3b4252", "highlight": "#81a1c1"},
    "Dracula": {"bg": "#282a36", "text": "#f8f8f2", "accent": "#bd93f9", "entry_bg": "#44475a", "highlight": "#ff79c6"},
}
THEME_COLOR_KEYS = ["bg", "text", "accent", "entry_bg", "highlight"]  # the ones exposed for editing

def _hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def _rgb_to_hex(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(c))) for c in rgb)

def _blend(hex1, hex2, t):
    r1, g1, b1 = _hex_to_rgb(hex1); r2, g2, b2 = _hex_to_rgb(hex2)
    return _rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))

def derive_full_theme(colors):
    """Every widget surface beyond the 5 user-picked colors (button/card/paper/
    divider) is computed from bg/text, so ANY theme - built-in or custom - gets
    a coherent, readable button/journal surface without the user picking 10+ colors."""
    full = dict(colors)
    bg = full.get("bg", "#ffffff")
    text = full.get("text", "#1a1a1a")
    full["btn"] = _blend(bg, text, 0.18)
    full["card"] = _blend(bg, text, 0.06)
    full["paper"] = _blend(bg, text, 0.05)
    full["lines"] = _blend(bg, text, 0.30)
    full["vibrant_green"] = "#2ecc71"
    return full

def make_dark_variant(colors):
    """Derives a dark mode FROM the theme's own accent hue, so e.g. Autumn's dark
    mode reads as a dark burnt orange, not a generic near-black - the theme's
    character carries through instead of dark mode washing it out to neutral."""
    h, l, s = colorsys.rgb_to_hls(*(c / 255 for c in _hex_to_rgb(colors.get("accent", "#4a7c59"))))
    def hls_hex(lightness, saturation):
        r, g, b = colorsys.hls_to_rgb(h, lightness, saturation)
        return _rgb_to_hex((r * 255, g * 255, b * 255))
    sat = max(0.45, s)  # keep the hue visibly present rather than washed toward gray
    return {
        "bg": hls_hex(0.20, sat),
        "text": "#f5f0e8",
        "accent": hls_hex(max(0.62, l), min(1.0, sat + 0.15)),
        "entry_bg": hls_hex(0.27, sat),
        "highlight": hls_hex(0.36, sat),
    }

MUSIC_DIR = os.path.join(DATA_DIR, "music")
JOURNAL_DIR = os.path.join(DATA_DIR, "journals")
SETTINGS_FILE = os.path.join(DATA_DIR, "favorites.json")

# --- RADIO ---
# Stations are found via the free, keyless Radio Browser API (radio-browser.info)
# and added manually by the user - only stations with a real, health-checked
# direct stream URL ever show up in search, so every result is playable.
RADIO_SEARCH_API = "https://de1.api.radio-browser.info/json/stations/search"

for d in [MUSIC_DIR, JOURNAL_DIR]:
    os.makedirs(d, exist_ok=True)

class MyFavoriteThingsApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        
        # 1. DATA INITIALIZATION
        self.settings = self.load_settings()
        self.favorites = self.settings.get("favorites", {"Books": [], "Songs": [], "Artists": [], "Movies": []})
        self.current_gif_path = self.settings.get("gif_path", "")
        
        self.all_genres = []
        self.current_songs_list = []
        self.current_playback_path = ""
        self.is_paused = False
        self.shuffle_on = False
        self.gif_frames = []
        self.gif_pil_frames = []
        self.gif_durations = []
        self.gif_idx = 0
        self.gif_size = self.settings.get("gif_size", 60)
        self.gif_speed = self.settings.get("gif_speed", 1.0)  # multiplier on each frame's native duration
        self.gif_after_id = None
        self.song_length = 0
        self.autosave_timer = None
        self.loaded_journal_file = None
        self.my_radio_stations = self.settings.get("radio_stations", [])  # [{"name":..,"url":..}, ...]
        self.radio_search_results = []
        self.radio_proc = None
        self.radio_playing_name = None

        # --- THEMES (fully user-authored: colors + header decoration gifs) ---
        self.themes = self.settings.get("themes", {})
        if not self.themes:
            self.themes["Default"] = {"colors": {k: THEME[k] for k in THEME_COLOR_KEYS}, "decorations": []}
        self.active_theme_name = self.settings.get("active_theme", "Default")
        if self.active_theme_name not in self.themes:
            self.active_theme_name = next(iter(self.themes))
        # Dark mode is a derived variant of whichever theme is active (see
        # make_dark_variant) - not a separate theme, so it always carries that
        # theme's own hue (e.g. Autumn's dark mode is warm brown, not neutral black).
        self.dark_mode = self.settings.get("dark_mode", False)
        self._apply_active_theme_colors()
        self.decoration_widgets = []  # [{"label":.., "frames":[PhotoImage,...], "idx":0, "record":dec}, ...]

        pygame.mixer.init()
        self.header_font = ("Verdana", 14, "bold")
        self.clock_font = ("Georgia", 22, "bold")
        self.list_font = ("Segoe UI", 10, "bold")
        self.ctrl_font = ("Segoe UI", 16, "bold")
        self.journal_font = ("Brush Script MT", 22)
        self.journal_title_font = ("Georgia", 16, "italic")

        self.title("My Favorite Things - Pro Edition")
        self.geometry("1550x950")
        self.configure(bg=THEME["bg"])
        
        # 2. UI SETUP
        self.setup_header()
        self.setup_notebook()
        
        self.init_music_tab()
        self.init_journal_tab()
        self.init_favorites_tab()
        self.init_radio_tab()
        self.init_theme_tab()

        # 3. LOAD DATA
        self.refresh_genres()
        self.refresh_journals()
        self.update_clock()
        self.check_music_end()

        if self.current_gif_path and os.path.exists(self.current_gif_path):
            self.load_gif_from_path(self.current_gif_path)

        self.render_decorations()

        self.drop_target_register(DND_FILES, DND_TEXT)
        self.dnd_bind('<<Drop>>', self.on_gif_drop)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f: return json.load(f)
            except: pass
        return {"gif_path": "", "favorites": {"Books": [], "Songs": [], "Artists": [], "Movies": []}, "radio_stations": [],
                "themes": {}, "active_theme": "Default"}

    def save_all_data(self):
        data = {
            "gif_path": self.current_gif_path, "gif_size": self.gif_size, "gif_speed": self.gif_speed,
            "favorites": self.favorites, "radio_stations": self.my_radio_stations,
            "themes": self.themes, "active_theme": self.active_theme_name, "dark_mode": self.dark_mode,
        }
        with open(SETTINGS_FILE, "w") as f: json.dump(data, f, indent=4)

    def update_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self.update_clock)

    def on_closing(self):
        self.save_all_data()
        self.stop_all_radio()
        pygame.mixer.quit()
        self.destroy()

    # ==========================
    # UI: MUSIC TAB
    # ==========================
    def init_music_tab(self):
        self.m_left = tk.Frame(self.music_tab, width=260, bg=THEME["bg"], borderwidth=1, relief="solid")
        self.m_left.pack(side="left", fill="y", padx=2, pady=2); self.m_left.pack_propagate(False)
        tk.Label(self.m_left, text="GENRES", font=self.header_font, bg=THEME["bg"], fg=THEME["text"]).pack(pady=(10,5))

        btn_g_f = tk.Frame(self.m_left, bg=THEME["bg"]); btn_g_f.pack(fill="x", pady=5)
        inner_btn_f = tk.Frame(btn_g_f, bg=THEME["bg"]); inner_btn_f.pack(expand=True)
        tk.Button(inner_btn_f, text="+", font=("Arial", 11, "bold"), width=4, bg=THEME["btn"], fg=THEME["text"], command=self.add_genre).pack(side="left", padx=2)
        tk.Button(inner_btn_f, text="-", font=("Arial", 11, "bold"), width=4, bg=THEME["btn"], fg=THEME["text"], command=self.remove_genre).pack(side="left", padx=2)
        tk.Button(inner_btn_f, text="Edit", font=("Arial", 11, "bold"), width=6, bg=THEME["btn"], fg=THEME["text"], command=self.rename_genre).pack(side="left", padx=2)
        
        self.genre_canvas = tk.Canvas(self.m_left, bg=THEME["bg"], highlightthickness=0)
        self.genre_scroll = ttk.Scrollbar(self.m_left, orient="vertical", command=self.genre_canvas.yview)
        self.genre_frame = tk.Frame(self.genre_canvas, bg=THEME["bg"])
        self.genre_canvas.create_window((0, 0), window=self.genre_frame, anchor="nw", width=240)
        self.genre_frame.bind("<Configure>", lambda e: self.genre_canvas.configure(scrollregion=self.genre_canvas.bbox("all")))
        self.genre_canvas.pack(side="left", fill="both", expand=True, padx=5); self.genre_scroll.pack(side="right", fill="y")
        self.genre_canvas.configure(yscrollcommand=self.genre_scroll.set)

        self.m_right = tk.Frame(self.music_tab, width=320, bg=THEME["bg"], borderwidth=1, relief="solid")
        self.m_right.pack(side="right", fill="y", padx=2, pady=2); self.m_right.pack_propagate(False)
        self.album_info_label = tk.Label(self.m_right, text="SELECT AN ALBUM", font=("Segoe UI", 11, "bold"), bg=THEME["bg"], fg=THEME["text"], wraplength=280)
        self.album_info_label.pack(pady=15)
        tk.Frame(self.m_right, height=2, bg=THEME["accent"]).pack(fill="x", padx=20, pady=5)
        self.song_box = tk.Listbox(self.m_right, font=self.list_font, bg=THEME["bg"], fg=THEME["text"], borderwidth=0, activestyle='none', selectbackground=THEME["accent"], selectforeground="white")
        self.song_box.pack(fill="both", expand=True, padx=5, pady=5)
        self.song_box.bind("<Double-1>", lambda e: self.play_song())

        self.m_center = tk.Frame(self.music_tab, bg=THEME["bg"]); self.m_center.pack(side="left", fill="both", expand=True)
        self.control_bar = tk.Frame(self.m_center, height=180, bg=THEME["bg"], borderwidth=1, relief="solid")
        self.control_bar.pack(side="bottom", fill="x", padx=2, pady=2); self.control_bar.pack_propagate(False)
        self.track_info_main = tk.Label(self.control_bar, text="---", font=("Segoe UI", 11, "bold"), bg=THEME["bg"], fg=THEME["text"])
        self.track_info_main.pack(pady=(10, 0))
        self.prog_bar = ttk.Progressbar(self.control_bar, length=500, mode='determinate')
        self.prog_bar.pack(pady=10)

        self.center_btn_container = tk.Frame(self.control_bar, bg=THEME["bg"]); self.center_btn_container.pack(expand=True)
        tk.Button(self.center_btn_container, text="⏮", font=self.ctrl_font, width=4, bg=THEME["btn"], fg=THEME["text"], command=lambda: self.skip_song(prev=True)).pack(side="left", padx=5)
        tk.Button(self.center_btn_container, text="▶", font=self.ctrl_font, width=4, bg=THEME["btn"], fg=THEME["text"], command=self.resume_music).pack(side="left", padx=5)
        tk.Button(self.center_btn_container, text="⏸", font=self.ctrl_font, width=4, bg=THEME["btn"], fg=THEME["text"], command=self.pause_music).pack(side="left", padx=5)
        tk.Button(self.center_btn_container, text="⏭", font=self.ctrl_font, width=4, bg=THEME["btn"], fg=THEME["text"], command=self.skip_song).pack(side="left", padx=5)
        tk.Frame(self.center_btn_container, width=30, bg=THEME["bg"]).pack(side="left")
        self.shuffle_btn = tk.Button(self.center_btn_container, text="🔀 OFF", font=self.ctrl_font, width=8, bg=THEME["btn"], fg=THEME["text"], command=self.toggle_shuffle)
        self.shuffle_btn.pack(side="left", padx=10)
        vol_f = tk.Frame(self.center_btn_container, bg=THEME["bg"]); vol_f.pack(side="left", padx=5)
        tk.Label(vol_f, text="VOL", font=("Segoe UI", 8, "bold"), bg=THEME["bg"], fg=THEME["text"]).pack()
        ttk.Scale(vol_f, from_=0, to=1, orient="horizontal", command=self.set_volume, length=100).pack()
        
        self.canvas = tk.Canvas(self.m_center, bg=THEME["bg"], highlightthickness=0)
        self.scroll = ttk.Scrollbar(self.m_center, orient="vertical", command=self.canvas.yview)
        self.grid_frame = tk.Frame(self.canvas, bg=THEME["bg"])
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side="left", fill="both", expand=True); self.scroll.pack(side="right", fill="y")

    # ==========================
    # LOGIC: GENRES
    # ==========================
    def refresh_genres(self):
        self.all_genres = sorted([d.upper() for d in os.listdir(MUSIC_DIR) if os.path.isdir(os.path.join(MUSIC_DIR, d))])
        for widget in self.genre_frame.winfo_children(): widget.destroy()
        for g in self.all_genres:
            btn = tk.Button(self.genre_frame, text=g, font=("Segoe UI", 10, "bold"), bg=THEME["btn"], fg=THEME["text"], height=2, width=25, command=lambda genre=g: self.load_genre_view(genre))
            btn.pack(pady=2, padx=5, fill="x")

    def add_genre(self):
        n = simpledialog.askstring("New", "Genre Name:")
        if n: os.makedirs(os.path.join(MUSIC_DIR, n.lower()), exist_ok=True); self.refresh_genres()

    def remove_genre(self):
        n = simpledialog.askstring("Delete", "Exact Genre Name to Delete:")
        if n and n.upper() in self.all_genres and messagebox.askyesno("Confirm", f"Delete {n}?"):
            shutil.rmtree(os.path.join(MUSIC_DIR, n.lower())); self.refresh_genres()

    def rename_genre(self):
        old = simpledialog.askstring("Rename", "Old Genre Name:")
        if old and old.upper() in self.all_genres:
            new = simpledialog.askstring("Rename", "New Genre Name:")
            if new: os.rename(os.path.join(MUSIC_DIR, old.lower()), os.path.join(MUSIC_DIR, new.lower())); self.refresh_genres()

    # ==========================
    # LOGIC: ALBUM GRID (DEFAULT COVER + ID3)
    # ==========================
    def create_default_cover(self):
        """Generates a default placeholder image."""
        img = Image.new('RGB', (150, 150), color=THEME["accent"])
        d = ImageDraw.Draw(img)
        d.rectangle([5, 5, 145, 145], outline="white", width=2)
        d.text((40, 65), "NO COVER", fill="white", font_size=15)
        return img

    def get_embedded_art(self, folder_path):
        # 1. Try Local Files
        for f in ["cover.jpg", "cover.png", "album.jpg", "folder.jpg"]:
            full_path = os.path.join(folder_path, f)
            if os.path.exists(full_path):
                try: return Image.open(full_path).resize((150, 150), Image.LANCZOS)
                except: pass
        
        # 2. Try Embedded ID3 (Iterate ALL files)
        try:
            files = [f for f in os.listdir(folder_path) if f.lower().endswith(".mp3")]
            for f in files:
                try:
                    audio = MP3(os.path.join(folder_path, f), ID3=ID3)
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            return Image.open(BytesIO(tag.data)).resize((150, 150), Image.LANCZOS)
                except: continue
        except: pass

        # 3. RETURN DEFAULT
        return self.create_default_cover()

    def load_genre_view(self, genre_name):
        for w in self.grid_frame.winfo_children(): w.destroy()
        g_path = os.path.join(MUSIC_DIR, genre_name.lower())
        items = []
        if os.path.exists(g_path):
            for d in os.listdir(g_path):
                p = os.path.join(g_path, d)
                if os.path.isdir(p):
                    # Default Metadata
                    meta = {"title": d.upper(), "artist": "Unknown Artist"}
                    
                    json_path = os.path.join(p, "metadata.json")
                    
                    # A. Try reading JSON first
                    if os.path.exists(json_path):
                        try:
                            with open(json_path, "r") as f: meta.update(json.load(f))
                        except: pass
                    
                    # B. If JSON missing or failed, try fetching from first MP3
                    else:
                        try:
                            mp3s = [f for f in os.listdir(p) if f.lower().endswith(".mp3")]
                            if mp3s:
                                audio = ID3(os.path.join(p, mp3s[0]))
                                if "TIT2" in audio: meta["title"] = str(audio["TIT2"])
                                if "TPE1" in audio: meta["artist"] = str(audio["TPE1"])
                        except: pass

                    items.append({"meta": meta, "path": p})
        
        r, c = 0, 0
        for item in items:
            p = item["path"]
            frame = tk.Frame(self.grid_frame, bg=THEME["bg"], pady=10); frame.grid(row=r, column=c, padx=20)
            
            img_pil = self.get_embedded_art(p)
            img = ImageTk.PhotoImage(img_pil) if img_pil else None
            
            btn = tk.Button(frame, image=img, compound="top", width=150, height=150, bg=THEME["btn"], command=lambda path=p: self.select_and_play_folder(path))
            if img: btn.image = img

            btn.bind("<Button-3>", lambda e, path=p: self.edit_album_popup(path, genre_name))
            btn.bind("<Control-Button-1>", lambda e, path=p: self.edit_album_popup(path, genre_name))
            btn.pack()

            tk.Label(frame, text=item["meta"]["title"], font=("Segoe UI", 9, "bold"), bg=THEME["bg"], fg=THEME["text"], wraplength=150).pack()
            tk.Label(frame, text=item["meta"]["artist"], font=("Segoe UI", 8), bg=THEME["bg"], fg="gray", wraplength=150).pack()
            c += 1
            if c >= 4: c=0; r+=1

    def edit_album_popup(self, path, genre_name):
        win = tk.Toplevel(self); win.title("Edit Album"); win.geometry("300x250")
        meta = {"title": os.path.basename(path), "artist": "Unknown Artist"}
        if os.path.exists(os.path.join(path, "metadata.json")):
            with open(os.path.join(path, "metadata.json"), "r") as f: meta.update(json.load(f))
        tk.Label(win, text="Album Title:").pack(pady=(10,0)); t_e = tk.Entry(win, width=30); t_e.pack(); t_e.insert(0, meta['title'])
        tk.Label(win, text="Artist Name:").pack(pady=(10,0)); a_e = tk.Entry(win, width=30); a_e.pack(); a_e.insert(0, meta['artist'])
        def save():
            with open(os.path.join(path, "metadata.json"), "w") as f: json.dump({"title": t_e.get(), "artist": a_e.get()}, f)
            win.destroy(); self.load_genre_view(genre_name)
        def change_art():
            f = filedialog.askopenfilename(filetypes=[("Image", "*.jpg *.png")])
            if f: shutil.copy(f, os.path.join(path, "cover.jpg")); win.destroy(); self.load_genre_view(genre_name)
        def delete():
            if messagebox.askyesno("Delete", "Delete entire album?"): shutil.rmtree(path); win.destroy(); self.load_genre_view(genre_name)
        btn_f = tk.Frame(win); btn_f.pack(pady=20)
        tk.Button(btn_f, text="Save", command=save, bg=THEME["accent"], fg="white").pack(side="left", padx=5)
        tk.Button(btn_f, text="Art...", command=change_art).pack(side="left", padx=5)
        tk.Button(btn_f, text="Delete", command=delete, bg="#ff4444", fg="white").pack(side="left", padx=5)

    def select_and_play_folder(self, path):
        self.current_playback_path = path
        meta = {"title": os.path.basename(path), "artist": "Unknown Artist"}
        
        # Try JSON
        if os.path.exists(os.path.join(path, "metadata.json")):
            try:
                with open(os.path.join(path, "metadata.json"), "r") as f: meta.update(json.load(f))
            except: pass
        # Fallback to ID3 for Display
        else:
            try:
                mp3s = [f for f in os.listdir(path) if f.lower().endswith(".mp3")]
                if mp3s:
                    audio = ID3(os.path.join(path, mp3s[0]))
                    if "TIT2" in audio: meta["title"] = str(audio["TIT2"])
                    if "TPE1" in audio: meta["artist"] = str(audio["TPE1"])
            except: pass
            
        self.album_info_label.config(text=f"{meta['title']}\n{meta['artist']}")
        self.current_songs_list = sorted([s for s in os.listdir(path) if s.lower().endswith((".mp3", ".m4a"))])
        self.song_box.delete(0, tk.END)
        for s in self.current_songs_list: self.song_box.insert(tk.END, os.path.splitext(s)[0])
        if self.current_songs_list: self.play_song(0)

    # ==========================
    # UI: JOURNAL
    # ==========================
    def init_journal_tab(self):
        self.j_sidebar = tk.Frame(self.journal_tab, width=320, bg=THEME["bg"]); self.j_sidebar.pack(side="left", fill="y", padx=5); self.j_sidebar.pack_propagate(False)
        j_btn_f = tk.Frame(self.j_sidebar, bg=THEME["bg"]); j_btn_f.pack(fill="x", pady=5)
        tk.Button(j_btn_f, text="+ New", bg=THEME["accent"], fg="white", command=self.new_journal).pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(j_btn_f, text="- Delete", bg="#ff4444", fg="white", command=self.delete_journal).pack(side="left", expand=True, fill="x", padx=2)
        self.j_list = tk.Listbox(self.j_sidebar, font=("Arial", 12, "bold"), bg=THEME["bg"], fg=THEME["text"]); self.j_list.pack(fill="both", expand=True); self.j_list.bind("<<ListboxSelect>>", self.load_journal_entry)
        right = tk.Frame(self.journal_tab, bg=THEME["paper"]); right.pack(side="right", fill="both", expand=True)
        self.j_status_label = tk.Label(right, text="Saved", font=("Arial", 8), bg=THEME["paper"], fg="gray"); self.j_status_label.pack(side="top", anchor="e", padx=20)
        self.j_title_var = tk.StringVar()
        tk.Label(right, text="ENTRY TITLE:", font=("Georgia", 10, "bold"), bg=THEME["paper"], fg=THEME["text"]).pack(pady=(5,0))
        self.j_title_ent = tk.Entry(right, textvariable=self.j_title_var, font=self.journal_title_font, bg=THEME["paper"], fg=THEME["text"], insertbackground=THEME["text"], bd=0, highlightthickness=0, justify="center"); self.j_title_ent.pack(fill="x", padx=100); self.j_title_ent.bind("<KeyRelease>", self.trigger_autosave)
        tk.Frame(right, height=2, bg=THEME["lines"]).pack(fill="x", padx=100, pady=(0, 20))
        paper_container = tk.Frame(right, bg=THEME["paper"]); paper_container.pack(fill="both", expand=True, padx=60)
        self.j_text = tk.Text(paper_container, font=self.journal_font, wrap="word", bg=THEME["paper"], fg=THEME["text"], insertbackground=THEME["text"], borderwidth=0, highlightthickness=0, spacing1=15); self.j_text.pack(fill="both", expand=True); self.j_text.bind("<KeyRelease>", self.trigger_autosave)
        tk.Button(right, text="Force Save", bg=THEME["accent"], fg="white", width=25, command=self.save_journal).pack(pady=20)

    def trigger_autosave(self, event=None):
        self.j_status_label.config(text="Typing...", fg="orange")
        if self.autosave_timer: self.after_cancel(self.autosave_timer)
        self.autosave_timer = self.after(2000, self.perform_autosave)

    def perform_autosave(self):
        self.save_journal(silent=True)
        self.j_status_label.config(text="Auto-Saved", fg="green")

    def save_journal(self, silent=False):
        title = self.j_title_var.get().strip() or "Untitled"
        content = self.j_text.get("1.0", tk.END).strip()
        if not content: return
        if self.loaded_journal_file:
            try: original_date = self.loaded_journal_file.split("_")[0]
            except: original_date = datetime.now().strftime("%Y-%m-%d")
        else: original_date = datetime.now().strftime("%Y-%m-%d")
        safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '-', '.')]).strip()
        new_filename = f"{original_date}_{safe_title}.txt"
        if self.loaded_journal_file and self.loaded_journal_file != new_filename:
            old_path = os.path.join(JOURNAL_DIR, self.loaded_journal_file); new_path = os.path.join(JOURNAL_DIR, new_filename)
            if os.path.exists(old_path): os.rename(old_path, new_path)
            self.loaded_journal_file = new_filename
        elif not self.loaded_journal_file: self.loaded_journal_file = new_filename
        with open(os.path.join(JOURNAL_DIR, self.loaded_journal_file), "w", encoding="utf-8") as f: f.write(content)
        self.refresh_journals()
        if not silent: messagebox.showinfo("Saved", f"Entry saved.")

    def load_journal_entry(self, event=None):
        sel = self.j_list.curselection()
        if not sel: return
        display_name = self.j_list.get(sel[0])
        target_file = None
        for f in os.listdir(JOURNAL_DIR):
            if f.endswith(".txt"):
                parts = f.replace(".txt", "").split("_", 1)
                d_part = parts[0]; t_part = parts[1] if len(parts)>1 else "Untitled"
                if f"{d_part} ({t_part})" == display_name: target_file = f; break
        if target_file:
            self.loaded_journal_file = target_file
            parts = target_file.replace(".txt", "").split("_", 1)
            self.j_title_var.set(parts[1] if len(parts) > 1 else "")
            with open(os.path.join(JOURNAL_DIR, target_file), "r", encoding="utf-8") as f:
                self.j_text.delete("1.0", tk.END); self.j_text.insert(tk.END, f.read())
            self.j_status_label.config(text="Loaded", fg="gray")

    def refresh_journals(self):
        if not hasattr(self, 'j_list'): return
        self.j_list.delete(0, tk.END)
        if os.path.exists(JOURNAL_DIR):
            for f in sorted(os.listdir(JOURNAL_DIR), reverse=True):
                if f.endswith(".txt"):
                    parts = f.replace(".txt", "").split("_", 1)
                    date_part = parts[0]; title_part = parts[1] if len(parts) > 1 else "Untitled"
                    self.j_list.insert(tk.END, f"{date_part} ({title_part})")

    def new_journal(self):
        self.j_title_var.set(""); self.j_text.delete("1.0", tk.END); self.j_list.selection_clear(0, tk.END)
        self.loaded_journal_file = None; self.j_status_label.config(text="New Entry", fg="gray")

    def delete_journal(self):
        if not self.loaded_journal_file: return
        if messagebox.askyesno("Delete", "Delete entry?"):
            os.remove(os.path.join(JOURNAL_DIR, self.loaded_journal_file))
            self.new_journal(); self.refresh_journals()

    def toggle_shuffle(self):
        self.shuffle_on = not self.shuffle_on
        self.shuffle_btn.config(text="🔀 ON" if self.shuffle_on else "🔀 OFF", fg=THEME["vibrant_green"] if self.shuffle_on else THEME["text"])

    def init_favorites_tab(self):
        container = tk.Frame(self.favorites_tab, bg=THEME["bg"]); container.pack(fill="both", expand=True, padx=50, pady=20)
        tk.Label(container, text="MY FAVORITES", font=("Georgia", 24, "bold"), bg=THEME["bg"], fg=THEME["accent"]).pack(pady=(0,20))
        grid_f = tk.Frame(container, bg=THEME["bg"]); grid_f.pack(fill="both", expand=True)
        self.fav_vars = {}
        for i, cat in enumerate(["Books", "Songs", "Artists", "Movies"]):
            f = tk.LabelFrame(grid_f, text=f" {cat} ", bg=THEME["bg"], font=("Arial", 14, "bold"), fg=THEME["accent"])
            f.grid(row=i//2, column=i%2, sticky="nsew", padx=20, pady=20)
            grid_f.grid_columnconfigure(i%2, weight=1); grid_f.grid_rowconfigure(i//2, weight=1)
            lf = tk.Frame(f, bg=THEME["bg"]); lf.pack(fill="both", expand=True, padx=10, pady=10)
            b1 = tk.Listbox(lf, font=("Arial", 11), bg=THEME["bg"], fg=THEME["text"], bd=1, relief="solid"); b1.pack(side="left", fill="both", expand=True, padx=5)
            b2 = tk.Listbox(lf, font=("Arial", 11), bg=THEME["bg"], fg=THEME["text"], bd=1, relief="solid"); b2.pack(side="left", fill="both", expand=True, padx=5)
            b1.bind("<Double-1>", lambda e, c=cat: self.entry_fav_popup(c)); b2.bind("<Double-1>", lambda e, c=cat: self.entry_fav_popup(c))
            tk.Button(f, text="Clear Slot", bg=THEME["btn"], fg=THEME["text"], command=lambda c=cat: self.remove_favorite(c)).pack(pady=10)
            self.fav_vars[cat] = {"box1": b1, "box2": b2}
        self.update_fav_display()

    def entry_fav_popup(self, cat):
        s = self.fav_vars[cat]["box1"].curselection() or self.fav_vars[cat]["box2"].curselection()
        if not s: return
        line = (self.fav_vars[cat]["box1"] if self.fav_vars[cat]["box1"].curselection() else self.fav_vars[cat]["box2"]).get(s[0])
        rn = int(line.split(".")[0]); nv = simpledialog.askstring("Favorite", f"Rank {rn} {cat}:")
        if nv is not None:
            self.favorites[cat] = [i for i in self.favorites[cat] if not i.startswith(f"{rn:02}.")]
            if nv.strip(): self.favorites[cat].append(f"{rn:02}. {nv.strip()}")
            self.favorites[cat].sort(); self.update_fav_display()

    def remove_favorite(self, cat):
        s = self.fav_vars[cat]["box1"].curselection() or self.fav_vars[cat]["box2"].curselection()
        if s:
            rn = (self.fav_vars[cat]["box1"] if self.fav_vars[cat]["box1"].curselection() else self.fav_vars[cat]["box2"]).get(s[0]).split(".")[0]
            self.favorites[cat] = [i for i in self.favorites[cat] if not i.startswith(rn)]; self.update_fav_display()

    def update_fav_display(self):
        for c in self.fav_vars:
            self.fav_vars[c]["box1"].delete(0, tk.END); self.fav_vars[c]["box2"].delete(0, tk.END)
            data = {int(i.split(".")[0]): i.split(". ", 1)[1] for i in self.favorites[c] if "." in i}
            for r in range(1, 21):
                txt = f"{r:02}. {data.get(r, '______________________')}"
                if r <= 10: self.fav_vars[c]["box1"].insert(tk.END, txt)
                else: self.fav_vars[c]["box2"].insert(tk.END, txt)

    # ==========================
    # UI/LOGIC: RADIO
    # ==========================
    def init_radio_tab(self):
        container = tk.Frame(self.radio_tab, bg=THEME["bg"], pady=15); container.pack(fill="both", expand=True, padx=20)
        tk.Label(container, text="RADIO", font=("Georgia", 24, "bold"), bg=THEME["bg"], fg=THEME["accent"]).pack(pady=(0, 10))

        search_row = tk.Frame(container, bg=THEME["bg"]); search_row.pack(fill="x", pady=(0, 10))
        self.radio_search_var = tk.StringVar()
        search_entry = tk.Entry(search_row, textvariable=self.radio_search_var, font=("Segoe UI", 11), bg=THEME["entry_bg"])
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        search_entry.bind("<Return>", lambda e: self.search_radio())
        tk.Button(search_row, text="Search", bg=THEME["accent"], fg="white", command=self.search_radio).pack(side="left")

        panes = tk.Frame(container, bg=THEME["bg"]); panes.pack(fill="both", expand=True)

        left = tk.LabelFrame(panes, text=" Search Results ", bg=THEME["bg"], fg=THEME["text"], font=("Arial", 11, "bold"))
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.radio_results_box = tk.Listbox(left, font=("Segoe UI", 10), bg=THEME["bg"], fg=THEME["text"], bd=1, relief="solid")
        self.radio_results_box.pack(fill="both", expand=True, padx=5, pady=5)
        tk.Button(left, text="+ Add to My Stations", bg=THEME["accent"], fg="white", command=self.add_radio_station).pack(pady=5)

        right = tk.LabelFrame(panes, text=" My Stations ", bg=THEME["bg"], fg=THEME["text"], font=("Arial", 11, "bold"))
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))
        self.radio_my_box = tk.Listbox(right, font=("Segoe UI", 10, "bold"), bg=THEME["bg"], fg=THEME["text"], bd=1, relief="solid")
        self.radio_my_box.pack(fill="both", expand=True, padx=5, pady=5)
        self.radio_my_box.bind("<Double-1>", lambda e: self.play_selected_radio())
        my_btn_row = tk.Frame(right, bg=THEME["bg"]); my_btn_row.pack(pady=5)
        tk.Button(my_btn_row, text="▶ Play / ⏹ Stop", bg=THEME["accent"], fg="white", command=self.play_selected_radio).pack(side="left", padx=5)
        tk.Button(my_btn_row, text="Remove", bg=THEME["btn"], fg=THEME["text"], command=self.remove_radio_station).pack(side="left", padx=5)

        self.radio_status = tk.Label(container, text="Nothing playing", font=("Segoe UI", 10), bg=THEME["bg"], fg="gray")
        self.radio_status.pack(pady=(10, 0))

        self.refresh_my_stations()

    def search_radio(self):
        query = self.radio_search_var.get().strip()
        if not query: return
        self.radio_status.config(text=f"Searching for '{query}'...", fg="blue")
        def run():
            try:
                resp = requests.get(RADIO_SEARCH_API, params={
                    "name": query, "limit": 25, "hidebroken": "true",
                    "order": "clickcount", "reverse": "true",
                }, timeout=10, headers={"User-Agent": "MyFavoriteThingsApp/1.0"})
                results = resp.json()
                self.after(0, lambda: self.fill_radio_results(results))
            except Exception as e:
                self.after(0, lambda: self.radio_status.config(text=f"Search failed: {e}", fg="red"))
        threading.Thread(target=run, daemon=True).start()

    def fill_radio_results(self, results):
        self.radio_search_results = results
        self.radio_results_box.delete(0, tk.END)
        for r in results:
            label = f"{r.get('name', 'Unknown')}  [{r.get('countrycode', '')} {r.get('codec', '')} {r.get('bitrate', '')}kbps]"
            self.radio_results_box.insert(tk.END, label)
        self.radio_status.config(text=f"Found {len(results)} station(s)" if results else "No stations found", fg="gray")

    def add_radio_station(self):
        sel = self.radio_results_box.curselection()
        if not sel: return
        r = self.radio_search_results[sel[0]]
        name, url = r.get("name", "Unknown"), r.get("url_resolved") or r.get("url")
        if not url: return
        if any(s["url"] == url for s in self.my_radio_stations):
            return
        self.my_radio_stations.append({"name": name, "url": url})
        self.save_all_data()
        self.refresh_my_stations()

    def remove_radio_station(self):
        sel = self.radio_my_box.curselection()
        if not sel: return
        station = self.my_radio_stations[sel[0]]
        if self.radio_playing_name == station["name"]:
            self.stop_radio()
        del self.my_radio_stations[sel[0]]
        self.save_all_data()
        self.refresh_my_stations()

    def refresh_my_stations(self):
        self.radio_my_box.delete(0, tk.END)
        for s in self.my_radio_stations:
            marker = "▶ " if self.radio_playing_name == s["name"] else "   "
            self.radio_my_box.insert(tk.END, f"{marker}{s['name']}")

    def play_selected_radio(self):
        sel = self.radio_my_box.curselection()
        if not sel: return
        station = self.my_radio_stations[sel[0]]
        if self.radio_playing_name == station["name"]:
            self.stop_radio()
        else:
            self.start_radio(station["name"], station["url"])

    def start_radio(self, name, url):
        self.stop_radio()
        try:
            ffplay = os.path.join(BASE_DIR, "ffplay.exe")
            self.radio_proc = subprocess.Popen([ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", url],
                                                creationflags=subprocess.CREATE_NO_WINDOW)
            self.radio_playing_name = name
            self.radio_status.config(text=f"Playing: {name}", fg=THEME["accent"])
            self.refresh_my_stations()
        except Exception as e:
            messagebox.showerror("Radio", f"Couldn't start {name}: {e}")

    def stop_radio(self):
        if self.radio_proc:
            try: self.radio_proc.terminate()
            except Exception: pass
            self.radio_proc = None
        self.radio_playing_name = None
        self.radio_status.config(text="Nothing playing", fg="gray")
        self.refresh_my_stations()

    def stop_all_radio(self):
        self.stop_radio()

    # ==========================
    # UI/LOGIC: THEME (fully user-authored - colors + header decoration gifs)
    # ==========================
    def init_theme_tab(self):
        container = tk.Frame(self.theme_tab, bg=THEME["bg"], pady=20); container.pack(fill="both", expand=True, padx=40)
        tk.Label(container, text="THEME", font=("Georgia", 24, "bold"), bg=THEME["bg"], fg=THEME["accent"]).pack(pady=(0, 20))

        row = tk.Frame(container, bg=THEME["bg"]); row.pack(pady=(0, 20))
        tk.Label(row, text="Active theme:", font=("Segoe UI", 11, "bold"), bg=THEME["bg"], fg=THEME["text"]).pack(side="left", padx=(0, 10))
        self.theme_cb = ttk.Combobox(row, values=list(self.themes.keys()), state="readonly", width=25)
        self.theme_cb.set(self.active_theme_name)
        self.theme_cb.pack(side="left")
        self.theme_cb.bind("<<ComboboxSelected>>", lambda e: self.switch_theme(self.theme_cb.get()))
        tk.Button(row, text="New Theme", bg=THEME["btn"], fg=THEME["text"], command=self.new_theme).pack(side="left", padx=(15, 5))
        tk.Button(row, text="Rename", bg=THEME["btn"], fg=THEME["text"], command=self.rename_theme).pack(side="left", padx=5)
        tk.Button(row, text="Delete", bg=THEME["btn"], fg=THEME["text"], command=self.delete_theme).pack(side="left", padx=5)

        colors_frame = tk.LabelFrame(container, text=" Colors ", bg=THEME["bg"], fg=THEME["text"], font=("Arial", 11, "bold"))
        colors_frame.pack(fill="x", pady=10)
        self.color_swatches = {}
        self.pending_colors = dict(self.themes[self.active_theme_name]["colors"])
        for key in THEME_COLOR_KEYS:
            r = tk.Frame(colors_frame, bg=THEME["bg"]); r.pack(fill="x", padx=10, pady=5)
            tk.Label(r, text=key.replace("_", " ").title() + ":", width=12, anchor="w", bg=THEME["bg"], fg=THEME["text"]).pack(side="left")
            sw = tk.Button(r, width=6, bg=self.pending_colors.get(key, "#ffffff"), command=lambda k=key: self.pick_color(k))
            sw.pack(side="left")
            self.color_swatches[key] = sw
        tk.Button(container, text="Save Colors", bg=THEME["accent"], fg="white", command=self.save_theme_colors).pack(pady=10)

        tk.Label(container, text="Header decorations: click the faint '+' in the header's bottom-right corner to add a gif,\n"
                                  "or just drag a .gif file (or a gif from a browser tab) onto the header.\n"
                                  "Drag to move, scroll wheel to resize, right-click to remove.\n"
                                  "The main header gif (right-click to set) also resizes with the scroll wheel.\n"
                                  "Shift + scroll wheel on any gif slows down or speeds up all gif animation.\n"
                                  "The switch in the header's top-right corner flips the active theme into a dark mode\n"
                                  "derived from its own accent color (Autumn's dark mode stays orange, not plain black).",
                 font=("Segoe UI", 9), fg="gray", bg=THEME["bg"], justify="center").pack(pady=(20, 0))

    def pick_color(self, key):
        _, hex_color = colorchooser.askcolor(color=self.pending_colors.get(key, "#ffffff"), title=f"Pick {key} color")
        if hex_color:
            self.pending_colors[key] = hex_color
            self.color_swatches[key].config(bg=hex_color)

    def save_theme_colors(self):
        self.themes[self.active_theme_name]["colors"] = dict(self.pending_colors)
        self.save_all_data()
        self.apply_theme_and_rebuild()

    def new_theme(self):
        win = tk.Toplevel(self); win.title("New Theme"); win.geometry("320x420")
        tk.Label(win, text="Start from a color palette:", font=("Segoe UI", 10, "bold")).pack(pady=(10, 5))
        box = tk.Listbox(win, font=("Segoe UI", 10))
        for preset_name in THEME_PRESETS: box.insert(tk.END, preset_name)
        box.selection_set(0)
        box.pack(fill="both", expand=True, padx=10, pady=5)

        def confirm():
            sel = box.curselection()
            preset_name = box.get(sel[0]) if sel else "Blank (current colors)"
            win.destroy()
            name = simpledialog.askstring("New Theme", "Name this theme:")
            if not name or name in self.themes: return
            base_colors = dict(self.themes[self.active_theme_name]["colors"])
            base_colors.update(THEME_PRESETS.get(preset_name, {}))
            self.themes[name] = {"colors": base_colors, "decorations": []}
            self.active_theme_name = name
            self.save_all_data()
            self.theme_cb["values"] = list(self.themes.keys())
            self.theme_cb.set(name)
            self.apply_theme_and_rebuild()

        tk.Button(win, text="Next", bg=THEME["accent"], fg="white", command=confirm).pack(pady=10)

    def rename_theme(self):
        old = self.active_theme_name
        new = simpledialog.askstring("Rename Theme", "New name:", initialvalue=old)
        if not new or new == old or new in self.themes: return
        self.themes[new] = self.themes.pop(old)
        self.active_theme_name = new
        self.save_all_data()
        self.theme_cb["values"] = list(self.themes.keys())
        self.theme_cb.set(new)

    def delete_theme(self):
        if len(self.themes) <= 1:
            messagebox.showwarning("Theme", "You need at least one theme.")
            return
        if not messagebox.askyesno("Delete Theme", f"Delete theme '{self.active_theme_name}'?"): return
        del self.themes[self.active_theme_name]
        self.active_theme_name = next(iter(self.themes))
        self.save_all_data()
        self.apply_theme_and_rebuild()

    def switch_theme(self, name):
        if name not in self.themes or name == self.active_theme_name: return
        self.active_theme_name = name
        self.save_all_data()
        self.apply_theme_and_rebuild()

    def _apply_active_theme_colors(self):
        base_colors = self.themes[self.active_theme_name].get("colors", {})
        colors = make_dark_variant(base_colors) if self.dark_mode else base_colors
        THEME.update(derive_full_theme(colors))

    def apply_theme_and_rebuild(self):
        self._apply_active_theme_colors()
        self.configure(bg=THEME["bg"])
        self.header_frame.destroy()
        self.notebook.destroy()
        self.decoration_widgets = []
        self.setup_header()
        self.setup_notebook()
        self.init_music_tab()
        self.init_journal_tab()
        self.init_favorites_tab()
        self.init_radio_tab()
        self.init_theme_tab()
        self.refresh_genres()
        self.refresh_journals()
        if self.current_gif_path and os.path.exists(self.current_gif_path):
            self.load_gif_from_path(self.current_gif_path)
        self.render_decorations()

    # --- Header decorations (gifs the user adds/drags/resizes) ---
    def add_decoration(self):
        path = filedialog.askopenfilename(filetypes=[("GIF", "*.gif")])
        if path: self.add_decoration_from_path(path, 200, 20)

    def add_decoration_from_path(self, path, x=200, y=20):
        dec = {"path": path, "x": x, "y": y, "w": 80, "h": 80}
        self.themes[self.active_theme_name]["decorations"].append(dec)
        self.save_all_data()
        self.render_one_decoration(dec)

    def add_decoration_from_url(self, url, x=200, y=20):
        # Browser drags usually hand over a URL, not the actual file - fetch it ourselves
        # and save into the app's own gifs folder, same as any other gif the user adds.
        def run():
            try:
                resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "").lower()
                content = resp.content
                final_url = url
                if "gif" not in content_type and not url.lower().split("?")[0].endswith(".gif"):
                    # Probably got the page URL, not the raw image (common when dragging from
                    # an Internet Archive item page) - look inside the page for a .gif link.
                    if "html" in content_type:
                        match = re.search(r'(?:src|href)=["\']([^"\']+\.gif[^"\']*)["\']', resp.text, re.IGNORECASE)
                        if not match:
                            self.after(0, lambda: messagebox.showwarning(
                                "Add Gif", "Couldn't find a gif on that page. Try dragging the image itself\n(or opening the gif in its own tab first), not the page link."))
                            return
                        final_url = urljoin(url, match.group(1))
                        resp2 = requests.get(final_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                        resp2.raise_for_status()
                        content = resp2.content
                    else:
                        self.after(0, lambda: messagebox.showwarning("Add Gif", "That link doesn't look like a gif."))
                        return
                gifs_dir = os.path.join(DATA_DIR, "gifs")
                os.makedirs(gifs_dir, exist_ok=True)
                filename = os.path.basename(final_url.split("?")[0]) or "dropped.gif"
                if not filename.lower().endswith(".gif"): filename += ".gif"
                local_path = os.path.join(gifs_dir, filename)
                base, ext = os.path.splitext(local_path)
                counter = 1
                while os.path.exists(local_path):
                    local_path = f"{base}_{counter}{ext}"; counter += 1
                with open(local_path, "wb") as f: f.write(content)
                self.after(0, lambda: self.add_decoration_from_path(local_path, x, y))
            except Exception as e:
                self.after(0, lambda err=e: messagebox.showerror("Add Gif", f"Couldn't fetch that image: {err}"))
        threading.Thread(target=run, daemon=True).start()

    def on_gif_drop(self, event):
        try:
            items = self.tk.splitlist(event.data)
        except Exception:
            items = [event.data]
        header_x = self.header_frame.winfo_rootx()
        header_w = max(1, self.header_frame.winfo_width())
        x = max(0, min(event.x_root - header_x, header_w - 80))
        for item in items:
            item = item.strip()
            if item.lower().startswith(("http://", "https://")):
                self.add_decoration_from_url(item, x, 20)
            elif os.path.isfile(item) and item.lower().endswith(".gif"):
                self.add_decoration_from_path(item, x, 20)
            x = max(0, min(x + 20, header_w - 80))

    def render_decorations(self):
        for d in self.decoration_widgets:
            try: d["label"].destroy()
            except Exception: pass
        self.decoration_widgets = []
        for dec in self.themes[self.active_theme_name]["decorations"]:
            self.render_one_decoration(dec)

    def render_one_decoration(self, dec):
        try:
            img = Image.open(dec["path"])
            pil_frames, durations = [], []
            for frame in ImageSequence.Iterator(img):
                durations.append(frame.info.get("duration", 100) or 100)
                pil_frames.append(frame.convert("RGBA"))
        except Exception:
            return
        entry = {"pil_frames": pil_frames, "durations": durations, "frames": [], "idx": 0, "record": dec, "label": None}
        self.rescale_decoration_frames(entry)
        label = tk.Label(self.header_frame, bd=0, bg=THEME["bg"])
        label.place(x=dec["x"], y=dec["y"], width=dec["w"], height=dec["h"])
        label.config(image=entry["frames"][0])
        entry["label"] = label
        label.bind("<ButtonPress-1>", lambda e, en=entry: self._dec_drag_start(e, en))
        label.bind("<B1-Motion>", lambda e, en=entry: self._dec_drag_move(e, en))
        label.bind("<ButtonRelease-1>", lambda e, en=entry: self.save_all_data())
        label.bind("<MouseWheel>", lambda e, en=entry: self._dec_resize(e, en))
        label.bind("<Shift-MouseWheel>", self.adjust_gif_speed)
        label.bind("<Button-3>", lambda e, en=entry: self._dec_remove(en))
        self.decoration_widgets.append(entry)
        self.animate_one_decoration(entry)

    def rescale_decoration_frames(self, entry):
        w, h = entry["record"]["w"], entry["record"]["h"]
        entry["frames"] = [ImageTk.PhotoImage(f.resize((w, h), Image.LANCZOS)) for f in entry["pil_frames"]]

    def animate_one_decoration(self, entry):
        if entry not in self.decoration_widgets or not entry["frames"]: return
        try: entry["label"].config(image=entry["frames"][entry["idx"]])
        except Exception: return
        delay = max(20, int(entry["durations"][entry["idx"]] * self.gif_speed))
        entry["idx"] = (entry["idx"] + 1) % len(entry["frames"])
        self.after(delay, lambda: self.animate_one_decoration(entry))

    def adjust_gif_speed(self, event):
        delta = 0.25 if event.delta > 0 else -0.25
        self.gif_speed = max(0.25, min(8.0, self.gif_speed + delta))
        self.save_all_data()

    def _dec_drag_start(self, event, entry):
        entry["drag_offset"] = (event.x, event.y)

    def _dec_drag_move(self, event, entry):
        ox, oy = entry.get("drag_offset", (0, 0))
        new_x = entry["label"].winfo_x() + (event.x - ox)
        new_y = entry["label"].winfo_y() + (event.y - oy)
        max_x = max(0, self.header_frame.winfo_width() - entry["record"]["w"])
        max_y = max(0, self.header_frame.winfo_height() - entry["record"]["h"])
        new_x = max(0, min(new_x, max_x))
        new_y = max(0, min(new_y, max_y))
        entry["label"].place(x=new_x, y=new_y)
        entry["record"]["x"], entry["record"]["y"] = new_x, new_y

    def _dec_resize(self, event, entry):
        delta = 10 if event.delta > 0 else -10
        new_w = max(24, min(300, entry["record"]["w"] + delta))
        new_h = max(24, min(300, entry["record"]["h"] + delta))
        entry["record"]["w"], entry["record"]["h"] = new_w, new_h
        self.rescale_decoration_frames(entry)
        entry["idx"] = entry["idx"] % len(entry["frames"])
        entry["label"].place(width=new_w, height=new_h)
        entry["label"].config(image=entry["frames"][entry["idx"]])
        self.save_all_data()

    def _dec_remove(self, entry):
        if not messagebox.askyesno("Remove Decoration", "Remove this gif from the header?"): return
        try: self.themes[self.active_theme_name]["decorations"].remove(entry["record"])
        except ValueError: pass
        entry["label"].destroy()
        if entry in self.decoration_widgets: self.decoration_widgets.remove(entry)
        self.save_all_data()

    def set_volume(self, val): pygame.mixer.music.set_volume(float(val))
    def pause_music(self): pygame.mixer.music.pause(); self.is_paused = True
    def resume_music(self): pygame.mixer.music.unpause(); self.is_paused = False
    def play_song(self, idx=None):
        if idx is None and self.song_box.curselection(): idx = self.song_box.curselection()[0]
        if idx is not None:
            fn = self.current_songs_list[idx]; fp = os.path.join(self.current_playback_path, fn)
            pygame.mixer.music.load(fp)
            try: self.song_length = pygame.mixer.Sound(fp).get_length()
            except: self.song_length = 0
            pygame.mixer.music.play(); self.track_info_main.config(text=f"Playing: {os.path.splitext(fn)[0]}"); self.update_progress()
    def update_progress(self):
        if pygame.mixer.music.get_busy() and self.song_length:
            self.prog_bar['value'] = (pygame.mixer.music.get_pos() / 1000 / self.song_length) * 100
            self.after(1000, self.update_progress)
    def skip_song(self, prev=False):
        if not self.current_songs_list: return
        curr = self.song_box.curselection()[0] if self.song_box.curselection() else 0
        idx = random.randint(0, len(self.current_songs_list)-1) if self.shuffle_on else (curr - 1 if prev else curr + 1) % len(self.current_songs_list)
        self.song_box.selection_clear(0, tk.END); self.song_box.selection_set(idx); self.play_song(idx)
    def check_music_end(self):
        if not pygame.mixer.music.get_busy() and not self.is_paused and self.current_songs_list:
            if pygame.mixer.music.get_pos() == -1: self.skip_song()
        self.after(1000, self.check_music_end)
    def setup_header(self):
        self.header_frame = tk.Frame(self, bg=THEME["bg"], height=150); self.header_frame.pack(fill="x", side="top"); self.header_frame.pack_propagate(False)
        self.clock_label = tk.Label(self.header_frame, font=self.clock_font, bg=THEME["bg"], fg=THEME["accent"]); self.clock_label.place(relx=0.5, rely=0.5, anchor="center")
        self.cat_label = tk.Label(self.header_frame, bg=THEME["bg"]); self.cat_label.pack(side="left", padx=15); self.cat_label.bind("<Button-3>", lambda e: self.set_header_gif())
        self.cat_label.bind("<MouseWheel>", self.resize_header_gif)
        self.cat_label.bind("<Shift-MouseWheel>", self.adjust_gif_speed)
        tk.Button(self.header_frame, text="+", font=("Segoe UI", 9), fg="#bbbbbb", bg=THEME["bg"], bd=0,
                  activeforeground=THEME["accent"], command=self.add_decoration).place(relx=1.0, rely=1.0, anchor="se", x=-6, y=-4)
        self.build_light_switch()
    def setup_notebook(self):
        self.notebook = ttk.Notebook(self); self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        self.music_tab = tk.Frame(self.notebook, bg=THEME["bg"]); self.journal_tab = tk.Frame(self.notebook, bg=THEME["bg"]); self.favorites_tab = tk.Frame(self.notebook, bg=THEME["bg"]); self.radio_tab = tk.Frame(self.notebook, bg=THEME["bg"]); self.theme_tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(self.music_tab, text=" 🎵 MUSIC "); self.notebook.add(self.journal_tab, text=" 📝 JOURNAL "); self.notebook.add(self.favorites_tab, text=" ⭐ FAVORITES "); self.notebook.add(self.radio_tab, text=" 📻 RADIO "); self.notebook.add(self.theme_tab, text=" 🎨 THEME ")
    def load_gif_from_path(self, path):
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id); self.gif_after_id = None
        try:
            img = Image.open(path)
            self.gif_pil_frames, self.gif_durations = [], []
            for frame in ImageSequence.Iterator(img):
                self.gif_durations.append(frame.info.get("duration", 100) or 100)
                self.gif_pil_frames.append(frame.convert("RGBA"))
            self.gif_frames = [ImageTk.PhotoImage(f.resize((self.gif_size, self.gif_size))) for f in self.gif_pil_frames]
            self.gif_idx = 0; self.animate_gif()
        except: pass
    def animate_gif(self):
        if self.gif_frames:
            self.cat_label.config(image=self.gif_frames[self.gif_idx])
            delay = max(20, int(self.gif_durations[self.gif_idx] * self.gif_speed))
            self.gif_idx = (self.gif_idx + 1) % len(self.gif_frames)
            self.gif_after_id = self.after(delay, self.animate_gif)
    def set_header_gif(self):
        p = filedialog.askopenfilename(filetypes=[("GIF", "*.gif")]);
        if p: self.current_gif_path = p; self.load_gif_from_path(p)
    def resize_header_gif(self, event):
        if not self.gif_pil_frames: return
        delta = 10 if event.delta > 0 else -10
        self.gif_size = max(24, min(140, self.gif_size + delta))
        self.gif_frames = [ImageTk.PhotoImage(f.resize((self.gif_size, self.gif_size))) for f in self.gif_pil_frames]
        self.gif_idx = self.gif_idx % len(self.gif_frames)
        self.cat_label.config(image=self.gif_frames[self.gif_idx])
        self.save_all_data()

    # --- Light/Dark switch (a literal switch graphic in the header corner) ---
    def build_light_switch(self):
        self.switch_canvas = tk.Canvas(self.header_frame, width=34, height=54, bg=THEME["bg"], highlightthickness=0)
        self.switch_canvas.place(relx=1.0, rely=0.0, anchor="ne", x=-14, y=8)
        self.switch_canvas.bind("<Button-1>", lambda e: self.toggle_light_switch())
        self.draw_light_switch()

    def draw_light_switch(self):
        c = self.switch_canvas
        c.delete("all")
        is_dark = self.dark_mode
        plate = "#3a3a3a" if is_dark else "#dcdcdc"
        c.create_rectangle(2, 2, 32, 52, fill=plate, outline="#888888", width=2)
        knob_y = 28 if is_dark else 4
        c.create_rectangle(6, knob_y, 28, knob_y + 20, fill=("#5566aa" if is_dark else "#f5d76e"), outline="black")
        c.create_text(17, 40 if is_dark else 14, text=("🌙" if is_dark else "☀"), font=("Segoe UI", 9))

    def toggle_light_switch(self):
        self.dark_mode = not self.dark_mode
        self.save_all_data()
        self.apply_theme_and_rebuild()

if __name__ == "__main__":
    app = MyFavoriteThingsApp()
    app.mainloop()