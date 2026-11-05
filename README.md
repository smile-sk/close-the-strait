# Strait Control — клиент + сервер

Кооперативный кликер по ТЗ: один индустриальный тумблер `ОТКРЫТО / ЗАКРЫТО`,
баржи перекрывают или освобождают пролив, состояние синхронизируется у всех
подключённых игроков в реальном времени (WebSocket) с фоновым REST для
первичной загрузки.

Всё графическое — **PNG-заглушки**, сгенерированные скриптом
`tools/gen_placeholders.py`. Меняй арт по одному файлу, не трогая код: клиент
грузит ассеты по фиксированным путям (`assets/*.png`).

> **История переименования.** Первая версия игры называлась «Close The
> Strait!» (`com.creadevapps.closethestrait`) и была прямо привязана к
> реальной геополитике вокруг Ормузского пролива — карта, флаги стран,
> названия. Google Play заблокировал приложение по политике Sensitive Events
> («капитализация на чувствительном событии») и после апелляции ответил, что
> реинстейт невозможен и нужно публиковать заново под **новым package name и
> новым названием**. Начиная с v8 из игры убраны реальные карты, флаги и
> названия стран — фракции полностью вымышленные. Проект переименован в
> **Strait Control** (`com.creadevapps.straitcontrol`), это новый листинг в
> Play Console с нуля (новый keystore, новые скриншоты/описание). Старые id
> ниже по тексту оставлены только там, где это чужие внешние сущности
> (тестовый домен сервера) и переименование самого проекта их не требует.

---

## Структура

```
strait-control/
├── client/                     ← то, что уходит в Play Market
│   ├── index.html
│   ├── config.js               ← адрес сервера + списки стран/языков
│   ├── css/style.css           ← safe-area (монобровь/вырезы) учтён
│   ├── js/
│   │   ├── i18n.js             ← локализация
│   │   ├── net.js              ← REST + WebSocket (+ автопереподключение)
│   │   ├── game.js             ← canvas: карта + анимация барж
│   │   ├── ui.js               ← профиль, шапка, тумблер, модалки
│   │   └── main.js             ← точка входа
│   ├── assets/
│   │   ├── bg_strait_map.png   ← фон-карта пролива (портрет 1080×1920)
│   │   ├── ship_barge.png      ← баржа (вид сверху, прозрачный фон)
│   │   ├── switch_toggle_open.png / switch_toggle_close.png
│   │   │                        ← ЦЕЛЬНАЯ картинка рубильника (по одной на состояние)
│   │   ├── switch_base.png     ← (не используется клиентом, оставлен для справки)
│   │   ├── icon_settings.png   ← шестерёнка
│   │   ├── ui_panel_bg.png     ← фон модалок
│   │   ├── sfx/switch_on.wav / switch_off.wav ← звук переключения
│   │   ├── flags/<iso>.png     ← флаги вымышленных фракций
│   │   └── lang/<code>.json    ← словари (13 языков)
│   ├── icons/                  ← иконки приложения + feature graphic
│   ├── manifest.webmanifest    ← PWA-манифест
│   └── sw.js                   ← офлайн-кэш
├── server/
│   ├── server.py               ← stdlib: статика + REST + WS + state.json
│   └── state.json              ← простая JSON-БД (ТЗ §6.1)
├── tools/
│   └── gen_placeholders.py     ← генератор ВСЕЙ графики (правь и перегенеряй)
├── resources/
│   ├── patch_android.py        ← портрет + фон сплеша + разрешение BILLING
│   └── README.txt              ← сплеш/иконки
└── README.md
```

---

## 1. Быстрый локальный тест (30 секунд, без установки)

Сервер написан на чистой стандартной библиотеке Python — `pip install` не нужен.

```bash
cd strait-control
python3 server/server.py
```

Открой в браузере адрес, который напечатает консоль (по умолчанию **http://localhost:8123**;
если порт занят другим приложением, сервер сам возьмёт следующий свободный и покажет его). При первом запуске появится онбординг
(язык / имя / страна). Дальше жми тумблер — баржи перестраиваются, шапка обновляется.

> Порт/хост/пути можно переопределить переменными окружения:
> `ORMUZ_PORT=9000 ORMUZ_CLIENT_DIR=... ORMUZ_STATE_FILE=... python3 server/server.py`
> (имена переменных исторические, `ORMUZ_*` — код сервера не переименовывался,
> только клиент/бренд; менять не обязательно).

