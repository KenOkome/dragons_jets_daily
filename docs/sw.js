const STATIC_CACHE = 'myspo-static-v4.0';
const DATA_CACHE = 'myspo-data-v4.0';

const ASSETS_TO_CACHE = [
    './',
    './index.html',
    './style.css?v=4.0',
    './manifest.json',
    './icon.svg',
    './assets/dragons_emblem.svg',
    './assets/jets_emblem.svg',
    './assets/motorsport_emblem.svg',
    './assets/world_emblem.svg'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => cache.addAll(ASSETS_TO_CACHE))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    const allowedCaches = new Set([STATIC_CACHE, DATA_CACHE]);
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((key) => !allowedCaches.has(key)).map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const req = event.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);
    if (url.origin !== self.location.origin) return;

    const isHtmlOrData =
        req.mode === 'navigate' ||
        url.pathname.endsWith('/') ||
        url.pathname.endsWith('/index.html') ||
        url.pathname.endsWith('.json');

    if (isHtmlOrData) {
        // HTMLおよびアーカイブJSONはブラウザキャッシュをバイパスして最新を取得し、オフライン時はキャッシュを返す
        event.respondWith(
            fetch(req, { cache: 'no-cache' })
                .then((response) => {
                    if (response && response.status === 200) {
                        const clone = response.clone();
                        const targetCache = url.pathname.endsWith('.json') ? DATA_CACHE : STATIC_CACHE;
                        caches.open(targetCache).then((cache) => cache.put(req, clone));
                    }
                    return response;
                })
                .catch(() => caches.match(req))
        );
    } else {
        // 静的アセット（CSS・SVG等）はキャッシュ優先＋バックグラウンド更新
        event.respondWith(
            caches.match(req).then((cached) => {
                const networkFetch = fetch(req)
                    .then((response) => {
                        if (response && response.status === 200) {
                            const clone = response.clone();
                            caches.open(STATIC_CACHE).then((cache) => cache.put(req, clone));
                        }
                        return response;
                    })
                    .catch(() => cached);
                return cached || networkFetch;
            })
        );
    }
});
