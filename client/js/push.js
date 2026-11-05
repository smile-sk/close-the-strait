/* Пуш-уведомления. Клиент только РЕГИСТРИРУЕТ FCM-токен на сервере; КОГДА слать
 * решает сервер — и только для платных действий (потопить/флот).
 *
 * Требует нативной настройки в Android-приложении:
 *   1) Firebase-проект + google-services.json в android/app/
 *   2) npm i @capacitor/push-notifications  → npx cap sync android
 *   3) на сервере: pip install firebase-admin и ORMUZ_FCM_CRED=путь/к/serviceAccount.json
 * На вебе (без Capacitor) — тихо ничего не делает.
 */
const Push = (() => {
  const cfg = window.ORMUZ_CONFIG || {};

  async function register(lang) {
    try {
      const Cap = window.Capacitor;
      const PN = Cap && Cap.Plugins && Cap.Plugins.PushNotifications;
      if (!PN) return;                                  // веб — пропускаем
      let perm = await PN.checkPermissions();
      if (perm.receive !== "granted") perm = await PN.requestPermissions();
      if (perm.receive !== "granted") return;
      PN.addListener("registration", (t) => {
        fetch((cfg.SERVER_URL || "") + "/api/v1/push/register", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: t.value, lang })
        }).catch(() => {});
      });
      await PN.register();
    } catch (e) {
      console.warn("Push register skipped:", e);
    }
  }

  return { register };
})();