### Проверить синхронизацию

Открой сайт в двух вкладках (или на телефоне в той же Wi‑Fi сети — тогда вместо
`localhost` возьми IP машины, напр. `http://192.168.x.x:8123`). Переключи тумблер
в одной вкладке — вторая мгновенно проиграет анимацию и обновит шапку. Состояние
переживает перезапуск сервера (лежит в `server/state.json`).

---

## 2. Замена графики

Все ключи ассетов зафиксированы — просто положи свой PNG с тем же именем/путём:

| Файл | Что это | Замечания |
|---|---|---|
| `assets/bg_strait_map.png` | фон-карта | портрет 1080×1920, «cover». Проще всего заменить исходник — см. ниже |
| `assets/ship_barge.png` | баржа | вид сверху, **прозрачный фон**, нос вправо (вдоль +X) |
| `assets/switch_toggle_open.png` | рубильник «ОТКРЫТО» | **цельная** картинка (панель+рукоятка), прозрачный фон |
| `assets/switch_toggle_close.png` | рубильник «ЗАКРЫТО» | то же, рукоятка в другом положении. Оба одного размера |
| `assets/sfx/switch_on.wav` | звук вкл. | короткий «клац» (≈0.15 c); заменяй любым wav/mp3/ogg |
| `assets/sfx/switch_off.wav` | звук выкл. | то же, тоном ниже |
| `assets/icon_settings.png` | шестерёнка | прозрачный фон, светлая |
| `assets/ui_panel_bg.png` | фон модалок | тянется под размер окна |
| `assets/flags/<iso>.png` | флаг фракции | имя = код из `config.js` |

> Рубильник — теперь **одна картинка на состояние** (клиент просто меняет `src`),
> поэтому на любой вёрстке контур не разъезжается. Подпись под ним
> («ОТКРЫТО/OPEN») рисуется отдельно и локализуется, в картинку её не зашивай.
>
> Готовые состояния лежат в `tools/switch_open.png` и `tools/switch_close.png` —
> генератор их **копирует** в игру (не перерисовывает). Чтобы поставить свой
> рубильник: замени эти два файла (одинаковый размер, прозрачный фон) — или
> удали их, чтобы вернулась рисованная заглушка. Есть ещё
> `tools/make_switch_from_source.py`: из ОДНОГО рендера (положи в
> `tools/source_switch.jpg`, рычаг влево + красное свечение) он делает оба
> состояния — вырезает фон, зеркалит для OPEN и перекрашивает свечение в зелёный
> (нужны `pip install pillow numpy scipy`).
>
> Звук проигрывается при нажатии; выключается галкой «Звук» в настройках
> (шестерёнка), состояние хранится в профиле. Форматы wav/mp3/ogg (правь имена
> в `SFX` в `client/js/ui.js`, если меняешь расширение).

Обновил ассеты в проде под Play Market → подними `CACHE_VERSION` в `client/sw.js`,
иначе клиент отдаст старую графику из кэша.

### Перегенерировать заглушки

```bash
pip install Pillow            # разово
python3 tools/gen_placeholders.py --out client
```

Цвета, размеры, формы, список фракций — всё правится прямо в
`tools/gen_placeholders.py` (палитра в начале файла, по функции на каждый ассет).

### Карта пролива и баржи

Фон — **абстрактная, вымышленная карта** (начиная с v8; реальной географии/
границ/названий стран в ассетах нет — это было условием разблокировки в Play).
Если хочешь заменить исходник схемы: положи своё изображение в
`tools/source_map.jpg` (или `.png`) — генератор кадрирует его «cover» под
портрет 1080×1920. Точка фокуса задаётся в `make_bg` константой `BG_FOCUS_X`
(0..1 по горизонтали исходника). Если файла-исходника нет, рисуется схематичная
карта-заглушка.

Позиции барж привязаны к **карте**, а не к экрану: в `client/js/game.js` заданы
нормализованные якоря `[0..1]` относительно фоновой картинки, а на экран они
переводятся той же «cover»-трансформацией, что и фон. Поэтому на любом
телефоне/кропе баржи стоят ровно на воде пролива. Правь при замене карты:

