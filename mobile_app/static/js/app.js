const state = {
  genre: null,
  album: null,
  artist: "",
  songs: [],
  songIdx: -1,
  shuffle: false,
};

const el = (id) => document.getElementById(id);
const views = { genre: el("genreView"), album: el("albumView"), song: el("songView") };

function cleanSongTitle(filename, artist) {
  let title = filename.replace(/\.(mp3|m4a)$/i, "");
  if (artist) {
    const escaped = artist.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    title = title.replace(new RegExp(`^${escaped}\\s*[-–—]\\s*`, "i"), "");
  }
  return title;
}

// ---------- Bottom tab navigation ----------
const tabSections = { library: el("librarySection"), radio: el("radioSection") };

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".nav-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    Object.entries(tabSections).forEach(([k, section]) => (section.hidden = k !== btn.dataset.tab));
    el("backBtn").hidden = true;
    if (btn.dataset.tab === "library") {
      el("topTitle").textContent = "My Favorite Things";
      showView("genre");
      loadGenres();
    } else {
      el("topTitle").textContent = "Radio";
      el("addBtn").hidden = true;
      loadSavedStations();
    }
  };
});

// ---------- Library ----------
function showView(name) {
  Object.entries(views).forEach(([k, v]) => (v.hidden = k !== name));
  el("backBtn").hidden = name === "genre";
  el("addBtn").hidden = name === "song"; // add-genre on genre view, add-album on album view
}

el("backBtn").onclick = () => {
  if (!views.song.hidden) { showView("album"); el("topTitle").textContent = state.genre; }
  else if (!views.album.hidden) { showView("genre"); el("topTitle").textContent = "My Favorite Things"; }
};

el("addBtn").onclick = () => {
  if (!views.album.hidden) {
    openAddAlbumModal();
  } else {
    const name = prompt("New genre name:");
    if (name && name.trim()) {
      fetch("/api/genres", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim() }),
      }).then(loadGenres);
    }
  }
};

async function loadGenres() {
  const genres = await fetch("/api/genres").then((r) => r.json());
  const list = el("genreList");
  list.innerHTML = "";
  genres.forEach((g) => {
    const btn = document.createElement("button");
    btn.textContent = g;
    btn.onclick = () => openGenre(g);
    list.appendChild(btn);
  });
}

async function openGenre(genre) {
  state.genre = genre;
  el("topTitle").textContent = genre;
  const albums = await fetch(`/api/genres/${encodeURIComponent(genre)}/albums`).then((r) => r.json());
  const grid = el("albumGrid");
  grid.innerHTML = "";
  albums.forEach((a) => {
    const card = document.createElement("div");
    card.className = "album-card";
    card.innerHTML = `
      <img src="/api/cover/${encodeURIComponent(genre)}/${encodeURIComponent(a.folder)}" alt="">
      <div class="title">${a.title}</div>
      <div class="artist">${a.artist}</div>`;
    card.onclick = () => openAlbum(genre, a.folder, a.title, a.artist);
    grid.appendChild(card);
  });
  showView("album");
}

async function openAlbum(genre, album, title, artist) {
  state.album = album;
  state.artist = artist;
  state.songs = await fetch(`/api/albums/${encodeURIComponent(genre)}/${encodeURIComponent(album)}/songs`).then((r) => r.json());
  el("topTitle").textContent = title;
  const list = el("songList");
  list.innerHTML = "";
  state.songs.forEach((s, idx) => {
    const row = document.createElement("div");
    row.className = "song-row";
    row.textContent = cleanSongTitle(s, artist);
    row.onclick = () => playSong(idx);
    list.appendChild(row);
  });
  showView("song");
}

function playSong(idx) {
  if (idx < 0 || idx >= state.songs.length) return;
  stopRadio();
  state.songIdx = idx;
  const filename = state.songs[idx];
  const audio = el("audio");
  audio.src = `/api/stream/${encodeURIComponent(state.genre)}/${encodeURIComponent(state.album)}/${encodeURIComponent(filename)}`;
  audio.play();
  el("player").hidden = false;
  el("nowPlayingTitle").textContent = cleanSongTitle(filename, state.artist);
  el("nowPlayingArtist").textContent = state.artist || "";
  document.querySelectorAll(".song-row").forEach((r, i) => r.classList.toggle("playing", i === idx));
}

