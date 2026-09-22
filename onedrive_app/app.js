// ---------- MSAL setup ----------
const msalConfig = {
  auth: {
    clientId: CLIENT_ID,
    authority: "https://login.microsoftonline.com/common", // supports personal Microsoft accounts
    redirectUri: window.location.origin + window.location.pathname,
  },
  cache: {
    cacheLocation: "localStorage", // survives tab/browser close, needed for a real SPA
  },
};
const msalInstance = new msal.PublicClientApplication(msalConfig);

const loginRequest = { scopes: ["Files.ReadWrite", "User.Read"] };
const GRAPH_ROOT = "https://graph.microsoft.com/v1.0";

const el = (id) => document.getElementById(id);

// ---------- Auth ----------
async function login() {
  // NOTE: loginPopup is what was asked for and works well on desktop browsers.
  // Some mobile browsers block or mishandle auth popups - if that happens on
  // your phone, swap this for msalInstance.loginRedirect(loginRequest) and
  // handle the result via msalInstance.handleRedirectPromise() on page load.
  const result = await msalInstance.loginPopup(loginRequest);
  msalInstance.setActiveAccount(result.account);
  return result.account;
}

async function getToken() {
  const account = msalInstance.getActiveAccount();
  if (!account) throw new Error("Not signed in");
  try {
    const result = await msalInstance.acquireTokenSilent({ ...loginRequest, account });
    return result.accessToken;
  } catch (err) {
    // Silent renewal failed (e.g. refresh token expired) - fall back to an interactive prompt.
    const result = await msalInstance.acquireTokenPopup(loginRequest);
    return result.accessToken;
  }
}

el("loginBtn").addEventListener("click", async () => {
  try {
    const account = await login();
    el("userLabel").textContent = account.username;
    el("loginBtn").hidden = true;
    el("app").hidden = false;
    loadLibrary();
  } catch (err) {
    console.error(err);
    alert("Sign-in failed: " + err.message);
  }
});

// ---------- Library: list + play ----------
async function loadLibrary() {
  el("uploadStatus").textContent = "";
  const token = await getToken();
  const path = `/me/drive/root:${ONEDRIVE_FOLDER_PATH}:/children`;
  const resp = await fetch(`${GRAPH_ROOT}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    if (resp.status === 404) {
      // Folder doesn't exist yet - it's created automatically on first upload.
      renderTrackList([]);
      return;
    }
    throw new Error(`Graph API error ${resp.status}`);
  }
  const data = await resp.json();
  renderTrackList(data.value || []);
}

function renderTrackList(items) {
  const list = el("trackList");
  list.innerHTML = "";
  const songs = items.filter((i) => i.file && /\.(mp3|m4a)$/i.test(i.name));
  if (!songs.length) {
    list.innerHTML = "<li>No songs yet - add one above.</li>";
    return;
  }
  songs.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item.name;
    li.onclick = () => playTrack(item);
    list.appendChild(li);
  });
}

function playTrack(item) {
  // @microsoft.graph.downloadUrl is a pre-authenticated, time-limited direct
  // link Graph includes in the listing response - no Authorization header
  // needed, and no CORS issue since it's served from OneDrive's CDN domain.
  const audio = el("audioPlayer");
  audio.src = item["@microsoft.graph.downloadUrl"];
  audio.play();
  el("nowPlaying").textContent = item.name;
}

el("refreshBtn").addEventListener("click", loadLibrary);

// ---------- Upload ----------
// Graph's simple "PUT /content" only supports files up to 4MB, which most
// real songs exceed. This uses an upload session instead, which supports
// much larger files. For anything under Graph's ~60MB single-chunk guidance
// (i.e. basically any individual song), it's a single PUT to the session's
// pre-authenticated URL with a Content-Range header covering the whole file.
async function uploadFile(file) {
  const token = await getToken();
  const path = `/me/drive/root:${ONEDRIVE_FOLDER_PATH}/${encodeURIComponent(file.name)}:/createUploadSession`;

  const sessionResp = await fetch(`${GRAPH_ROOT}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ item: { "@microsoft.graph.conflictBehavior": "rename" } }),
  });
  if (!sessionResp.ok) throw new Error(`Couldn't start upload session (${sessionResp.status})`);
  const { uploadUrl } = await sessionResp.json();

  const uploadResp = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      "Content-Length": file.size,
      "Content-Range": `bytes 0-${file.size - 1}/${file.size}`,
    },
    body: file,
  });
  if (!uploadResp.ok) throw new Error(`Upload failed (${uploadResp.status})`);
  return uploadResp.json();
}

el("fileInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  el("uploadStatus").textContent = `Uploading ${file.name}...`;
  try {
    await uploadFile(file);
    el("uploadStatus").textContent = "Added!";
    e.target.value = "";
    loadLibrary();
  } catch (err) {
    console.error(err);
    el("uploadStatus").textContent = "Upload failed - see console for details.";
  }
});

// ---------- Restore session on page reload ----------
(async function init() {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    msalInstance.setActiveAccount(accounts[0]);
    el("userLabel").textContent = accounts[0].username;
    el("loginBtn").hidden = true;
    el("app").hidden = false;
    loadLibrary();
  }
})();