- `WALL_A` / `WALL_B` — концы стенки в состоянии CLOSED (перекрывают фарватер);
- `OPEN_CENTER` + `OPEN_SPREAD` — состояние OPEN: центр «стоянки» и таблица
  `[du, dv, курс]` на каждую баржу (баржи раскиданы вразброс, каждая со своим
  курсом, чтобы не читались одной линией);
- `N` — число барж, `BARGE_FRAC` — их размер как доля ширины карты.

Ставь точки по воде (не на суше). Для CLOSED баржи интерполируются между
`WALL_A` и `WALL_B`; для OPEN берутся из `OPEN_SPREAD` (если увеличишь `N` больше
длины таблицы — лишние баржи пойдут по кругу таблицы, дополни её при желании).

---

## 3. Локализация и страны

В комплекте **13 языков**: English (по умолчанию), Русский, Українська,
Deutsch, Français, Italiano, Polski, Türkçe, العربية (RTL), فارسی (RTL),
हिन्दी, 中文, 日本語. Файлы — `client/assets/lang/<code>.json`, список в
онбординге/настройках — `LANGS` в `client/config.js` (порядок = порядок показа).

**Добавить язык:** создай `client/assets/lang/xx.json` (скопируй `en.json`,
переведи значения; для RTL-языков поставь `"dir": "rtl"`), добавь строку в `LANGS`
в `config.js` и в список `CORE` в `client/sw.js` (чтобы кэшировался), затем подними
`CACHE_VERSION` там же.

**Добавить страну/фракцию:** добавь `{ iso, name }` в `COUNTRIES`/`FLAGS` в
`config.js` и положи `client/assets/flags/<iso>.png`.

**Язык по умолчанию** — английский (для нового игрока онбординг открывается на EN).
Меняется в двух местах: `let lang = "en"` в `client/js/i18n.js` и фолбэк
`|| "en"` в `openModal` (`client/js/ui.js`).

Название игры — **«Strait Control»** (в `manifest.webmanifest`, `<title>` и
ключе `app_title` во всех 13 словарях — значение одинаковое, не переводится,
это имя собственное). Формат строки действия — с плейсхолдерами:
`{name}`, `{flag}`, `{status}`.

---

## 3a. Платные действия, лок и разлок (монетизация)

**Механика.** Обычный тумблер открывает/закрывает пролив бесплатно. Два платных
действия ($1.99, без привязки к странам) флипают статус И **запирают** его:

- **«Потопить баржи»** (`sink`) → пролив **ЗАКРЫТ**, баржи затоплены (спрайт
  `barge_wreck`), тумблер серый/неактивен.
- **«Позвать флот»** (`fleet`) → приходят военные корабли (`warship`), мультяшные
  взрывы (`explosion`) на баржах → пролив **ОТКРЫТ**, траффик оживает.

Пока пролив заперт, бесплатно открыть можно только **коллективным тапаньем** по
тумблеру: общий серверный счётчик, порог **750**, а каждые **150** своих тапов —
rewarded-реклама с бонусом **+75**. Платное действие всегда срабатывает и
перезапирает в свою сторону (дефолт; правится на сервере).

**Траффик.** В открытом проливе танкеры/сухогрузы снуют туда-сюда; при закрытом
встают (максимум по одному с каждой стороны).

**Где что крутить:**
- Цены/пороги на клиенте (только UI-подсказки): `client/config.js` —
  `PRICE_LABEL`, `PRODUCTS`, `UNLOCK_TAPS`, `AD_EVERY`, `AD_BONUS`,
  `AD_FREE_REWARD`, `BILLING_MOCK`.
- **Источник правды — сервер:** `server/server.py`, env-переменные
  `ORMUZ_LOCK_SECONDS` (по умолчанию сутки), `ORMUZ_UNLOCK_TAPS`,
  `ORMUZ_AD_EVERY`, `ORMUZ_AD_BONUS`.
- Спрайты — `tools/gen_gameplay_assets.py` (карту/рубильник не трогает).

### Покупки в APK — плагин @capgo/native-purchases (уже подключён в billing.js)

`client/js/billing.js` реализует настоящую покупку через Google Play, с
устойчивым восстановлением после сбоя потребления (см. ниже). В браузере/PWA —
мок (реального биллинга там нет). На устройстве нужно один раз:

