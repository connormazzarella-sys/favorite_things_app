# My Favorite Things — Serverless OneDrive Player

No backend, no Termux, no PC dependency. The browser talks directly to
Microsoft Graph; OneDrive is the storage. Netlify just hosts static files.

## 1. Register the app in Entra (one-time, ~5 minutes)

1. Go to [entra.microsoft.com](https://entra.microsoft.com) and sign in with
   your normal Microsoft account (no paid Azure subscription needed for this).
2. **Identity → Applications → App registrations → New registration**.
3. Name: anything, e.g. `MyFavoriteThings`.
4. **Supported account types**: choose *"Accounts in any organizational
   directory and personal Microsoft accounts"* — this is the option that
   allows your personal OneDrive account to sign in.
5. **Redirect URI**: platform = **Single-page application (SPA)**. Add TWO
   values here (you can add more later the same way):
   - `http://localhost:8090` — for testing on your laptop before deploying
   - `https://YOUR-SITE-NAME.netlify.app` — your real Netlify URL, once you
     know it (you can come back and add this after your first deploy)
6. Click **Register**. On the app's **Overview** page, copy the
   **Application (client) ID** — paste it into `config.js` as `CLIENT_ID`.
7. Go to **API permissions → Add a permission → Microsoft Graph →
   Delegated permissions**, and add:
   - `Files.ReadWrite`
   - `User.Read` (usually already present by default)

   There's no "admin consent" step for a personal account — you'll approve
   these permissions yourself in the login popup the first time you sign in.

## 2. Run it locally first

From this folder:

```bash
python -m http.server 8090
```

Open `http://localhost:8090` in your browser, click **Sign in with
Microsoft**, and approve the permissions. If login works and the library
loads (empty at first), you're ready to deploy.

## 3. Deploy to Netlify

1. Push this `onedrive_app` folder to GitHub (or drag-and-drop the folder
   directly onto [app.netlify.com/drop](https://app.netlify.com/drop) for
   the fastest possible first deploy, no git required).
2. Once deployed, copy your real `https://....netlify.app` URL.
3. Go back to the Entra app registration → **Authentication** → add that
   URL as a second **Single-page application** redirect URI (alongside the
   localhost one from step 1).
4. Visit your live Netlify URL, sign in, and use it from your phone too —
   it's just a website, works in any browser, "Add to Home Screen" makes it
   feel like a real app.

## Notes

- **Uploads use Graph's upload-session endpoint**, not the simple 4MB-limited
  `PUT /content` — necessary because most real songs exceed 4MB.
- **Mobile popups**: `loginPopup` works well on desktop. If Android Chrome
  ever blocks or mishandles the login popup, swap `msalInstance.loginPopup()`
  for `msalInstance.loginRedirect()` in `app.js`, and handle the return value
  via `msalInstance.handleRedirectPromise()` when the page loads.
- The music folder (`/FavouriteThingsApp/Music` in your OneDrive) is created
  automatically the first time you upload a song — nothing to set up by hand.
