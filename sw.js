/* OráculoRFIR · service worker: la app, el banco de preguntas y las imágenes ya vistas funcionan sin conexión.
   index.html y data/*.json: primero la red (para recibir actualizaciones) y, si no hay, la copia guardada.
   Imágenes e iconos: primero la copia guardada. Las llamadas a proveedores de IA nunca se guardan. */
const CACHE = 'oraculorfir-v2';
const BASE = ['./', 'index.html', 'data/rfir.json', 'data/asignaturas.json', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;   // IA y demás orígenes: directo a la red
  const primeroCache = /\/(data\/img|icons)\//.test(u.pathname);
  if (primeroCache) {
    e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(res => { if (res.ok) { const cp = res.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); } return res; })));
  } else {
    e.respondWith(fetch(e.request, {cache: 'no-cache'}).then(res =>   // no-cache: pregunta siempre al servidor si hay versión nueva { if (res.ok) { const cp = res.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)); } return res; })
      .catch(() => caches.match(e.request, {ignoreSearch: true}).then(r => r || caches.match('index.html'))));
  }
});