```bash
npm install @capgo/native-purchases   # версия плагина = версии Capacitor
npx cap sync android
```

Дальше:
- `resources/patch_android.py` добавляет в манифест разрешение
  `com.android.vending.BILLING` (запусти его после `cap add android`).
- `productId` в `config.js → PRODUCTS` (`sink_barges` / `call_fleet`) должны точно
  совпадать с товарами в Play Console нового приложения (одноразовые/расходуемые;
  сами имена product ID при переименовании проекта менять не обязательно — они
  локальны для каталога конкретного приложения и заводятся в консоли заново).
- `BILLING_MOCK: false` уже стоит — на устройстве код сам идёт в нативную ветку.
- Товар «расходуемый»: в Google Play нет галочки consumable в консоли — это
  определяется только кодом. `billing.js` помечает покупку `isConsumable: true`,
  сам вызывает `consumePurchase` после оплаты (используя правильный токен —
  `purchaseToken || transactionId`, на Android это часто именно
  `transactionId`), и **на каждом старте приложения плюс перед каждой покупкой**
  подчищает все незакрытые покупки (`Billing.init()` в `main.js` +
  `consumeAll()` внутри `buy()`), чтобы «Вы уже владеете этим товаром» не могло
  залипнуть между сборками/сессиями.

Для **закрытого теста** этого достаточно: покупатель — аккаунт из «License
testing» в Play Console, оплата тестовая (без денег), токен уходит на сервер, и
сервер применяет действие. ⚠️ **Перед продакшеном** сервер обязан проверять
`purchaseToken` через Google Play Developer API (`purchases.products.get`) —
сейчас он принимает любой токен (`TODO(prod)` в `server.py`). Без этого платное
действие можно вызвать поддельным токеном. Допиши валидацию на сервере, когда
дойдёшь до продажи за реальные деньги (нужен сервис-аккаунт).

### Реклама (rewarded) — пока выключена

На время закрытого теста рекламы нет: кнопка «посмотреть рекламу +75 тапов»
засчитывается **бесплатно** без ролика (`AD_FREE_REWARD: true` в `config.js`).
Когда подключишь AdMob (`@capacitor-community/admob`) — поставь
`AD_FREE_REWARD: false` и реализуй ветку NATIVE в `client/js/ads.js`.

### Пуши (нативный слой) — делаешь у себя

Это **нельзя** собрать/протестировать в вебе. Billing и реклама описаны выше
(billing.js уже реализован под @capgo/native-purchases, реклама пока бесплатный
бонус). Осталось пуши:

- **Пуш-уведомления (FCM) — ТОЛЬКО на платные действия** (потопить/флот), на
  языке устройства, с галкой отключения в настройках (`profile.push`; сама
  галка временно скрыта из UI в `index.html` — раскомментируй блок `f-push`,
  когда захочешь её вернуть, логика в `ui.js` уже устойчива к обоим случаям).
  Уже готово:
  - клиент регистрирует токен: `client/js/push.js` → `POST /api/v1/push/register`
    (нужен плагин `@capacitor/push-notifications` + `google-services.json` из
    **нового** Firebase-проекта, привязанного к новому `applicationId`, в
    `android/app/`, затем `npx cap sync android`);
  - сервер шлёт пуш только в обработчике `PAID`, локализуя текст из `lang/*.json`
    (`app_title` + `action_sink`/`action_fleet`). Для реальной отправки:
    `pip install firebase-admin` и переменная `ORMUZ_FCM_CRED=/путь/к/serviceAccount.json`
    (сервис-аккаунт из Firebase Console). Без этого пуши тихо пропускаются
    (в логе `[push] skipped … FCM не настроен`) — остальное работает.

**Протокол** (WebSocket, см. шапку `server/server.py`): входящие
`TOGGLE / PAID / TAP / AD`, исходящие `STATE_CHANGED / ACTION / TAP_PROGRESS /
UNLOCKED`. Строка события вверху и пуш локализуются ключами `action_sink` /
`action_fleet` во всех 13 словарях.

---

## 4. Развёртывание сервера (у тебя: постоянный IP + свой веб-сервер)

