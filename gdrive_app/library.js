const libState = { genreId: null, genreName: null, albumId: null, albumName: null, artist: "", songs: [], songIdx: -1, shuffle: false };

function cleanSongTitle(filename, artist) {
  let title = filename.replace(/\.(mp3|m4a)$/i, "");
  title = title.replace(/^\d+\s*[-.]\s*/, ""); // strip a leading track-number prefix like "01 - "
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

async function renameGenre(folderId, currentName) {
  const newName = prompt("Rename genre:", currentName);
  if (!newName || !newName.trim() || newName.trim() === currentName) return;
  await renameFile(folderId, newName.trim());
  loadGenres();
}

async function deleteGenre(folderId, name) {
  if (!confirm(`Delete "${name}" and everything inside it?\n\nThis moves it to your Google Drive trash, so it's recoverable there for 30 days.`)) return;
  await deleteFile(folderId);
  loadGenres();
}

// Windows/macOS file managers hand a dropped folder over as a
// FileSystemDirectoryEntry, not a plain File - this walks it (and any
// dropped loose file) down to a flat list of actual File objects.
function entryToFile(entry) {
  return new Promise((resolve) => entry.file(resolve));
}
function readAllDirEntries(dirEntry) {
  return new Promise((resolve) => {
    const reader = dirEntry.createReader();
    let all = [];
    (function readBatch() {
      reader.readEntries((entries) => {
        if (!entries.length) return resolve(all);
        all = all.concat(entries);
        readBatch();
      });
    })();
  });
}
async function collectAllFiles(entry) {
  if (entry.isFile) return [await entryToFile(entry)];
  if (entry.isDirectory) {
    const children = await readAllDirEntries(entry);
    let files = [];
    for (const child of children) files = files.concat(await collectAllFiles(child));
    return files;
  }
  return [];
}
const isAudioFile = (file) => /\.(mp3|m4a)$/i.test(file.name);
const isCoverImageFile = (file) => /^cover\.(jpe?g|png|webp)$/i.test(file.name);

// getAsEntry() must be called synchronously inside the drop handler
// (before any await), so this pulls entries out first thing.
function entriesFromDrop(dataTransfer) {
  return [...dataTransfer.items]
    .map((item) => (item.webkitGetAsEntry ? item.webkitGetAsEntry() : null))
    .filter(Boolean);
}

// Reads embedded ID3/MP4 tags (title, artist, album, track #, cover art)
// straight out of an audio File in the browser - resolves null on anything
// unreadable/untagged rather than rejecting, since tags are best-effort.
function readAudioTags(file) {
  return new Promise((resolve) => {
    if (typeof jsmediatags === "undefined") return resolve(null);
    jsmediatags.read(file, {
      onSuccess: ({ tags }) => {
        let picture = null;
        if (tags.picture) {
          const bytes = new Uint8Array(tags.picture.data);
          const ext = (tags.picture.format || "image/jpeg").split("/")[1] || "jpg";
          picture = { blob: new Blob([bytes], { type: tags.picture.format }), ext };
        }
        resolve({
          title: tags.title || null,
          artist: tags.artist || null,
          album: tags.album || null,
          track: tags.track ? parseInt(tags.track, 10) : null,
          picture,
        });
      },
      onError: () => resolve(null),
    });
  });
}

function sanitizeForFilename(name) {
  return name.replace(/[\\/:*?"<>|]/g, "").trim();
}

// Uploads one song, preferring its own embedded title/track-number (renamed
// to "01 - Title.mp3" so Drive's name-sort keeps album order and the on
// screen title comes out clean) over its original OS filename.
async function uploadAudioFileWithTags(albumId, file, tagsOverride) {
  const tags = tagsOverride !== undefined ? tagsOverride : await readAudioTags(file);
  const ext = (file.name.match(/\.(\w+)$/) || [, "mp3"])[1];
  let uploadName = file.name;
  if (tags && tags.title) {
    const trackPrefix = tags.track ? String(tags.track).padStart(2, "0") + " - " : "";
    uploadName = `${trackPrefix}${sanitizeForFilename(tags.title)}.${ext}`;
  }
  await uploadNewFile(albumId, uploadName, file, file.type || "audio/mpeg");
  return tags;
}

// Creates a new album from a dropped folder's contents: album title/artist
// come from the first track's ID3 tags (falling back to the folder name /
// "Unknown Artist"), the cover comes from a "cover.*" file in the folder or
// else the first track's embedded art, and each song is uploaded via
// uploadAudioFileWithTags so titles/order come from tags too.
async function createAlbumFromFolderFiles(genreId, folderName, audioFiles, coverFile) {
  el("topTitle").textContent = `Reading tags for "${folderName}"...`;
  const firstTags = audioFiles.length ? await readAudioTags(audioFiles[0]) : null;
  const albumTitle = (firstTags && firstTags.album) || folderName;
  const albumArtist = (firstTags && firstTags.artist) || "Unknown Artist";

  const albumId = await findOrCreateChild(genreId, folderName, true);
  const existingMeta = await findChildByName(albumId, "metadata.json");
  const metaData = { title: albumTitle, artist: albumArtist };
  if (existingMeta) await saveJsonFile(existingMeta.id, metaData);
  else await uploadNewFile(albumId, "metadata.json", new Blob([JSON.stringify(metaData)]), "application/json");

  let coverBlob = coverFile;
  let coverExt = coverFile ? (coverFile.name.match(/\.(\w+)$/) || [, "jpg"])[1] : "jpg";
  if (!coverBlob && firstTags && firstTags.picture) {
    coverBlob = firstTags.picture.blob;
    coverExt = firstTags.picture.ext;
  }
  if (coverBlob && !(await findChildByName(albumId, `cover.${coverExt}`))) {
    await uploadNewFile(albumId, `cover.${coverExt}`, coverBlob, coverBlob.type || `image/${coverExt}`);
  }

  for (let i = 0; i < audioFiles.length; i++) {
    el("topTitle").textContent = `Uploading ${i + 1}/${audioFiles.length}...`;
    await uploadAudioFileWithTags(albumId, audioFiles[i], i === 0 ? firstTags : undefined);
  }
}

// Drops onto a genre tile: a dropped FOLDER becomes a new album automatically
// (named after the folder, songs uploaded straight in) - loose MP3/M4A files
// dropped directly (not inside a folder) open the Add Album modal instead,
// pre-filled, so the user just has to name the album and confirm.
function wireGenreDropTarget(row, folder) {
  row.addEventListener("dragover", (e) => { e.preventDefault(); row.classList.add("drag-over"); });
  row.addEventListener("dragleave", () => row.classList.remove("drag-over"));
  row.addEventListener("drop", async (e) => {
    e.preventDefault();
    row.classList.remove("drag-over");
    const entries = entriesFromDrop(e.dataTransfer);
    const folderEntries = entries.filter((en) => en.isDirectory);
    if (folderEntries.length) {
      for (const folderEntry of folderEntries) {
        el("topTitle").textContent = `Reading "${folderEntry.name}"...`;
        const allFiles = await collectAllFiles(folderEntry);
        const audioFiles = allFiles.filter(isAudioFile);
        const coverFile = allFiles.find(isCoverImageFile);
        if (audioFiles.length) await createAlbumFromFolderFiles(folder.id, folderEntry.name, audioFiles, coverFile);
      }
      openGenre(folder.id, folder.name);
      return;
    }

    // webkitGetAsEntry() isn't guaranteed everywhere (e.g. some non-Chromium
    // browsers) - fall back to the plain FileList so loose-file drops still
    // work even when it's unavailable and entries came back empty.
    let looseFiles;
    if (entries.length) {
      looseFiles = [];
      for (const en of entries.filter((en) => en.isFile)) {
        const file = await entryToFile(en);
        if (/\.(mp3|m4a)$/i.test(file.name)) looseFiles.push(file);
      }
    } else {
      looseFiles = [...e.dataTransfer.files].filter((f) => /\.(mp3|m4a)$/i.test(f.name));
    }
    if (!looseFiles.length) return;
    libState.genreId = folder.id;
    libState.genreName = folder.name;
    openAddAlbumModal();
    const dt = new DataTransfer();
    looseFiles.forEach((f) => dt.items.add(f));
    el("albumSongFiles").files = dt.files;
    el("albumNameInput").focus();
  });
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
    const li = document.createElement("li");
    li.className = "genre-row";
    li.innerHTML = `<button class="genre-name">${f.name.toUpperCase()}</button>
      <button class="icon-sm" data-edit title="Rename">&#9998;</button>
      <button class="icon-sm danger" data-del title="Delete">&#128465;</button>`;
    li.querySelector(".genre-name").onclick = () => openGenre(f.id, f.name);
    li.querySelector("[data-edit]").onclick = () => renameGenre(f.id, f.name);
    li.querySelector("[data-del]").onclick = () => deleteGenre(f.id, f.name);
    wireGenreDropTarget(li, f);
    list.appendChild(li);
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
    card.innerHTML = `<div class="card-actions">
        <button data-edit title="Rename">&#9998;</button>
        <button data-del title="Delete">&#128465;</button>
      </div>
      <img alt="">
      <div class="title">${folder.name}</div>
      <div class="artist"></div>`;
    grid.appendChild(card);
    wireAlbumDropTarget(card, folder);
    loadAlbumCardMeta(folder, card); // fire-and-forget, fills in async
  }
  showLibView("album");
}

async function renameAlbum(folder, currentTitle, currentArtist) {
  const newTitle = prompt("Album title:", currentTitle);
  if (newTitle === null || !newTitle.trim()) return;
  const newArtist = prompt("Artist:", currentArtist);
  if (newArtist === null) return;
  const data = { title: newTitle.trim(), artist: newArtist.trim() || "Unknown Artist" };
  const meta = await findChildByName(folder.id, "metadata.json");
  if (meta) await saveJsonFile(meta.id, data);
  else await uploadNewFile(folder.id, "metadata.json", new Blob([JSON.stringify(data)]), "application/json");
  openGenre(libState.genreId, libState.genreName);
}

async function deleteAlbum(folder, title) {
  if (!confirm(`Delete "${title}" and all its songs?\n\nThis moves it to your Google Drive trash, so it's recoverable there for 30 days.`)) return;
  await deleteFile(folder.id);
  openGenre(libState.genreId, libState.genreName);
}

// Lets you drop more MP3/M4A files (loose, or inside a folder) straight
// onto an existing album's cover to add them to that album, without
// opening the Add Album modal.
function wireAlbumDropTarget(card, folder) {
  card.addEventListener("dragover", (e) => { e.preventDefault(); card.classList.add("drag-over"); });
  card.addEventListener("dragleave", () => card.classList.remove("drag-over"));
  card.addEventListener("drop", async (e) => {
    e.preventDefault();
    card.classList.remove("drag-over");
    const entries = entriesFromDrop(e.dataTransfer);
    let audioFiles = [];
    if (entries.length) {
      let allFiles = [];
      for (const entry of entries) allFiles = allFiles.concat(await collectAllFiles(entry));
      audioFiles = allFiles.filter(isAudioFile);
    } else {
      audioFiles = [...e.dataTransfer.files].filter(isAudioFile);
    }
    if (!audioFiles.length) return;
    for (let i = 0; i < audioFiles.length; i++) {
      el("topTitle").textContent = `Uploading ${i + 1}/${audioFiles.length}...`;
      await uploadAudioFileWithTags(folder.id, audioFiles[i]);
    }
    openGenre(libState.genreId, libState.genreName);
  });
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
  card.querySelector("[data-edit]").onclick = (e) => { e.stopPropagation(); renameAlbum(folder, title, artist); };
  card.querySelector("[data-del]").onclick = (e) => { e.stopPropagation(); deleteAlbum(folder, title); };

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
  renderSongList();
  showLibView("song");
}

function renderSongList() {
  const list = el("songList");
  list.innerHTML = "";
  if (!libState.songs.length) {
    list.innerHTML = "<li>No songs in this album yet.</li>";
    return;
  }
  libState.songs.forEach((file, idx) => {
    const li = document.createElement("li");
    li.innerHTML = `<span class="track-name">${cleanSongTitle(file.name, libState.artist)}</span>
      <span><button data-dl>Download</button><button data-del>Delete</button></span>`;
    li.querySelector(".track-name").onclick = () => playSong(idx);
    li.querySelector("[data-dl]").onclick = async () => {
      const blob = await fetchFileBlob(file.id);
      triggerBrowserDownload(blob, file.name);
    };
    li.querySelector("[data-del]").onclick = () => deleteSong(idx);
    list.appendChild(li);
  });
}

async function deleteSong(idx) {
  const file = libState.songs[idx];
  if (!confirm(`Delete "${cleanSongTitle(file.name, libState.artist)}"?\n\nThis moves it to your Google Drive trash, so it's recoverable there for 30 days.`)) return;
  await deleteFile(file.id);
  libState.songs.splice(idx, 1);
  if (libState.songIdx === idx) { el("audio").pause(); el("player").hidden = true; libState.songIdx = -1; }
  else if (libState.songIdx > idx) libState.songIdx--;
  renderSongList();
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
