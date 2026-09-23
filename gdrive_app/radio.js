let radioSearchResults = [];
let radioStationsFileId = null;
let myStations = [];

async function initRadio() {
  const { fileId, data } = await loadOrCreateJsonFile(driveIds.root, "radio_stations.json", []);
  radioStationsFileId = fileId;
  myStations = data;
  renderSavedStations();
}

function stopRadio() {
  const ra = el("radioAudio");
  ra.pause();
  ra.hidden = true;
}

async function searchRadio() {
  const q = el("radioSearchInput").value.trim();
  if (!q) return;
  el("radioStatus").textContent = `Searching for "${q}"...`;
  try {
    const resp = await fetch(`${RADIO_SEARCH_API}?name=${encodeURIComponent(q)}&limit=25&hidebroken=true&order=clickcount&reverse=true`, {
      headers: { "User-Agent": "MyFavoriteThingsApp/1.0" },
    });
    radioSearchResults = await resp.json();
  } catch (err) {
    console.error(err);
    el("radioStatus").textContent = "Search failed - see console.";
    return;
  }
  const box = el("radioResults");
  box.innerHTML = "";
  radioSearchResults.forEach((s, idx) => {
    const url = s.url_resolved || s.url;
    if (!url) return;
    const row = document.createElement("div");
    row.className = "radio-row";
    row.innerHTML = `<span>${s.name} <small>[${s.countrycode || ""} ${s.codec || ""} ${s.bitrate || ""}kbps]</small></span>
      <button data-idx="${idx}">+ Add</button>`;
    row.querySelector("button").onclick = () => addStation(s.name, url);
    box.appendChild(row);
  });
  el("radioStatus").textContent = radioSearchResults.length ? `Found ${radioSearchResults.length} station(s)` : "No stations found";
}

async function addStation(name, url) {
  if (myStations.some((s) => s.url === url)) return;
  myStations.push({ name, url });
  await saveJsonFile(radioStationsFileId, myStations);
  renderSavedStations();
}

async function removeStation(idx) {
  myStations.splice(idx, 1);
  await saveJsonFile(radioStationsFileId, myStations);
  renderSavedStations();
}

async function renameStation(idx) {
  const newName = prompt("Rename station:", myStations[idx].name);
  if (!newName || !newName.trim()) return;
  myStations[idx].name = newName.trim();
  await saveJsonFile(radioStationsFileId, myStations);
  renderSavedStations();
}

function renderSavedStations() {
  const box = el("radioSaved");
  box.innerHTML = "";
  if (!myStations.length) {
    box.innerHTML = "<div class='hint'>No saved stations yet - search above and tap + Add.</div>";
    return;
  }
  myStations.forEach((s, idx) => {
    const row = document.createElement("div");
    row.className = "radio-row";
    row.innerHTML = `<span>${s.name}</span>
      <span><button data-play>&#9654;</button><button data-edit>&#9998;</button><button data-remove>&times;</button></span>`;
    row.querySelector("[data-play]").onclick = () => playStation(s.name, s.url);
    row.querySelector("[data-edit]").onclick = () => renameStation(idx);
    row.querySelector("[data-remove]").onclick = () => removeStation(idx);
    box.appendChild(row);
  });
}

function playStation(name, url) {
  const audio = el("audio");
  audio.pause();
  el("player").hidden = true;
  const ra = el("radioAudio");
  ra.src = url;
  ra.hidden = false;
  ra.play();
  el("radioStatus").textContent = `Playing: ${name}`;
  showStationInMediaSession(name);
}

// Station name in the phone's media controls; track skipping doesn't apply
// to a live stream, so those buttons are switched off until an album plays.
function showStationInMediaSession(name) {
  if (!("mediaSession" in navigator)) return;
  const ms = navigator.mediaSession;
  ms.metadata = new MediaMetadata({
    title: name,
    artist: "Radio",
    artwork: [
      { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  });
  const ra = el("radioAudio");
  const handlers = { play: () => ra.play(), pause: () => ra.pause(), previoustrack: null, nexttrack: null, seekto: null, seekbackward: null, seekforward: null };
  for (const [action, handler] of Object.entries(handlers)) {
    try { ms.setActionHandler(action, handler); } catch { /* unsupported action */ }
  }
}

el("radioSearchBtn").addEventListener("click", searchRadio);
el("radioSearchInput").addEventListener("keydown", (e) => { if (e.key === "Enter") searchRadio(); });