**Что где живёт.** Мобильное приложение (APK/AAB) содержит клиент ВНУТРИ себя
(Capacitor бандлит статику). На сервере крутится только `server/server.py` —
это REST (`/api/v1/state`) + WebSocket (`/ws`) + отдача клиента для игры в
браузере/PWA. Приложение стучится на сервер по адресу из `client/config.js`
(поле `SERVER_URL`), который вшивается в APK при сборке.

### 4.1. Куда положить и как запустить

Скопируй папку проекта на сервер, например в `/opt/strait-control/`
(годится любой путь — важно лишь указать его в systemd ниже):

```bash
sudo mkdir -p /opt/strait-control
sudo cp -r ./* /opt/strait-control/      # или git clone / scp
sudo chown -R www-data:www-data /opt/strait-control
```

Запускаем `server.py` на **localhost** (наружу его отдаст твой веб-сервер).
`/etc/systemd/system/strait-control.service`:

```ini
[Unit]
Description=Strait Control server
After=network.target

[Service]
WorkingDirectory=/opt/strait-control
Environment=ORMUZ_HOST=127.0.0.1 ORMUZ_PORT=8123
ExecStart=/usr/bin/python3 server/server.py
Restart=always
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now strait-control
sudo systemctl status strait-control      # должно быть active (running)
```

Сервер на чистом stdlib — `pip install` не нужен, только Python 3.10+.
Состояние переживает перезапуск (лежит в `/opt/strait-control/server/state.json`).

### 4.2. Пробросить через твой веб-сервер (обязательно TLS для приложения)

⚠️ Android в релизе **блокирует незашифрованный `ws://`** — нужен `wss://`,
значит нужен **HTTPS с доменом** (Let's Encrypt выдаёт сертификаты на домен, не
на голый IP). Если домена нет — заведи любой (можно бесплатный) и наведи
A-запись на свой IP. Вариант «только по IP, без TLS» годится лишь для теста
(см. 4.4).

Главное в прокси — **проброс WebSocket-апгрейда** на `/ws`.

**nginx** (добавь server-блок или location в существующий конфиг):

```nginx
server {
    listen 443 ssl;
    server_name strait.punksnotdead.pp.ua;
    ssl_certificate     /etc/letsencrypt/live/strait.punksnotdead.pp.ua/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/strait.punksnotdead.pp.ua/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8123;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;    # ← апгрейд сокета
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;                  # держим /ws открытым
    }
}
```
Сертификат: `sudo certbot --nginx -d strait.punksnotdead.pp.ua`.

**Apache** (нужны модули: `proxy proxy_http proxy_wstunnel`, вкл. `a2enmod`):

```apache
<VirtualHost *:443>
    ServerName strait.punksnotdead.pp.ua
    SSLEngine on
    SSLCertificateFile    /etc/letsencrypt/live/strait.punksnotdead.pp.ua/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/strait.punksnotdead.pp.ua/privkey.pem

    # сначала сокет, потом всё остальное
    ProxyPass        /ws  ws://127.0.0.1:8123/ws
    ProxyPassReverse /ws  ws://127.0.0.1:8123/ws
    ProxyPass        /    http://127.0.0.1:8123/
    ProxyPassReverse /    http://127.0.0.1:8123/
    ProxyPreserveHost On
</VirtualHost>
```
Сертификат: `sudo certbot --apache -d strait.punksnotdead.pp.ua`.

После этого прод-адрес — `https://strait.punksnotdead.pp.ua`, а сокет автоматически
станет `wss://strait.punksnotdead.pp.ua/ws`. Проверить: открой этот адрес в браузере —
должна открыться игра; переключи тумблер во второй вкладке и увидишь синхрон.

> Сам домен/сервер переименовывать не обязательно — ребрендинг приложения
> (имя + applicationId) никак не завязан на адрес бэкенда, можно продолжать
> использовать тот же `strait.punksnotdead.pp.ua`.

### 4.3. Указать адрес в клиенте (перед сборкой приложения)

В `client/config.js`:
```js
SERVER_URL: "https://strait.punksnotdead.pp.ua",
```
Клиент сам выведет `wss://…/ws` из `https`. Пустая строка = локальный режим
(берётся `location.origin`) — для приложения так оставлять нельзя.

### 4.4. Только для теста, без домена/TLS

Можно временно ходить на `ws://ТВОЙ-IP:8123` (открой порт 8123 наружу:
`ORMUZ_HOST=0.0.0.0`, `sudo ufw allow 8123`). Но Android разрешит незашифрованный
трафик только если в приложении явно включить cleartext — см. раздел 5.4.
Для публикации в Play так делать не надо, только для отладки.

