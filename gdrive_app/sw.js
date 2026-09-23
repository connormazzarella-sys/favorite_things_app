// Caches the app shell itself so the page loads with zero connectivity.
// Deliberately does NOT touch cross-origin requests (Google auth/API
// scripts, the Drive API, radio streams) - those need to be live or fail
// naturally; only our own static files get cached.
const CACHE_NAME = "ft-app-shell-v1";
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

  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return resp;
        })
        .catch(() => cached);
      // Serve the cached shell instantly when we have it, refreshing it in
      // the background - falls through to the network on a first visit.
      return cached || network;
    })
  );
});
