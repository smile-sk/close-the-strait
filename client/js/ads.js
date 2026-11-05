/* Rewarded-реклама.
 *   • Закрытый тест (сейчас): рекламы нет, кнопка «+{bonus} тапов» засчитывается
 *     бесплатно — включено флагом AD_FREE_REWARD в config.js.
 *   • Браузер/PWA без флага — мок с подтверждением.
 *   • Позже, с реальной рекламой: поставь AD_FREE_REWARD:false и реализуй ветку
 *     NATIVE (плагин @capacitor-community/admob): prepareRewardedVideo ->
 *     showRewardedVideo, верни true ТОЛЬКО по событию Rewarded (награда выдана).
 *
 * showRewarded() -> Promise<boolean> (true = награду засчитать).
 */
const Ads = (() => {
  const cfg = window.ORMUZ_CONFIG || {};
  function isNativeApp() {
    const C = window.Capacitor;
    if (!C) return false;
    if (typeof C.isNativePlatform === "function") return C.isNativePlatform();
    if (typeof C.getPlatform === "function") return C.getPlatform() !== "web";
    return !!C.isNative;
  }
  const MOCK = (cfg.BILLING_MOCK === true) || !isNativeApp();

  async function showRewarded() {
    // Бесплатный бонус без ролика (закрытый тест) ИЛИ общий тест-режим
    if (cfg.AD_FREE_REWARD || cfg.FREE_ACTIONS_TEST) return true;

    if (MOCK) {
      return window.confirm(
        `[DEMO] Просмотр рекламы за +${cfg.AD_BONUS || 75} тапов.\n` +
        `В APK здесь будет ролик AdMob. Досмотреть?`);
    }

    // ---- NATIVE (реализуй под @capacitor-community/admob) ----
    try {
      // const { AdMob, RewardAdPluginEvents } = ... // из плагина
      // await AdMob.prepareRewardedVideoAd({ adId: "ca-app-pub-.../..." });
      // const item = await AdMob.showRewardedVideoAd();
      // return !!item; // true если награда выдана (событие Rewarded)
      console.warn("Ads NATIVE не реализован — см. ads.js");
      return false;
    } catch (e) {
      console.error("Ads error:", e);
      return false;
    }
  }

  return { showRewarded };
})();