> Для сотен одновременных соединений stdlib-сервер (поток на клиента) хватит с
> запасом. Захочешь тысячи — перепиши сокет-часть на `asyncio`
> (`websockets`/FastAPI); REST-контракт и `state.json` менять не придётся.

---

## 5. Сборка приложения: APK и AAB (Capacitor)

Игра — статический веб-клиент, поэтому в APK/AAB его удобно упаковать через
**Capacitor** (ассеты кладутся внутрь приложения, отдельный хостинг клиента не
нужен; на сервере остаётся только API/сокет).

**Что есть что:**
- **AAB** (Android App Bundle) — формат, который загружается в Google Play. Это
  НЕ устанавливается на телефон напрямую; Play сам собирает из него APK.
- **APK** — то, что ставится на телефон напрямую (тест/сайдлоад/раздача вне Play).

**Понадобится:** Node.js LTS, JDK 17, Android Studio (с Android SDK).

### 5.1. Инициализация (один раз)

```bash
# 0) Перед сборкой укажи прод-адрес в client/config.js:
#    SERVER_URL: "https://strait.punksnotdead.pp.ua"

cd strait-control
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/android
# имя приложения и applicationId (свой обратный домен + новое имя проекта):
npx cap init "Strait Control" com.creadevapps.straitcontrol --web-dir=client
#   ↑ в комплекте уже есть готовый capacitor.config.json (портрет-сплеш без
#     растяжения, см. 5.5). Если cap init предложит перезаписать — откажись
#     и оставь версию из репозитория.

npx cap add android
npx cap copy android            # копирует client/ внутрь android-проекта

# иконки/сплэш из готового client/icons/icon-512.png (перегенерировать нужно,
# только если сами PNG меняются — простое переименование проекта их не требует)
npm install @capacitor/assets --save-dev
npx @capacitor/assets generate --android --iconBackgroundColor "#0e1016" --splashBackgroundColor "#070707"
```

> **applicationId сменился** (было `com.creadevapps.closethestrait`, теперь
> `com.creadevapps.straitcontrol`) — это новое приложение с точки зрения
> Google Play: новый листинг с нуля, **новый keystore** (не переиспользуй
> старый — см. 5.3), новый Firebase-проект под пуши/AdMob, если были заведены.
> Old `android/` перед этим шагом должна быть удалена (или отсутствовать) —
> `cap add android` создаёт её заново под новый id.

### 5.2. APK для теста (без подписи-ключа, debug)

```bash
cd android
./gradlew assembleDebug
# готово: android/app/build/outputs/apk/debug/app-debug.apk
```
Перекинь `app-debug.apk` на телефон и установи (разреши «установку из этого
источника»). Это самый быстрый способ проверить приложение на устройстве.

### 5.3. AAB для Google Play (release, с подписью)

Нужен **keystore** (ключ подписи), отдельный для нового приложения. Создай один
раз и храни вечно — без него не выпустишь обновления:
```bash
keytool -genkey -v -keystore strait-control.keystore \
        -alias straitcontrol -keyalg RSA -keysize 2048 -validity 10000
```
Проще всего собрать через Android Studio (`npx cap open android`):
`Build → Generate Signed Bundle / APK → Android App Bundle`, выбери keystore,
вариант `release`. Файл появится в
`android/app/build/outputs/bundle/release/app-release.aab` — его и грузишь в
Play Console.

Через командную строку (после настройки подписи в `android/app/build.gradle`):
```bash
cd android
./gradlew bundleRelease      # AAB  → app/build/outputs/bundle/release/
./gradlew assembleRelease    # APK  → app/build/outputs/apk/release/ (если нужен и APK)
```

> Поменял клиент (config.js, ассеты, локализацию) → `npx cap copy android` →
> пересобрать. Для обновления в Play подними `versionCode`/`versionName` в
> `android/app/build.gradle`.

### 5.4. Тест без TLS (только отладка!)

Если сервер пока по `ws://IP:8123` без сертификата, Android заблокирует
незашифрованный трафик. Чтобы временно разрешить — в
`android/app/src/main/AndroidManifest.xml` у `<application>` добавь
`android:usesCleartextTraffic="true"`, а в `config.js` укажи
`SERVER_URL: "http://ТВОЙ-IP:8123"`. **Для релиза убери** — Play не любит
cleartext, да и небезопасно.