function nextSong() {
  if (!state.songs.length) return;
  const idx = state.shuffle ? Math.floor(Math.random() * state.songs.length) : (state.songIdx + 1) % state.songs.length;
  playSong(idx);
}

function prevSong() {
  if (!state.songs.length) return;
  playSong((state.songIdx - 1 + state.songs.length) % state.songs.length);
}

el("nextBtn").onclick = () => nextSong();
el("prevBtn").onclick = () => prevSong();
el("audio").addEventListener("ended", () => nextSong());
el("shuffleBtn").onclick = () => {
  state.shuffle = !state.shuffle;
  el("shuffleBtn").innerHTML = `🔀 ${state.shuffle ? "ON" : "OFF"}`;
};

// ---------- Radio ----------
let radioResultsData = [];

function stopRadio() {
  const ra = el("radioAudio");
  ra.pause();
  ra.hidden = true;
}

async function searchRadio() {
  const q = el("radioSearchInput").value.trim();
  if (!q) return;
  el("radioStatus").textContent = `Searching for "${q}"...`;
  const res = await fetch(`/api/radio/search?q=${encodeURIComponent(q)}`).then((r) => r.json());
  radioResultsData = Array.isArray(res) ? res : [];
  const box = el("radioResults");
  box.innerHTML = "";
  radioResultsData.forEach((s, idx) => {
    const row = document.createElement("div");
    row.className = "radio-row";
    row.innerHTML = `<span>${s.name} <small>[${s.country} ${s.codec} ${s.bitrate}kbps]</small></span>
      <button data-idx="${idx}">+ Add</button>`;
    row.querySelector("button").onclick = () => addStation(s.name, s.url);
    box.appendChild(row);
  });
  el("radioStatus").textContent = radioResultsData.length ? `Found ${radioResultsData.length} station(s)` : "No stations found";
}

async function addStation(name, url) {
  await fetch("/api/radio/stations", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, url }),
  });
  loadSavedStations();
}

async function loadSavedStations() {
  const stations = await fetch("/api/radio/stations").then((r) => r.json());
  const box = el("radioSaved");
  box.innerHTML = "";
  stations.forEach((s, idx) => {
    const row = document.createElement("div");
    row.className = "radio-row";
    row.innerHTML = `<span>${s.name}</span>
      <span>
        <button data-play>&#9654;</button>
        <button data-remove>&times;</button>
      </span>`;
    row.querySelector("[data-play]").onclick = () => playStation(s.name, s.url);
    row.querySelector("[data-remove]").onclick = async () => {
      await fetch(`/api/radio/stations/${idx}`, { method: "DELETE" });
      loadSavedStations();
    };
    box.appendChild(row);
  });
}

function playStation(name, url) {
  el("audio").pause();
  el("player").hidden = true;
  const ra = el("radioAudio");
  ra.src = url;
  ra.hidden = false;
  ra.play();
  el("radioStatus").textContent = `Playing: ${name}`;
}

el("radioSearchBtn").onclick = searchRadio;
el("radioSearchInput").addEventListener("keydown", (e) => { if (e.key === "Enter") searchRadio(); });

// ---------- Add Album modal (contextual to the currently open genre) ----------
function openAddAlbumModal() {
  el("addAlbumHeading").textContent = `Add Album to ${state.genre}`;
  el("uploadForm").reset();
  el("uploadStatus").textContent = "";
  el("addAlbumModal").hidden = false;
}

el("cancelUpload").onclick = () => { el("addAlbumModal").hidden = true; };

el("uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const files = el("uploadFiles").files;
  if (!files.length) return;
  const album = el("uploadAlbum").value.trim();
  const fd = new FormData();
  fd.append("genre", state.genre);
  fd.append("album", album);
  fd.append("artist", el("uploadArtist").value.trim());
  fd.append("title", album);
  for (const f of files) fd.append("files", f);

  el("uploadStatus").textContent = `Uploading ${files.length} file(s)...`;
  const res = await fetch("/api/upload", { method: "POST", body: fd });
  if (res.ok) {
    el("addAlbumModal").hidden = true;
    openGenre(state.genre); // refresh the album grid
  } else {
    el("uploadStatus").textContent = "Something went wrong - check album/files and try again.";
  }
});

showView("genre");
loadGenres();
