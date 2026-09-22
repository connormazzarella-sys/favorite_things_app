const libState = { genreId: null, genreName: null, albumId: null, albumName: null, artist: "", songs: [], songIdx: -1, shuffle: false };

function cleanSongTitle(filename, artist) {
  let title = filename.replace(/\.(mp3|m4a)$/i, "");
  if (artist) {
    const escaped = artist.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    title = title.replace(new RegExp(`^${escaped}\\s*[-–—]\\s*`, "i"), "");
  }
  return title;
}

function showLibView(name) {
  ["genre", "album", "song"].forEach((v) => (el(`lib-${v}View`).hidden = v !== name));
  el("libBackBtn").hidden = name === "genre";
  el("libAddBtn").hidden = name === "song";
}

el("libBackBtn").addEventListener("click", () => {
  if (!el("lib-songView").hidden) { showLibView("album"); el("topTitle").textContent = libState.genreName; }
  else if (!el("lib-albumView").hidden) { showLibView("genre"); el("topTitle").textContent = "My Favorite Things"; }
});

el("libAddBtn").addEventListener("click", () => {
  if (!el("lib-albumView").hidden) {
    openAddAlbumModal();
  } else {
    const name = prompt("New genre name:");
    if (name && name.trim()) addGenre(name.trim());
  }
});

async function addGenre(name) {
  await findOrCreateChild(driveIds.music, name, true);
  loadGenres();
}

async function loadGenres() {
  const folders = await listChildren(driveIds.music, true);
  const list = el("genreList");
  list.innerHTML = "";
  if (!folders.length) {
    list.innerHTML = "<li>No genres yet - tap + to add one.</li>";
    return;
  }
  folders.forEach((f) => {
    const btn = document.createElement("button");
    btn.textContent = f.name.toUpperCase();
    btn.onclick = () => openGenre(f.id, f.name);
    list.appendChild(btn);
  });
}

async function openGenre(genreId, genreName) {
  libState.genreId = genreId;
  libState.genreName = genreName;
  el("topTitle").textContent = genreName.toUpperCase();
  const albumFolders = await listChildren(genreId, true);
  const grid = el("albumGrid");
  grid.innerHTML = "";
  for (const folder of albumFolders) {
    const card = document.createElement("div");
    card.className = "album-card";
    card.innerHTML = `<img alt="">
      <div class="title">${folder.name}</div>
      <div class="artist"></div>`;
    grid.appendChild(card);
    loadAlbumCardMeta(folder, card); // fire-and-forget, fills in async
  }
  showLibView("album");
}

async function loadAlbumCardMeta(folder, card) {
  const meta = await findChildByName(folder.id, "metadata.json");
  let title = folder.name, artist = "Unknown Artist";
  if (meta) {
    const data = await fetchFileJson(meta.id, {});
    title = data.title || title;
    artist = data.artist || artist;
  }
  card.querySelector(".title").textContent = title;
  card.querySelector(".artist").textContent = artist;
  card.onclick = () => openAlbum(folder.id, folder.name, title, artist);

  const cover = await findChildByName(folder.id, "cover.jpg") || await findChildByName(folder.id, "cover.png");
  if (cover) {
    const blob = await fetchFileBlob(cover.id);
    card.querySelector("img").src = URL.createObjectURL(blob);
  }
}

async function openAlbum(albumId, folderName, title, artist) {
  libState.albumId = albumId;
  libState.artist = artist;
  el("topTitle").textContent = title;
  const files = await listChildren(albumId, false);
  libState.songs = files.filter((f) => /\.(mp3|m4a)$/i.test(f.name));
  const list = el("songList");
  list.innerHTML = "";
  if (!libState.songs.length) {
    list.innerHTML = "<li>No songs in this album yet.</li>";
  }
  libState.songs.forEach((file, idx) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="track-name">${cleanSongTitle(file.name, artist)}</span><button data-dl>Download</button>`;
    li.querySelector(".track-name").onclick = () => playSong(idx);
    li.querySelector("[data-dl]").onclick = async () => {
      const blob = await fetchFileBlob(file.id);
      triggerBrowserDownload(blob, file.name);
    };
    list.appendChild(li);
  });
  showLibView("song");
}

async function playSong(idx) {
  if (idx < 0 || idx >= libState.songs.length) return;
  stopRadio();
  libState.songIdx = idx;
  const file = libState.songs[idx];
  el("nowPlayingTitle").textContent = "Loading...";
  el("player").hidden = false;
  try {
    const blob = await fetchFileBlob(file.id);
    const audio = el("audio");
    if (audio.dataset.blobUrl) URL.revokeObjectURL(audio.dataset.blobUrl);
    const url = URL.createObjectURL(blob);
    audio.dataset.blobUrl = url;
    audio.src = url;
    audio.play();
    el("nowPlayingTitle").textContent = cleanSongTitle(file.name, libState.artist);
    el("nowPlayingArtist").textContent = libState.artist || "";
    document.querySelectorAll(".song-row, #songList li").forEach((r, i) => r.classList.toggle("playing", i === idx));
  } catch (err) {
    console.error(err);
    el("nowPlayingTitle").textContent = "Couldn't play that track.";
  }
}

function nextSong() {
  if (!libState.songs.length) return;
  const idx = libState.shuffle ? Math.floor(Math.random() * libState.songs.length) : (libState.songIdx + 1) % libState.songs.length;
  playSong(idx);
}
function prevSong() {
  if (!libState.songs.length) return;
  playSong((libState.songIdx - 1 + libState.songs.length) % libState.songs.length);
}
el("nextBtn").addEventListener("click", nextSong);
el("prevBtn").addEventListener("click", prevSong);
el("audio").addEventListener("ended", nextSong);
el("shuffleBtn").addEventListener("click", () => {
  libState.shuffle = !libState.shuffle;
  el("shuffleBtn").innerHTML = `🔀 ${libState.shuffle ? "ON" : "OFF"}`;
});

// ---------- Add Album modal ----------
function openAddAlbumModal() {
  el("addAlbumHeading").textContent = `Add Album to ${libState.genreName}`;
  el("albumUploadForm").reset();
  el("albumUploadStatus").textContent = "";
  el("addAlbumModal").hidden = false;
}
el("cancelAlbumUpload").addEventListener("click", () => { el("addAlbumModal").hidden = true; });

el("albumUploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const files = el("albumSongFiles").files;
  if (!files.length) return;
  const albumName = el("albumNameInput").value.trim();
  const artist = el("albumArtistInput").value.trim() || "Unknown Artist";
  const coverFile = el("albumCoverFile").files[0];
  const statusEl = el("albumUploadStatus");
  try {
    statusEl.textContent = "Creating album...";
    const albumId = await findOrCreateChild(libState.genreId, albumName, true);
    await uploadNewFile(albumId, "metadata.json", new Blob([JSON.stringify({ title: albumName, artist })]), "application/json");
    if (coverFile) {
      statusEl.textContent = "Uploading cover...";
      await uploadNewFile(albumId, "cover.jpg", coverFile, coverFile.type || "image/jpeg");
    }
    for (let i = 0; i < files.length; i++) {
      statusEl.textContent = `Uploading ${i + 1}/${files.length}...`;
      await uploadNewFile(albumId, files[i].name, files[i], files[i].type || "audio/mpeg");
    }
    el("addAlbumModal").hidden = true;
    openGenre(libState.genreId, libState.genreName);
  } catch (err) {
    console.error(err);
    statusEl.textContent = "Something went wrong - see console.";
  }
});
