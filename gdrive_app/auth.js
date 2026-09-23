const SCOPE = "https://www.googleapis.com/auth/drive.file";

let tokenClient = null;
let accessToken = null;
let gapiReady = false;
let refreshTimer = null;
let isOfflineMode = false;
let authResolved = false;

// Folder IDs, resolved once at sign-in and reused everywhere.
const driveIds = { root: null, music: null };

function loadGapiClient() {
  return new Promise((resolve) => {
    gapi.load("client", async () => {
      await gapi.client.init({});
      await gapi.client.load("https://www.googleapis.com/discovery/v1/apis/drive/v3/rest");
      gapiReady = true;
      resolve();
    });
  });
}

let attemptingSilently = false;

function initTokenClient() {
  tokenClient = google.accounts.oauth2.initTokenClient({
    client_id: CLIENT_ID,
    scope: SCOPE,
    callback: async (tokenResponse) => {
      authResolved = true;
      // We may have already fallen back to offline mode (see initAuth's
      // timeout) by the time a slow request finally comes back - ignore it
      // rather than yanking the UI out of offline mode mid-use.
      if (isOfflineMode) return;
      if (tokenResponse.error) {
        // A silent auto-attempt failing just means "not currently signed
        // in" (first visit, or fully logged out of Google) - that's the
        // normal case, not an error, so just show the login button quietly.
        if (!attemptingSilently) {
          console.error(tokenResponse);
          alert("Sign-in failed: " + tokenResponse.error);
        }
        attemptingSilently = false;
        return;
      }
      attemptingSilently = false;
      accessToken = tokenResponse.access_token;
      gapi.client.setToken(tokenResponse);
      scheduleTokenRefresh(tokenResponse.expires_in);
      await setupFolderStructure();
      onSignedIn(); // defined in main.js - kicks off every tab
    },
  });
}

// Tries to sign in without any popup or user interaction, using your
// existing Google session in this browser - succeeds silently if you've
// signed into this app before and are still logged into Google, so you
// don't have to tap "Sign in" every time you open the app.
function attemptSilentSignIn() {
  attemptingSilently = true;
  tokenClient.requestAccessToken({ prompt: "" });
}

// Google's token-client flow doesn't hand out a refresh token to pure
// client-side apps - access tokens last ~1hr. This attempts a silent
// re-grant (no popup) shortly before expiry, which succeeds as long as
// you're still signed into Google in this browser; if that ever fails,
// you'll just need to click "Sign in with Google" again.
function scheduleTokenRefresh(expiresInSeconds) {
  if (refreshTimer) clearTimeout(refreshTimer);
  const refreshInMs = Math.max(60, expiresInSeconds - 300) * 1000;
  refreshTimer = setTimeout(() => tokenClient.requestAccessToken({ prompt: "" }), refreshInMs);
}

async function setupFolderStructure() {
  driveIds.root = await findOrCreateChild("root", ROOT_FOLDER_NAME, true);
  driveIds.music = await findOrCreateChild(driveIds.root, "Music", true);
}

function login() {
  attemptingSilently = false;
  tokenClient.requestAccessToken();
}

// Shown when there's no way to reach Google at all (offline at load time,
// the auth scripts failed to load, or sign-in just never came back within
// a few seconds) - falls back to whatever's already been downloaded for
// offline use instead of leaving the user stuck on the sign-in screen.
function enterOfflineMode() {
  if (isOfflineMode) return;
  isOfflineMode = true;
  el("loginBtn").hidden = true;
  el("userLabel").textContent = "Offline (tap to reconnect)";
  el("userLabel").style.cursor = "pointer";
  el("userLabel").onclick = () => location.reload();
  el("app").hidden = false;
  onOfflineMode(); // defined in main.js
}

(async function initAuth() {
  // main.js (which defines onOfflineMode/onSignedIn) is a later <script>
  // tag that hasn't run yet at this point - deferring even the "no network
  // at all" fast path to a fresh macrotask guarantees every script has
  // finished executing first (a microtask isn't enough: Chromium drains
  // the microtask queue between individual <script> tags, not just after
  // all of them), exactly like the online path already gets for free by
  // only calling onSignedIn() from an async network callback.
  await new Promise((resolve) => setTimeout(resolve, 0));

  if (!navigator.onLine) return enterOfflineMode();

  // If nothing resolves (success, failure, or a thrown error below) within
  // a few seconds, assume the network is unreachable even though the OS
  // thinks it's connected (captive portal, dead wifi, etc.) and fall back.
  setTimeout(() => { if (!authResolved) enterOfflineMode(); }, 7000);

  try {
    await loadGapiClient();
  } catch (err) {
    authResolved = true;
    return enterOfflineMode();
  }
  initTokenClient();
  attemptSilentSignIn();
})();
