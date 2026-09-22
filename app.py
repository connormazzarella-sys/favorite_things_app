import os
import shutil
import json
import random
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime
import pygame
from PIL import Image, ImageTk, ImageSequence, ImageDraw
from io import BytesIO

# --- EXTERNAL LIBRARIES ---
import yt_dlp
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB

# Hide Pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

# --- CONFIGURATION ---
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

MUSIC_DIR = os.path.join(DATA_DIR, "music")
JOURNAL_DIR = os.path.join(DATA_DIR, "journals")
SETTINGS_FILE = os.path.join(DATA_DIR, "favorites.json")

for d in [MUSIC_DIR, JOURNAL_DIR]:
    os.makedirs(d, exist_ok=True)

class MyFavoriteThingsApp(tk.Tk):
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
        self.gif_idx = 0
        self.song_length = 0
        self.autosave_timer = None
        self.fetch_timer = None
        self.loaded_journal_file = None 

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
        self.init_downloader_tab()
        self.init_journal_tab()
        self.init_favorites_tab()
        
        # 3. LOAD DATA
        self.refresh_genres()
        self.refresh_journals()
        self.update_clock()
        self.check_music_end() 
        
        if self.current_gif_path and os.path.exists(self.current_gif_path):
            self.load_gif_from_path(self.current_gif_path)
            
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f: return json.load(f)
            except: pass
        return {"gif_path": "", "favorites": {"Books": [], "Songs": [], "Artists": [], "Movies": []}}

    def save_all_data(self):
        data = {"gif_path": self.current_gif_path, "favorites": self.favorites}
        with open(SETTINGS_FILE, "w") as f: json.dump(data, f, indent=4)

    def update_clock(self):
        self.clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
        self.after(1000, self.update_clock)

    def on_closing(self):
        self.save_all_data()
        pygame.mixer.quit()
        self.destroy()

    # ==========================
    # UI: MUSIC TAB
    # ==========================
    def init_music_tab(self):
        self.m_left = tk.Frame(self.music_tab, width=260, bg=THEME["bg"], borderwidth=1, relief="solid")
        self.m_left.pack(side="left", fill="y", padx=2, pady=2); self.m_left.pack_propagate(False)
        tk.Label(self.m_left, text="GENRES", font=self.header_font, bg=THEME["bg"]).pack(pady=(10,5))
        
        btn_g_f = tk.Frame(self.m_left, bg=THEME["bg"]); btn_g_f.pack(fill="x", pady=5)
        inner_btn_f = tk.Frame(btn_g_f, bg=THEME["bg"]); inner_btn_f.pack(expand=True)
        tk.Button(inner_btn_f, text="+", font=("Arial", 11, "bold"), width=4, command=self.add_genre).pack(side="left", padx=2)
        tk.Button(inner_btn_f, text="-", font=("Arial", 11, "bold"), width=4, command=self.remove_genre).pack(side="left", padx=2)
        tk.Button(inner_btn_f, text="Edit", font=("Arial", 11, "bold"), width=6, command=self.rename_genre).pack(side="left", padx=2)
        
        self.genre_canvas = tk.Canvas(self.m_left, bg=THEME["bg"], highlightthickness=0)
        self.genre_scroll = ttk.Scrollbar(self.m_left, orient="vertical", command=self.genre_canvas.yview)
        self.genre_frame = tk.Frame(self.genre_canvas, bg=THEME["bg"])
        self.genre_canvas.create_window((0, 0), window=self.genre_frame, anchor="nw", width=240)
        self.genre_frame.bind("<Configure>", lambda e: self.genre_canvas.configure(scrollregion=self.genre_canvas.bbox("all")))
        self.genre_canvas.pack(side="left", fill="both", expand=True, padx=5); self.genre_scroll.pack(side="right", fill="y")
        self.genre_canvas.configure(yscrollcommand=self.genre_scroll.set)

        self.m_right = tk.Frame(self.music_tab, width=320, bg=THEME["bg"], borderwidth=1, relief="solid")
        self.m_right.pack(side="right", fill="y", padx=2, pady=2); self.m_right.pack_propagate(False)
        self.album_info_label = tk.Label(self.m_right, text="SELECT AN ALBUM", font=("Segoe UI", 11, "bold"), bg=THEME["bg"], wraplength=280)
        self.album_info_label.pack(pady=15)
        tk.Frame(self.m_right, height=2, bg=THEME["accent"]).pack(fill="x", padx=20, pady=5)
        self.song_box = tk.Listbox(self.m_right, font=self.list_font, bg=THEME["bg"], borderwidth=0, activestyle='none', selectbackground=THEME["accent"], selectforeground="white")
        self.song_box.pack(fill="both", expand=True, padx=5, pady=5)
        self.song_box.bind("<Double-1>", lambda e: self.play_song())

        self.m_center = tk.Frame(self.music_tab, bg=THEME["bg"]); self.m_center.pack(side="left", fill="both", expand=True)
        self.control_bar = tk.Frame(self.m_center, height=180, bg=THEME["bg"], borderwidth=1, relief="solid")
        self.control_bar.pack(side="bottom", fill="x", padx=2, pady=2); self.control_bar.pack_propagate(False)
        self.track_info_main = tk.Label(self.control_bar, text="---", font=("Segoe UI", 11, "bold"), bg=THEME["bg"])
        self.track_info_main.pack(pady=(10, 0))
        self.prog_bar = ttk.Progressbar(self.control_bar, length=500, mode='determinate')
        self.prog_bar.pack(pady=10)
        
        self.center_btn_container = tk.Frame(self.control_bar, bg=THEME["bg"]); self.center_btn_container.pack(expand=True)
        tk.Button(self.center_btn_container, text="⏮", font=self.ctrl_font, width=4, command=lambda: self.skip_song(prev=True)).pack(side="left", padx=5)
        tk.Button(self.center_btn_container, text="▶", font=self.ctrl_font, width=4, command=self.resume_music).pack(side="left", padx=5)
        tk.Button(self.center_btn_container, text="⏸", font=self.ctrl_font, width=4, command=self.pause_music).pack(side="left", padx=5)
        tk.Button(self.center_btn_container, text="⏭", font=self.ctrl_font, width=4, command=self.skip_song).pack(side="left", padx=5)
        tk.Frame(self.center_btn_container, width=30, bg=THEME["bg"]).pack(side="left")
        self.shuffle_btn = tk.Button(self.center_btn_container, text="🔀 OFF", font=self.ctrl_font, width=8, command=self.toggle_shuffle)
        self.shuffle_btn.pack(side="left", padx=10)
        vol_f = tk.Frame(self.center_btn_container, bg=THEME["bg"]); vol_f.pack(side="left", padx=5)
        tk.Label(vol_f, text="VOL", font=("Segoe UI", 8, "bold"), bg=THEME["bg"]).pack()
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
            btn = tk.Button(self.genre_frame, text=g, font=("Segoe UI", 10, "bold"), bg=THEME["btn"], height=2, width=25, command=lambda genre=g: self.load_genre_view(genre))
            btn.pack(pady=2, padx=5, fill="x")
        if hasattr(self, 'dl_genre_cb'): self.dl_genre_cb['values'] = [g.lower() for g in self.all_genres]

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
            
            btn = tk.Button(frame, image=img, compound="top", width=150, height=150, command=lambda path=p: self.select_and_play_folder(path))
            if img: btn.image = img 
            
            btn.bind("<Button-3>", lambda e, path=p: self.edit_album_popup(path, genre_name))
            btn.bind("<Control-Button-1>", lambda e, path=p: self.edit_album_popup(path, genre_name))
            btn.pack()
            
            tk.Label(frame, text=item["meta"]["title"], font=("Segoe UI", 9, "bold"), bg=THEME["bg"], wraplength=150).pack()
            tk.Label(frame, text=item["meta"]["artist"], font=("Segoe UI", 8), bg=THEME["bg"], fg="#555", wraplength=150).pack()
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
    # UI: DOWNLOADER (BANDCAMP OPTIMIZED)
    # ==========================
    def init_downloader_tab(self):
        container = tk.Frame(self.dl_tab, bg="white", pady=20); container.pack(fill="both", expand=True)
        tk.Label(container, text="Paste Bandcamp/Music URL Here:", font=("Segoe UI", 12, "bold"), bg="white").pack(pady=(10,0))
        self.url_var = tk.StringVar(); self.url_var.trace_add("write", self.on_url_change)
        tk.Entry(container, textvariable=self.url_var, width=60, bg=THEME["entry_bg"]).pack(pady=5)
        self.dl_ents = {}
        
        # --- FIXED LABEL: "Title (Album)" -> "Title:" ---
        for l, k in [("Title:", "title"), ("Artist:", "artist")]:
            tk.Label(container, text=l, bg="white").pack(); ent = tk.Entry(container, width=50, bg=THEME["entry_bg"]); ent.pack(pady=2); self.dl_ents[k] = ent
            
        self.dl_genre_cb = ttk.Combobox(container); self.dl_genre_cb.pack(pady=5)
        tk.Button(container, text="Download (Max 50 Songs)", bg=THEME["accent"], fg="white", width=25, command=self.start_download).pack(pady=20)
        self.dl_status = tk.Label(container, text="Ready", bg="white", font=("Arial", 10, "bold")); self.dl_status.pack()
        self.dl_progress = ttk.Progressbar(container, length=400, mode='determinate'); self.dl_progress.pack(pady=10)

    def on_url_change(self, *args):
        if self.fetch_timer: self.after_cancel(self.fetch_timer)
        self.fetch_timer = self.after(1000, self.auto_fetch_info)

    def auto_fetch_info(self):
        u = self.url_var.get()
        if len(u) < 8: return
        self.dl_status.config(text="Fetching info...", fg="blue")
        def run():
            try:
                # --- FIXED: REMOVED 'extract_flat' to force deep scan of Bandcamp pages ---
                with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                    info = ydl.extract_info(u, download=False)
                    self.after(0, lambda: self.fill_dl_info(info))
            except: self.after(0, lambda: self.dl_status.config(text="Info fetch failed", fg="red"))
        threading.Thread(target=run, daemon=True).start()

    def fill_dl_info(self, info):
        # 1. FETCH TITLE
        title = info.get('title', '')
        self.dl_ents['title'].delete(0, tk.END); self.dl_ents['title'].insert(0, title)
        
        # 2. FETCH ARTIST (Bandcamp Optimized)
        artist = info.get('artist') or info.get('uploader') or info.get('channel') or ''
        
        # Fallback: Check inside entries (common for albums)
        if not artist and 'entries' in info and len(info['entries']) > 0:
            first = info['entries'][0]
            artist = first.get('artist') or first.get('uploader') or ''
            
        # Fallback: Check URL subdomain (e.g. soulmass.bandcamp.com -> soulmass)
        if not artist and 'webpage_url_domain' in info:
            # try to get subdomain if possible, otherwise use uploader_id
            artist = info.get('uploader_id') or ''

        self.dl_ents['artist'].delete(0, tk.END); self.dl_ents['artist'].insert(0, artist)
        self.dl_status.config(text="Info Loaded", fg="green")

    def start_download(self):
        u = self.url_var.get(); g = self.dl_genre_cb.get(); t = self.dl_ents['title'].get().strip()
        a = self.dl_ents['artist'].get().strip()
        if not u or not g or not t: messagebox.showwarning("Error", "Missing info."); return
        self.dl_status.config(text="Initializing...", fg="blue")
        self.dl_progress['value'] = 0
        threading.Thread(target=self.run_dl, args=(u, {"title": t, "artist": a}, g), daemon=True).start()

    def run_dl(self, u, d, g):
        # 1. Setup Directory
        safe_title = "".join([c for c in d['title'] if c.isalnum() or c in (' ', '.', '_')]).strip()
        path = os.path.join(MUSIC_DIR, g, safe_title)
        os.makedirs(path, exist_ok=True)
        
        # Save Metadata
        with open(os.path.join(path, "metadata.json"), "w") as f: json.dump(d, f)
        
        # 2. Progress Hook
        def hook(x):
            if x['status'] == 'downloading':
                # --- FIXED BATCH PROGRESS ---
                idx = x.get('info_dict', {}).get('playlist_index', 1) or 1
                total = x.get('info_dict', {}).get('n_entries', 1) or 1
                
                file_pct = 0
                if x.get('total_bytes'): file_pct = x['downloaded_bytes'] / x['total_bytes']
                elif x.get('total_bytes_estimate'): file_pct = x['downloaded_bytes'] / x['total_bytes_estimate']
                
                # Formula: ((Previous Songs) + (Current %)) / Total
                global_pct = ((idx - 1) + file_pct) / total * 100
                self.after(0, lambda: self.update_dl_ui(global_pct, f"DL: {idx}/{total} ({int(global_pct)}%)"))
                
            elif x['status'] == 'finished':
                self.after(0, lambda: self.dl_status.config(text="Processing audio conversion..."))

        # 3. Download Options
        opts = {
            'format': 'bestaudio/best', 
            'outtmpl': f'{path}/%(title)s.%(ext)s', 
            'progress_hooks': [hook], 
            'playlistend': 50,
            
            # --- BANDCAMP/YT-DLP POST PROCESSING ---
            'writethumbnail': True,
            'addmetadata': True,
            'postprocessors': [
                {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'},
                {'key': 'EmbedThumbnail'}, 
                {'key': 'FFmpegMetadata'}, 
            ],
            'noplaylist': False,
            'quiet': True,
            'no_warnings': True
        }

        # 4. Execute Download
        try:
            with yt_dlp.YoutubeDL(opts) as ydl: 
                ydl.download([u])
            
            # 5. --- FORCE ARTIST TAGGING ---
            self.after(0, lambda: self.dl_status.config(text="Tagging Files..."))
            
            user_artist = d.get('artist', 'Unknown Artist').strip()
            album_title = d.get('title', '').strip()

            for f in os.listdir(path):
                if f.lower().endswith(".mp3"):
                    full_p = os.path.join(path, f)
                    try:
                        audio = ID3(full_p)
                        
                        # Set Artist
                        audio.add(TPE1(encoding=3, text=user_artist))
                        
                        # Set Album (using the title from the text box)
                        if album_title:
                            audio.add(TALB(encoding=3, text=album_title))
                        
                        # If Title missing, use filename
                        if "TIT2" not in audio:
                            clean_title = os.path.splitext(f)[0]
                            audio.add(TIT2(encoding=3, text=clean_title))
                            
                        audio.save()
                    except Exception as tag_err:
                        print(f"Tag error on {f}: {tag_err}")

            self.after(0, lambda: self.dl_status.config(text="Complete!", fg="green"))
            self.after(0, lambda: self.dl_progress.configure(value=100))
            self.after(500, self.refresh_genres)
            
        except Exception as e: 
            self.after(0, lambda: self.dl_status.config(text=f"Error: {str(e)[:20]}...", fg="red"))

    def update_dl_ui(self, val, msg):
        self.dl_progress['value'] = val
        self.dl_status.config(text=msg)

    # ==========================
    # UI: JOURNAL
    # ==========================
    def init_journal_tab(self):
        self.j_sidebar = tk.Frame(self.journal_tab, width=320, bg=THEME["bg"]); self.j_sidebar.pack(side="left", fill="y", padx=5); self.j_sidebar.pack_propagate(False)
        j_btn_f = tk.Frame(self.j_sidebar, bg=THEME["bg"]); j_btn_f.pack(fill="x", pady=5)
        tk.Button(j_btn_f, text="+ New", bg=THEME["accent"], fg="white", command=self.new_journal).pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(j_btn_f, text="- Delete", bg="#ff4444", fg="white", command=self.delete_journal).pack(side="left", expand=True, fill="x", padx=2)
        self.j_list = tk.Listbox(self.j_sidebar, font=("Arial", 12, "bold"), bg="#f8f9fa"); self.j_list.pack(fill="both", expand=True); self.j_list.bind("<<ListboxSelect>>", self.load_journal_entry)
        right = tk.Frame(self.journal_tab, bg=THEME["paper"]); right.pack(side="right", fill="both", expand=True)
        self.j_status_label = tk.Label(right, text="Saved", font=("Arial", 8), bg=THEME["paper"], fg="gray"); self.j_status_label.pack(side="top", anchor="e", padx=20)
        self.j_title_var = tk.StringVar()
        tk.Label(right, text="ENTRY TITLE:", font=("Georgia", 10, "bold"), bg=THEME["paper"]).pack(pady=(5,0))
        self.j_title_ent = tk.Entry(right, textvariable=self.j_title_var, font=self.journal_title_font, bg=THEME["paper"], bd=0, highlightthickness=0, justify="center"); self.j_title_ent.pack(fill="x", padx=100); self.j_title_ent.bind("<KeyRelease>", self.trigger_autosave)
        tk.Frame(right, height=2, bg=THEME["lines"]).pack(fill="x", padx=100, pady=(0, 20))
        paper_container = tk.Frame(right, bg=THEME["paper"]); paper_container.pack(fill="both", expand=True, padx=60)
        self.j_text = tk.Text(paper_container, font=self.journal_font, wrap="word", bg=THEME["paper"], borderwidth=0, highlightthickness=0, spacing1=15); self.j_text.pack(fill="both", expand=True); self.j_text.bind("<KeyRelease>", self.trigger_autosave)
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
        self.shuffle_btn.config(text="🔀 ON" if self.shuffle_on else "🔀 OFF", fg=THEME["vibrant_green"] if self.shuffle_on else "black")

    def init_favorites_tab(self):
        container = tk.Frame(self.favorites_tab, bg="white"); container.pack(fill="both", expand=True, padx=50, pady=20)
        tk.Label(container, text="MY FAVORITES", font=("Georgia", 24, "bold"), bg="white", fg=THEME["accent"]).pack(pady=(0,20))
        grid_f = tk.Frame(container, bg="white"); grid_f.pack(fill="both", expand=True)
        self.fav_vars = {}
        for i, cat in enumerate(["Books", "Songs", "Artists", "Movies"]):
            f = tk.LabelFrame(grid_f, text=f" {cat} ", bg="white", font=("Arial", 14, "bold"), fg=THEME["accent"])
            f.grid(row=i//2, column=i%2, sticky="nsew", padx=20, pady=20)
            grid_f.grid_columnconfigure(i%2, weight=1); grid_f.grid_rowconfigure(i//2, weight=1)
            lf = tk.Frame(f, bg="white"); lf.pack(fill="both", expand=True, padx=10, pady=10)
            b1 = tk.Listbox(lf, font=("Arial", 11), bd=1, relief="solid"); b1.pack(side="left", fill="both", expand=True, padx=5)
            b2 = tk.Listbox(lf, font=("Arial", 11), bd=1, relief="solid"); b2.pack(side="left", fill="both", expand=True, padx=5)
            b1.bind("<Double-1>", lambda e, c=cat: self.entry_fav_popup(c)); b2.bind("<Double-1>", lambda e, c=cat: self.entry_fav_popup(c))
            tk.Button(f, text="Clear Slot", command=lambda c=cat: self.remove_favorite(c)).pack(pady=10)
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
        self.header_frame = tk.Frame(self, bg=THEME["bg"], height=70); self.header_frame.pack(fill="x", side="top")
        self.clock_label = tk.Label(self.header_frame, font=self.clock_font, bg=THEME["bg"], fg=THEME["accent"]); self.clock_label.place(relx=0.5, rely=0.5, anchor="center")
        self.cat_label = tk.Label(self.header_frame, bg=THEME["bg"]); self.cat_label.pack(side="left", padx=15); self.cat_label.bind("<Button-3>", lambda e: self.set_header_gif())
    def setup_notebook(self):
        self.notebook = ttk.Notebook(self); self.notebook.pack(fill="both", expand=True, padx=10, pady=5)
        self.music_tab = tk.Frame(self.notebook, bg=THEME["bg"]); self.dl_tab = tk.Frame(self.notebook, bg=THEME["bg"]); self.journal_tab = tk.Frame(self.notebook, bg=THEME["bg"]); self.favorites_tab = tk.Frame(self.notebook, bg=THEME["bg"])
        self.notebook.add(self.music_tab, text=" 🎵 MUSIC "); self.notebook.add(self.dl_tab, text=" ⬇️ DOWNLOADER "); self.notebook.add(self.journal_tab, text=" 📝 JOURNAL "); self.notebook.add(self.favorites_tab, text=" ⭐ FAVORITES ")
    def load_gif_from_path(self, path):
        try:
            img = Image.open(path); self.gif_frames = [ImageTk.PhotoImage(f.convert("RGBA").resize((60, 60))) for f in ImageSequence.Iterator(img)]; self.gif_idx = 0; self.animate_gif()
        except: pass
    def animate_gif(self):
        if self.gif_frames: self.cat_label.config(image=self.gif_frames[self.gif_idx]); self.gif_idx = (self.gif_idx + 1) % len(self.gif_frames); self.after(100, self.animate_gif)
    def set_header_gif(self):
        p = filedialog.askopenfilename(filetypes=[("GIF", "*.gif")]); 
        if p: self.current_gif_path = p; self.load_gif_from_path(p)

if __name__ == "__main__":
    app = MyFavoriteThingsApp()
    app.mainloop()