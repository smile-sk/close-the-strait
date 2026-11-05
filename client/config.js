/* Конфигурация клиента.
 * ЛОКАЛЬНЫЙ запуск: оставь SERVER_URL пустым — клиент отдаётся тем же сервером
 *   (server/server.py), и адрес берётся из location.origin.
 * PLAY MARKET / прод: клиент упакован локально (Capacitor), поэтому укажи
 *   ПОЛНЫЙ адрес прод-сервера, например "https://strait.example.com".
 *   WebSocket-адрес выведется автоматически (http->ws, https->wss).
 */
window.ORMUZ_CONFIG = {
  SERVER_URL: "https://strait.punksnotdead.pp.ua",

  // Языки в онбординге/настройках (файлы assets/lang/<code>.json).
  // По умолчанию — английский (см. i18n.js). Порядок = порядок в списке.
  LANGS: [
    { code: "en", label: "English" },
    { code: "ru", label: "Русский" },
    { code: "uk", label: "Українська" },
    { code: "de", label: "Deutsch" },
    { code: "fr", label: "Français" },
    { code: "it", label: "Italiano" },
    { code: "pl", label: "Polski" },
    { code: "tr", label: "Türkçe" },
    { code: "ar", label: "العربية" },
    { code: "fa", label: "فارسی" },
    { code: "hi", label: "हिन्दी" },
    { code: "zh", label: "中文" },
    { code: "ja", label: "日本語" }
  ],

  // Список фракций (id -> ключ локали с названием). id используется как имя
  // файла флага: assets/flags/<id>.png. Добавляй фракции здесь + клади PNG рядом.
  // id уходит на сервер в поле "country" (обратная совместимость протокола).
  FLAGS: [
    { id: "blood_standard",    name: "flag_blood_standard" },
    { id: "coastal_syndicate", name: "flag_coastal_syndicate" },
    { id: "black_sun",         name: "flag_black_sun" },
    { id: "north_guard",       name: "flag_north_guard" },
    { id: "steel_brotherhood", name: "flag_steel_brotherhood" },
    { id: "ash_phoenix",       name: "flag_ash_phoenix" },
    { id: "mist_lighthouse",   name: "flag_mist_lighthouse" },
    { id: "gold_pyramid",      name: "flag_gold_pyramid" },
    { id: "corsair_raiders",   name: "flag_corsair_raiders" },
    { id: "abyssal_leviathan", name: "flag_abyssal_leviathan" }
  ],

  // --- монетизация / механика ---
  // Цена — только для отображения; реальную ставит Google Play по productId.
  PRICE_LABEL: "$0.99",
  // productId из Google Play Console (одноразовые/расходуемые покупки):
  PRODUCTS: { sink: "sink_barges", fleet: "call_fleet" },
  // Разлок (сервер — источник правды, эти значения только для UI до первого ответа):
  UNLOCK_TAPS: 750,
  AD_EVERY: 150,     // каждые N ТВОИХ тапов — rewarded-реклама
  AD_BONUS: 75,      // сколько тапов добавляет просмотр рекламы
  // Закрытый тест: реклама ещё не подключена, поэтому кнопка «+бонус тапов»
  // засчитывается БЕСПЛАТНО без ролика. Подключишь AdMob (см. ads.js) —
  // поставь false.
  AD_FREE_REWARD: true,
  // В браузере/PWA мок покупок/рекламы включается АВТОМАТИЧЕСКИ (реального
  // биллинга в вебе нет). true — форсит мок и в APK. Для релиза оставь false —
  // на устройстве пойдёт настоящий Google Play Billing.
  BILLING_MOCK: false,
  // ТЕСТ: true = платные действия срабатывают БЕЗ оплаты и без диалога
  // (чтобы гонять механику бесплатно). ПЕРЕД РЕЛИЗОМ поставь false!
  FREE_ACTIONS_TEST: false,
  // Фоновая музыка (файлы в assets/sfx/): расширение и громкость.
  // Поставишь mp3 — оставь "mp3"; если петля щёлкает на стыке — перекодируй в ogg
  // и поставь "ogg". Треки: dune_warpath / desert_veil / blue_grid_horizon / iron_resolve
  MUSIC_EXT: "mp3",
  MUSIC_VOLUME: 0.30
};
