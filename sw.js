const CACHE = 'carecompanion-v59';
const FILES = [
  '/CareCompanion/',
  '/CareCompanion/manifest.json',
  '/CareCompanion/icon-192.png',
  '/CareCompanion/icon-512.png',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      Promise.allSettled(FILES.map(f => c.add(f)))
    )
  );
  // Wait for message from app before taking over
});

self.addEventListener('message', e => {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => clients.claim())
  );
});

self.addEventListener('fetch', e => {
  // Network-first: always try to get fresh content, fall back to cache if offline
  e.respondWith(
    fetch(e.request).then(res => {
      if (res && res.status === 200) {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return res;
    }).catch(() => {
      // Offline — serve from cache
      return caches.match(e.request)
        .then(cached => cached || caches.match('/CareCompanion/index.html'));
    })
  );
});
