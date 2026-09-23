// Local (per-device) library of albums explicitly downloaded for offline
// use. Entirely separate from Google Drive - this is what the app reads
// from when there's no internet connection at all.

const OFFLINE_DB_NAME = "FavoriteThingsOffline";
const OFFLINE_DB_VERSION = 1;

function openOfflineDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("genres")) db.createObjectStore("genres", { keyPath: "id" });
      if (!db.objectStoreNames.contains("albums")) db.createObjectStore("albums", { keyPath: "id" }).createIndex("genreId", "genreId");
      if (!db.objectStoreNames.contains("songs")) db.createObjectStore("songs", { keyPath: "id" }).createIndex("albumId", "albumId");
      if (!db.objectStoreNames.contains("covers")) db.createObjectStore("covers", { keyPath: "albumId" });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function idbRequest(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function txDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

// genre/album are {id, name}/{id, title, artist}; songs is [{id, name, blob}];
// coverBlob may be null.
async function saveAlbumOffline(genre, album, songs, coverBlob) {
  const db = await openOfflineDb();
  const tx = db.transaction(["genres", "albums", "songs", "covers"], "readwrite");
  tx.objectStore("genres").put({ id: genre.id, name: genre.name });
  tx.objectStore("albums").put({ id: album.id, genreId: genre.id, title: album.title, artist: album.artist });
  if (coverBlob) tx.objectStore("covers").put({ albumId: album.id, blob: coverBlob });
  for (const song of songs) tx.objectStore("songs").put({ id: song.id, albumId: album.id, name: song.name, blob: song.blob });
  return txDone(tx);
}

async function removeAlbumOffline(albumId) {
  const db = await openOfflineDb();
  const tx = db.transaction(["albums", "songs", "covers"], "readwrite");
  tx.objectStore("albums").delete(albumId);
  tx.objectStore("covers").delete(albumId);
  const cursorReq = tx.objectStore("songs").index("albumId").openCursor(IDBKeyRange.only(albumId));
  cursorReq.onsuccess = () => {
    const cursor = cursorReq.result;
    if (cursor) { cursor.delete(); cursor.continue(); }
  };
  return txDone(tx);
}

async function isAlbumOffline(albumId) {
  const db = await openOfflineDb();
  const tx = db.transaction("albums", "readonly");
  const result = await idbRequest(tx.objectStore("albums").get(albumId));
  return !!result;
}

async function listOfflineGenres() {
  const db = await openOfflineDb();
  const tx = db.transaction("genres", "readonly");
  return idbRequest(tx.objectStore("genres").getAll());
}

async function listOfflineAlbums(genreId) {
  const db = await openOfflineDb();
  const tx = db.transaction("albums", "readonly");
  return idbRequest(tx.objectStore("albums").index("genreId").getAll(IDBKeyRange.only(genreId)));
}

async function listOfflineSongs(albumId) {
  const db = await openOfflineDb();
  const tx = db.transaction("songs", "readonly");
  return idbRequest(tx.objectStore("songs").index("albumId").getAll(IDBKeyRange.only(albumId)));
}

async function getOfflineCover(albumId) {
  const db = await openOfflineDb();
  const tx = db.transaction("covers", "readonly");
  return idbRequest(tx.objectStore("covers").get(albumId));
}

async function getOfflineStorageStats() {
  const db = await openOfflineDb();
  const tx = db.transaction(["albums", "songs", "covers"], "readonly");
  const [albums, songs, covers] = await Promise.all([
    idbRequest(tx.objectStore("albums").getAll()),
    idbRequest(tx.objectStore("songs").getAll()),
    idbRequest(tx.objectStore("covers").getAll()),
  ]);
  const songBytes = songs.reduce((sum, s) => sum + (s.blob ? s.blob.size : 0), 0);
  const coverBytes = covers.reduce((sum, c) => sum + (c.blob ? c.blob.size : 0), 0);
  return { albumCount: albums.length, songCount: songs.length, totalBytes: songBytes + coverBytes };
}
