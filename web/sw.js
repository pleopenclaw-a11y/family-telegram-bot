/**
 * Family Board — service worker (offline shell).
 *
 * Static files only. This worker NEVER intercepts AI/API endpoints and
 * never touches credentials — in a real deployment the app's API calls
 * go to a server-side endpoint (Track C), and network-first policies
 * for those are configured separately, never here.
 */
const CACHE = 'family-board-v1';
const PRECACHE = ['./', './index.html', './css/styles.css', './js/app.js', './js/api.js', './manifest.webmanifest'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

// Cache-first for the static shell; fall back to network/cache.
self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  // Only cache same-origin static resources we listed.
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request)
        .then((response) => {
          if (response && response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => cached || Response.error());
      return cached || network;
    }),
  );
});