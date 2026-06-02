const CACHE_NAME = 'sentinel-v4-cache-v1';
const urlsToCache = [
  '/',
  '/static/index.html',
  '/static/app.js',
  '/static/index.css'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
