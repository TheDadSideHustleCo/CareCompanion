// CareCompanion Service Worker v13
const CACHE_NAME = 'carecompanion-v13';

const ASSETS_TO_CACHE = [
  './carecompanion.html',
  '/',
  '/index.html',
  './lato-300.ttf',
  './lato-400.ttf',
  './lato-700.ttf',
  './playfair-400.ttf',
  './playfair-600.ttf',
  './playfair-italic-400.ttf',
];

// Install — cache all assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(ASSETS_TO_CACHE))
  );
  self.skipWaiting();
});

// Activate — purge old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch — cache-first strategy
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(cached => {
      return cached || fetch(event.request).then(response => {
        if (response && response.status === 200 && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    }).catch(() => {
      if (event.request.mode === 'navigate') {
        return caches.match('./carecompanion.html');
      }
    })
  );
});

// SKIP_WAITING — allow clients to trigger update immediately
self.addEventListener('message', event => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self