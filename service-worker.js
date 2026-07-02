const CACHE_NAME = 'inworker-cache-v2'; // Subimos la versión para forzar limpieza
const urlsToCache = ['/static/manifest.json'];

// Instalar el Service Worker
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(urlsToCache);
        }).then(() => self.skipWaiting()) // Forzar a que se active de inmediato
    );
});

// Activar y destruir cachés antiguos por completo
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cache => {
                    if (cache !== CACHE_NAME) {
                        console.log('Borrando caché antiguo:', cache);
                        return caches.delete(cache);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// ESTRATEGIA: Red primero (Network First). Así tus estilos y el perfil cambian al instante
self.addEventListener('fetch', event => {
    // No interceptar peticiones de la API o POST para que Gemini no se bloquee
    if (event.request.url.includes('/api/') || event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        fetch(event.request)
            .then(networkResponse => {
                // Si la red responde bien, clonamos y guardamos en caché
                if (networkResponse && networkResponse.status === 200) {
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseToCache);
                    });
                }
                return networkResponse;
            })
            .catch(() => {
                // Si estás en el rincón más oscuro de Barranquilla sin señal, usa la caché
                return caches.match(event.request);
            })
    );
});