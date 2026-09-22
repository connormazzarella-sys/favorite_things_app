const SCOPE = "https://www.googleapis.com/auth/drive.file";

let tokenClient = null;
let accessToken = null;
let gapiReady = false;
let refreshTimer = null;

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

function initTokenClient() {
  tokenClient = google.accounts.oauth2.initTokenClient({
    client_id: CLIENT_ID,
    scope: SCOPE,
    callback: async (tokenResponse) => {
      if (tokenResponse.error) {
        console.error(tokenResponse);
        alert("Sign-in failed: " + tokenResponse.error);
        return;
      }
      accessToken = tokenResponse.access_token;
      gapi.client.setToken(tokenResponse);
      scheduleTokenRefresh(tokenResponse.expires_in);
      await setupFolderStructure();
      onSignedIn(); // defined in main.js - kicks off every tab
    },
  });
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
  tokenClient.requestAccessToken();
}

(async function initAuth() {
  await loadGapiClient();
  initTokenClient();
})();
