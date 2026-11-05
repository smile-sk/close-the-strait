/* Офлайн-кэш статики. Стратегия — NETWORK-FIRST: сначала берём свежий файл с
 * сервера (заменил на сервере — сразу видно новое), а кэш держим как офлайн-запас.
 */
const CACHE_VERSION = "ormuz-v21";
const CORE = [
  "./", "./index.html", "./config.js",
  "./css/style.css",
  "./js/i18n.js", "./js/net.js", "./js/billing.js", "./js/ads.js",
  "./js/game.js", "./js/ui.js", "./js/main.js",
  "./manifest.webmanifest",
  "./assets/bg_strait_map.png", "./assets/ship_barge.png",
  "./assets/switch_toggle_open.png", "./assets/switch_toggle_close.png",
  "./assets/icon_settings.png", "./assets/ui_panel_bg.png",
  "./assets/tanker.png", "./assets/cargo.png", "./assets/warship.png",
  "./assets/barge_wreck.png", "./assets/explosion.png",
  "./assets/icon_sink.png", "./assets/icon_fleet.png",
  "./assets/sfx/switch_on.wav", "./assets/sfx/switch_off.wav",
  "./assets/sfx/sink.wav", "./assets/sfx/fleet.wav",
  "./assets/lang/en.json", "./assets/lang/ru.json", "./assets/lang/uk.json",
  "./assets/lang/de.json", "./assets/lang/fr.json", "./assets/lang/it.json",
  "./assets/lang/pl.json", "./assets/lang/tr.json", "./assets/lang/ar.json",
  "./assets/lang/fa.json", "./assets/lang/hi.json", "./assets/lang/zh.json",
  "./assets/lang/ja.json"
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE_VERSION).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  // API/сокет не трогаем
  if (url.pathname.startsWith("/api/") || url.pathname === "/ws") return;
  if (e.request.method !== "GET") return;
  // NETWORK-FIRST: свежий файл с сервера; при офлайне — из кэша
  e.respondWith(
    fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE_VERSION).then((c) => c.put(e.request, copy)).catch(() => {});
      return res;
    }).catch(() => caches.match(e.request))
  );
});