### 5.5. Портретная ориентация и заставка (важно)

**Только портрет (телефон И планшет).** Веб-слой уже держит портрет сам:
`screen.orientation.lock("portrait")` (работает в приложении/PWA/WebView) плюс
CSS-рамка `#app`, привязанная к пропорции карты пролива (в браузере игра не
расплывается в ландшафте).

**Заставка растягивала логотип на первом кадре** — это тема запуска Android:
она по умолчанию рисует `splash.png` как `windowBackground`, а Android тянет
bitmap на весь экран (отсюда «плющит»). Через секунду его сменяет плагин
SplashScreen (в `capacitor.config.json` уже стоит `"androidScaleType":
"CENTER_CROP"` — равномерно, без искажений) и веб-заставка `#splash`. Чтобы убрать
и самый первый растянутый кадр, фон темы запуска нужно сделать сплошным цветом.

Ориентацию активности, цвет фона заставки и разрешение Google Play Billing
ставит один скрипт — запусти его **из корня проекта после `npx cap add
android`** (и после `@capacitor/assets generate`, если гонял):

```bash
python3 resources/patch_android.py
```
(на Windows: `py resources/patch_android.py` или `python resources/patch_android.py`
— `python3` там обычно не зарегистрирован)

Он идемпотентен (можно повторять). Папка `android/` пересоздаётся `cap add
android`, поэтому это шаг после каждой чистой генерации. После патча:

```bash
npx cap sync android
cd android && ./gradlew assembleDebug
```

> Логотип на первом кадре теперь не показывается (чистый тёмный фон #070707),
> брендинг покажет центрированно плагин и веб-заставка — искажения нет ни на
> одном этапе. Сами PNG в `resources/` править не нужно.

> Альтернатива Capacitor — TWA через Bubblewrap, но тогда PWA придётся ещё и
> хостить по HTTPS; Capacitor проще, т.к. бандлит клиент локально.

---

## 6. Для карточки в Play Market

Уже сгенерированы заглушки в `client/icons/`:

- `icon-512.png` — иконка приложения (Play требует 512×512).
- `icon-maskable-512.png` — адаптивная иконка (безопасная зона внутри).
- `feature-graphic-1024x500.png` — обложка карточки.

Дополнительно для листинга подготовь: 2–8 скриншотов телефона, короткое и полное
описание, политику конфиденциальности (нужен URL — данные профиля хранятся на
устройстве + имя/фракция уходят на сервер; отрази это), возрастной рейтинг.
Раз это новый листинг — все поля (включая Data Safety форму) заполняются заново.

---

## 7. Чеклист перед публикацией

- [ ] `client/config.js` → `SERVER_URL` = боевой `https://`-адрес
- [ ] Прод-сервер под TLS, `/ws` проксируется (проверь `wss://…/ws`)
- [ ] Заменены финальные ассеты, поднят `CACHE_VERSION` в `sw.js`
- [ ] Карта — абстрактная/вымышленная (без реальной географии/флагов/названий стран)
- [ ] `applicationId` (`com.creadevapps.straitcontrol`) уникален и постоянен, новый keystore создан и сохранён
- [ ] Товары `sink_barges` / `call_fleet` заведены в Play Console **нового** листинга
- [ ] Иконка 512, feature graphic 1024×500, скриншоты, описание, privacy policy — всё заново под новое имя
- [ ] Тест на реальном устройстве: онбординг, синхронизация двух телефонов, потеря/восстановление связи, реальная покупка (License testing аккаунт)

---

## Замечание по контенту

Первая версия (v1–v7, «Close The Strait!») была прямо привязана к реальной
геополитике вокруг Ормузского пролива — это и привело к блокировке в Google
Play по политике Sensitive Events. С v8 («Strait Control») тема полностью
вымышлена: абстрактная карта, вымышленные фракции без привязки к реальным
странам/флагам/конфликтам. Перед следующими правками контента всё равно стоит
сверяться с актуальными Developer Program Policies (разделы sensitive events и
user-generated content, т.к. игроки вводят свои имена) — это организационный
момент, не техническое ограничение проекта.
