self.addEventListener("install", (event) => {
  event.waitUntil(caches.open("receipt-tracker-v1").then((cache) => cache.addAll(["/", "/static/styles.css", "/static/app.js"])));
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
