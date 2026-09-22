# My Favorite Things — Google Drive Music Library + Radio

No backend, no Termux. The browser authenticates directly with Google and
talks to the Drive API; Google Drive is the storage. Scope: Music Library
(Genre → Album → Song, matching the real app's structure) and Radio. Journal,
Favorites, and the Theme system are intentionally not part of this build.

## 1. Google Cloud Console setup (~10 minutes)

1. Go to [console.cloud.google.com](https://console.cloud.google.com), create
   or select a project.
2. **APIs & Services → Library** → search **Google Drive API** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type: **External**
   - Fill in the required app name/support email fields
   - **Scopes**: add `.../auth/drive.file`
   - **Test users**: add your own Google account's email — while the app is
     in "Testing" status (fine to leave it there for personal use), only
     listed accounts can sign in. Skipping this is the #1 cause of a
     confusing "access_denied" error on first login.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Web application**
   - **Authorized JavaScript origins** — add:
     - `http://localhost:8090`
     - your future Netlify URL, once you have it
   - No redirect URI needed - the token-client flow used here is popup-based,
     handled internally by Google's own code.
5. Copy the **Client ID** into `config.js`.

## 2. Run it locally

```bash
python -m http.server 8090
```

Open `http://localhost:8090`, sign in, approve access. The app creates its
own folder structure in your Drive on first sign-in:

```
FavouriteThingsApp/
  Music/<Genre>/<Album>/*.mp3 (+ metadata.json, cover.jpg)
  radio_stations.json
```

## 3. Deploy to Netlify

Push this folder to GitHub or drag-and-drop it onto
[app.netlify.com/drop](https://app.netlify.com/drop), then add the real
`https://....netlify.app` URL to the OAuth client's Authorized JavaScript
origins (same place as the localhost one).

## How to use it

- **Library tab**: tap a genre to see its albums (with cover art, if you
  added one), tap an album to see its songs, tap a song to play it. The "+"
  in the header adds a new genre (from the genre list) or a new album with
  songs + optional cover + artist (from inside a genre). Each song has a
  Download button that saves it straight to your device.
- **Radio tab**: search stations (via the free radio-browser.info API),
  tap **+ Add** to save one, tap the play icon to stream it. Saved stations
  sync across devices via `radio_stations.json` in your Drive, same as the
  music library.

## Important things to know

- **Scope is `drive.file`, not full Drive access** - this app only ever
  sees files/folders it created itself, which is why it builds its own
  `FavouriteThingsApp` folder rather than expecting one to already exist.
- **Sessions last about an hour, not indefinitely.** Google's token-client
  flow doesn't give a pure client-side app a refresh token - only an access
  token good for ~1hr. The app attempts a silent, popup-free renewal a few
  minutes before expiry, which works as long as you're still signed into
  Google in that browser; otherwise, just click sign-in again.
- **No true range-streaming.** Playing or downloading a song fetches the
  whole file into memory as a Blob first - fine for song-length audio, not
  suited to very large files.
- **Cover art must be uploaded manually** when adding an album - this
  version doesn't extract embedded ID3 art from the MP3s themselves (that
  would need an additional JS ID3-parsing library, not included yet).
