/* Точка входа: онбординг -> загрузка состояния -> сцена -> сокет + механика. */
(async function main() {
  const connEl = document.getElementById("conn");

  function connStatus(kind) {
    connEl.className = "conn " + (
      kind === "ok" ? "conn--ok" : kind === "bad" ? "conn--bad" : "conn--wait");
    connEl.textContent = I18N.t(
      kind === "ok" ? "online" : kind === "bad" ? "offline" : "connecting");
    if (kind === "ok") setTimeout(() => connEl.classList.add("conn--hide"), 1200);
    else connEl.classList.remove("conn--hide");
  }

  // 1. Профиль / онбординг
  let profile = UI.loadProfile();
  if (!profile) profile = await UI.openModal("onboarding");
  await I18N.load(profile.lang);
  UI.setSound(profile.sound !== false);
  if (profile.push !== false) Push.register(profile.lang);   // пуши только на платные действия (решает сервер)
  Billing.init();   // почистить залипшие непотреблённые покупки (Android) при запуске

  // 2. Настройки по шестерёнке
  UI.settingsButton().addEventListener("click", async () => {
    const saved = await UI.openModal("settings");
    if (saved) {
      profile = saved;
      await I18N.load(saved.lang);
      UI.setSound(saved.sound !== false);
      UI.applyState(UI.state);
      UI.setHeader(lastInfo);
      if (saved.push !== false) Push.register(saved.lang);   // (пере)регистрируем токен
    }
  });

  // 3. Первичное состояние (REST): статус + лок + прогресс
  let initial = "CLOSED";
  let lastInfo = null;
  let lockInfo = { locked: false };
  try {
    const st = await Net.fetchState();
    initial = st.current_state || "CLOSED";
    lockInfo = {
      locked: !!st.locked, lock_kind: st.lock_kind,
      taps: st.unlock_taps || 0, threshold: st.threshold,
    };
    const la = st.last_action;
    if (la && la.user) {
      lastInfo = { user: la.user, country: (la.country || "").toLowerCase(),
                   state: initial, kind: la.kind, at: la.at || st.updated_at };
    } else if (st.last_updated_by) {
      lastInfo = { user: st.last_updated_by, country: (st.last_country || "").toLowerCase(),
                   state: initial, at: st.updated_at };
    }
  } catch (e) { console.warn("REST state failed, default CLOSED", e); }

  UI.state = initial;
  UI.applyState(initial);
  UI.applyLock(lockInfo);
  document.getElementById("hdr-text").dataset.empty = lastInfo ? "0" : "1";
  UI.setHeader(lastInfo);
  await Game.start(initial);
  if (lockInfo.lock_kind) Game.setLock(lockInfo.lock_kind);
  UI.bindToggle();
  UI.bindControls();

  // 4. Исходящее: обычный тумблер
  UI.onToggle((next) => {
    UI.state = next;
    Net.sendToggle(next, profile.name, profile.country);
  });

  // 4a. Платное действие -> покупка -> ОПТИМИСТИЧНО применяем локально
  //     (как тумблер: сразу видно), затем шлём на сервер; броадкаст подтвердит.
  let lastFx = 0, lastFxKind = null;
  function actionFx(kind) {                 // звук + анимация действия (без дубля)
    const now = Date.now();
    if (now - lastFx < 1500 && lastFxKind === kind) return;
    lastFx = now; lastFxKind = kind;
    if (kind === "fleet") { Game.playFleet(); UI.playFx("fleet"); }
    else { UI.playFx("sink"); }
  }
  UI.onPaid((kind) => {
    Billing.buy(kind).then((token) => {
      if (!token) return;                       // покупка отменена
      const s = kind === "fleet" ? "OPEN" : "CLOSED";
      actionFx(kind);
      UI.state = s;
      UI.applyState(s);
      UI.applyLock({ locked: true, lock_kind: kind, taps: 0,
                     threshold: (window.ORMUZ_CONFIG || {}).UNLOCK_TAPS || 750 });
      Game.setState(s);
      Game.setLock(kind);
      lastInfo = { user: profile.name, country: (profile.country || "").toLowerCase(),
                   state: s, kind, at: Math.floor(Date.now() / 1000) };
      document.getElementById("hdr-text").dataset.empty = "0";
      UI.setHeader(lastInfo);
      Net.sendPaid(kind, profile.name, profile.country, token);   // на сервер (если ws есть)
    });
  });

  // 4b. Тап по заблокированному тумблеру -> общий счётчик разлока
  UI.onTap(() => Net.sendTap(profile.name));

  // 4c. Реклама: по кнопке или автоматически каждые AD_EVERY своих тапов
  function watchAd() {
    Ads.showRewarded().then((ok) => { if (ok) Net.sendAd(profile.name); });
  }
  UI.onAdWatch(watchAd);
  UI.onAdDue(watchAd);

  // 5. Входящие события синхронизации
  Net.onState((msg) => {
    const s = msg.state === "OPEN" ? "OPEN" : "CLOSED";
    const la = msg.last_action;
    lastInfo = la && la.user
      ? { user: la.user, country: (la.country || "").toLowerCase(), state: s, kind: la.kind,
          at: la.at || msg.at }
      : { user: msg.user, country: (msg.country || "").toLowerCase(), state: s,
          at: msg.at };
    UI.state = s;
    UI.applyState(s);
    UI.applyLock({ locked: !!msg.locked, lock_kind: msg.lock_kind,
                   taps: msg.taps || 0, threshold: msg.threshold });
    Game.setState(s);
    Game.setLock(msg.locked ? msg.lock_kind : null);
    document.getElementById("hdr-text").dataset.empty = "0";
    UI.setHeader(lastInfo);
  });

  // 5a. Платное действие кем-то: спектакль + строка события
  Net.onAction((msg) => {
    const s = msg.state === "OPEN" ? "OPEN" : "CLOSED";
    if (msg.kind === "fleet" || msg.kind === "sink") actionFx(msg.kind);  // спектакль + звук
    lastInfo = { user: msg.user, country: (msg.country || "").toLowerCase(),
                 state: s, kind: msg.kind, at: msg.at };
    document.getElementById("hdr-text").dataset.empty = "0";
    UI.setHeader(lastInfo);
    // STATE_CHANGED следом обновит статус/лок/сцену
  });

  // 5b. Прогресс разлока
  Net.onProgress((msg) => UI.setProgress(msg.taps, msg.threshold));

  // 5c. Разлок завершён
  Net.onUnlocked(() => {
    UI.applyLock({ locked: false });
    Game.setLock(null);
  });

  Net.onConn(connStatus);
  Net.connect();

  // 6. Service worker (офлайн-кэш ассетов)
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  }
})();
