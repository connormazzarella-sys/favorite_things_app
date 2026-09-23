// Caches the app shell itself so the page loads with zero connectivity.
// Deliberately does NOT touch cross-origin requests (Google auth/API
// scripts, the Drive API, radio streams) - those need to be live or fail
// naturally; only our own static files get cached.
const CACHE_NAME = "ft-app-shell-v2";
const APP_SHELL = [
  "/",
  "/index.html",
  "/style.css",
  "/config.js",
  "/offline-db.js",
  "/drive-api.js",
  "/auth.js",
  "/library.js",
  "/radio.js",
  "/main.js",
  "/manifest.json",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (event.request.method !== "GET") return;

  // Network-first: an online visit always gets the latest deployed files
  // (and refreshes the cache), so a new deploy shows up immediately instead
  // of being masked by a stale cached copy. Only falls back to whatever's
  // cached when the network genuinely isn't reachable - true offline use.
  event.respondWith(
    // cache: "no-store" bypasses the browser's own HTTP cache too - without
    // it, a plain fetch() can quietly resolve from disk cache and mask a
    // fresh deploy exactly like the service worker cache itself could.
    fetch(event.request, { cache: "no-store" })
      .then((resp) => {
        const copy = resp.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
        return resp;
      })
      .catch(() => caches.match(event.request))
  );
});
