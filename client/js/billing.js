/* Покупки.
 *   • Браузер/PWA — мок (реального биллинга в вебе нет): подтверждение диалогом.
 *   • Android-приложение (Capacitor) — Google Play Billing через плагин
 *     @capgo/native-purchases (проверено на 8.6.5).
 *
 * Товары sink/fleet — РАСХОДУЕМЫЕ (покупаются многократно). В Google Play нет
 * галочки «consumable» в консоли: расходуемость задаётся ТОЛЬКО кодом — покупку
 * надо «потребить» (consume) после выдачи, иначе следующая покупка падает с
 * «Вы уже владеете этим товаром».
 *
 * ВАЖНО про токен: на Android плагин часто кладёт значение в tx.transactionId,
 * а tx.purchaseToken оставляет undefined (на Android transactionId — это тот же
 * purchase token). Поэтому и на сервер, и в consume уходит РАЗРЕШЁННЫЙ токен
 * (purchaseToken || transactionId), а не голый tx.purchaseToken.
 *
 * buy(kind) -> Promise<purchaseToken|null>.
 */
const Billing = (() => {
  const cfg = window.ORMUZ_CONFIG || {};
  const PRODUCTS = cfg.PRODUCTS || { sink: "sink_barges", fleet: "call_fleet" };

  function platform() {
    const C = window.Capacitor;
    return (C && C.getPlatform) ? C.getPlatform() : "web";
  }
  function isNativeApp() {
    const C = window.Capacitor;
    if (!C) return false;
    if (typeof C.isNativePlatform === "function") return C.isNativePlatform();
    if (typeof C.getPlatform === "function") return C.getPlatform() !== "web";
    return !!C.isNative;
  }
  const MOCK = (cfg.BILLING_MOCK === true) || !isNativeApp();

  function np() {
    const C = window.Capacitor;
    return (C && C.Plugins && C.Plugins.NativePurchases) || window.NativePurchases || null;
  }

  // разрешённый токен транзакции/покупки (см. коммент выше)
  function tokenOf(t) {
    return t ? (t.purchaseToken || t.transactionId || null) : null;
  }

  // потребить покупку (Android) — чтобы товар можно было купить снова.
  // Передаём оба возможных ключа: у разных версий плагина он называется
  // purchaseToken либо transactionId.
  async function consumeToken(NP, token) {
    if (!token || platform() !== "android") return;
    if (NP.consumePurchase) {
      try {
        await NP.consumePurchase({ purchaseToken: token, transactionId: token });
        return;
      } catch (e) {
        console.warn("Billing: consumePurchase не удалось:", (e && e.message) || e);
      }
    }
    // запасной путь (совсем старые версии без consume): хотя бы подтвердить
    if (NP.acknowledgePurchase) {
      try {
        await NP.acknowledgePurchase({ purchaseToken: token, transactionId: token });
      } catch (e) {
        console.warn("Billing: acknowledgePurchase не удалось:", (e && e.message) || e);
      }
    }
  }

  // вернуть токен + потребить покупку
  async function finish(NP, tx) {
    const token = tokenOf(tx);
    await consumeToken(NP, token);
    return token;
  }

  // найти ранее купленный, но не потреблённый товар (для восстановления)
  async function findOwned(NP, productId) {
    if (!NP.getPurchases) return null;
    try {
      const r = await NP.getPurchases({ productType: "inapp" });
      const list = (r && r.purchases) || [];
      return list.find(
        (p) => p && (p.productIdentifier === productId || p.productId === productId)
      ) || null;
    } catch (e) {
      console.warn("Billing: getPurchases не удалось:", (e && e.message) || e);
      return null;
    }
  }

  // ПОТРЕБИТЬ ВСЕ незакрытые покупки. Расходуемый товар в Google Play остаётся
  // «в собственности», пока его явно не consume — из-за этого вылезает «Вы уже
  // владеете этим товаром». Чистим при старте и перед каждой покупкой, чтобы
  // ничего не могло залипнуть между сессиями/сборками.
  async function consumeAll(NP) {
    NP = NP || np();
    if (!NP || platform() !== "android" || !NP.getPurchases) return;
    try {
      const r = await NP.getPurchases({ productType: "inapp" });
      const list = (r && r.purchases) || [];
      for (const p of list) {
        const t = tokenOf(p);
        if (t) await consumeToken(NP, t);
      }
      if (list.length) console.warn("Billing: очищено незакрытых покупок:", list.length);
    } catch (e) {
      console.warn("Billing: consumeAll не удалось:", (e && e.message) || e);
    }
  }

  // вызвать один раз при запуске приложения (main.js)
  async function init() {
    if (MOCK) return;
    await consumeAll();
  }

  async function buy(kind) {
    const productId = PRODUCTS[kind];
    if (!productId) return null;

    if (cfg.FREE_ACTIONS_TEST) return "FREE-TEST-" + Date.now();

    if (MOCK) {
      const ok = window.confirm(
        `[DEMO] Purchase «${productId}» for ${cfg.PRICE_LABEL || ""}.\n` +
        `The APK will open Google Play here. Confirm?`);
      return ok ? "MOCK-" + Date.now() : null;
    }

    // ---- НАТИВ: @capgo/native-purchases (Google Play Billing) ----
    const NP = np();
    if (!NP) {
      console.warn("Billing: плагин @capgo/native-purchases не установлен (npm i + cap sync)");
      return null;
    }
    try {
      const sup = await NP.isBillingSupported();
      if (sup && sup.isBillingSupported === false) {
        console.warn("Billing: покупки не поддерживаются на этом устройстве");
        return null;
      }

      await consumeAll(NP);   // на всякий случай чистим залипшее ПЕРЕД покупкой

      let tx;
      try {
        tx = await NP.purchaseProduct({
          productIdentifier: productId,
          productType: "inapp",              // PURCHASE_TYPE.INAPP
          quantity: 1,
          autoAcknowledgePurchases: false,   // финализируем сами через consume
        });
      } catch (e) {
        const msg = ((e && e.message) || String(e)).toLowerCase();
        if (/cancel/.test(msg)) return null;                 // пользователь закрыл окно
        // «Вы уже владеете этим товаром» — прошлая покупка не была потреблена.
        if (/own|already|code\s*7|responsecode\s*7/.test(msg)) {
          const owned = await findOwned(NP, productId);
          if (owned) {
            console.warn("Billing: восстанавливаю непотреблённую покупку", productId);
            return await finish(NP, owned);                  // засчитать и потребить
          }
        }
        throw e;
      }
      return await finish(NP, tx);
    } catch (e) {
      console.error("Billing error:", (e && e.message) || e);
      return null;
    }
  }

  return { buy, init };
})();
