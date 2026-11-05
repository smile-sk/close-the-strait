/* UI: профиль (localStorage), шапка, тумблер с debounce, модалки. */
const UI = (() => {
  const cfg = window.ORMUZ_CONFIG || {};
  const $ = (id) => document.getElementById(id);
  const KEY = "ormuz_profile_v1";

  let profile = null;                 // {name, country(=id флага), lang}
  let flagSel = null;                 // выбранный в модалке флаг (id)
  let state = "CLOSED";               // текущее состояние пролива
  let locked = false;                 // debounce-блокировка тумблера
  let onToggle = () => {};            // колбэк наружу (main.js -> Net.sendToggle)

  // --- механика: лок пролива / тапы / платные действия ---
  const CFG = window.ORMUZ_CONFIG || {};
  let strLocked = false, lockKind = null;
  let localTaps = 0;                  // свои тапы (для частоты рекламы)
  const adEvery = CFG.AD_EVERY || 150;
  let onPaid = () => {}, onTap = () => {}, onAdWatch = () => {}, onAdDue = () => {};

  /* ---------- звук переключения (assets/sfx/*.wav, заменяй своими) ---------- */
  const SFX = {
    OPEN:   new Audio("assets/sfx/switch_on.wav"),
    CLOSED: new Audio("assets/sfx/switch_off.wav"),
    sink:   new Audio("assets/sfx/sink.wav"),     // бульканье тонущих барж
    fleet:  new Audio("assets/sfx/fleet.wav"),    // очередь взрывов
    tap:    new Audio("assets/sfx/tap.wav"),      // клик по неактивной кнопке
  };
  SFX.OPEN.volume = SFX.CLOSED.volume = 0.6;
  SFX.sink.volume = SFX.fleet.volume = 0.45;      // потише, но слышно
  SFX.tap.volume = 0.4;
  Object.values(SFX).forEach(a => { a.preload = "auto"; });
  let soundOn = true;                 // можно выключить (см. setSound)
  function playSfx(s) {
    if (!soundOn) return;
    const a = SFX[s];
    if (!a) return;
    try { a.currentTime = 0; const p = a.play(); if (p && p.catch) p.catch(() => {}); }
    catch (e) { /* автоплей до жеста — игнорируем */ }
  }
  function setSound(on) { soundOn = !!on; }     // только звуковые эффекты
  let musicOn = true;                            // фоновая музыка (отдельно от SFX)
  function setMusic(on) {
    musicOn = !!on;
    if (musicOn) playWanted(); else stopMusic();
  }

  /* ---------- фоновая музыка (по состоянию, зациклено) ---------- */
  const MEXT = (cfg.MUSIC_EXT || "mp3");
  const MVOL = (cfg.MUSIC_VOLUME != null ? cfg.MUSIC_VOLUME : 0.35);
  const MUSIC = {};
  ["dune_warpath", "desert_veil", "blue_grid_horizon", "iron_resolve"].forEach((nm) => {
    const a = new Audio(`assets/sfx/${nm}.${MEXT}`);
    a.loop = true; a.preload = "auto"; a.volume = MVOL;
    try { a.load(); } catch (e) {}                 // качаем заранее (пока показывается лого)
    MUSIC[nm] = a;
  });
  let musicName = null;
  let musicPrimed = false;                          // хоть раз успешно заиграло

  function musicFor() {                             // платный лок важнее статуса
    if (strLocked && lockKind === "sink") return "desert_veil";
    if (strLocked && lockKind === "fleet") return "iron_resolve";
    return state === "OPEN" ? "blue_grid_horizon" : "dune_warpath";
  }
  function stopMusic() {
    Object.values(MUSIC).forEach(a => { try { a.pause(); } catch (e) {} });
  }
  // играть нужный трек ПРЯМО СЕЙЧАС (вызывать внутри жеста пользователя)
  function playWanted() {
    if (!musicOn) return;
    const want = musicFor();
    if (musicName && musicName !== want && MUSIC[musicName]) {
      try { MUSIC[musicName].pause(); } catch (e) {}
    }
    musicName = want;
    const a = MUSIC[want];
    if (!a) return;
    try {
      const p = a.play();
      if (p && p.then) p.then(() => { musicPrimed = true; }).catch(() => {});
      else musicPrimed = true;
    } catch (e) {}
  }
  // вызывается при смене состояния; до первого успешного старта только запоминает трек
  function updateMusic(force) {
    const want = musicFor();
    if (!musicOn || !musicPrimed) { musicName = want; return; }
    if (!force && want === musicName && MUSIC[want] && !MUSIC[want].paused) return;
    playWanted();
  }
  // на ЛЮБОМ жесте: если музыка должна играть, но не играет — стартуем (не сдаёмся)
  function onGesture() {
    if (musicOn) {
      const a = MUSIC[musicFor()];
      if (a && a.paused) playWanted();
    }
  }
  document.addEventListener("pointerdown", onGesture);
  document.addEventListener("touchstart", onGesture);
  document.addEventListener("keydown", onGesture);
  document.addEventListener("click", onGesture);

  // Пауза/резюм музыки при сворачивании.
  // В Android WebView document.hidden/visibilitychange НЕНАДЁЖНЫ: системные
  // события (шторка уведомлений, системный диалог, реальное сворачивание)
  // иногда не транслируются в веб-API видимости корректно, а порой дают
  // ложное "снова видимо", пока приложение всё ещё в фоне — из-за этого
  // музыка могла сама включаться в фоне. Поэтому в приложении (Capacitor)
  // используем НАТИВНОЕ событие жизненного цикла App.appStateChange
  // (дергается напрямую из onPause/onResume Android-активности, точное).
  // В браузере/PWA плагина нет — там остаётся document.hidden, там он
  // работает штатно, это единственный доступный сигнал.
  let usingNativeAppState = false;
  (function wireAppLifecycle() {
    const C = window.Capacitor;
    const AppPlugin = C && C.Plugins && C.Plugins.App;
    if (AppPlugin && AppPlugin.addListener) {
      usingNativeAppState = true;
      AppPlugin.addListener("appStateChange", ({ isActive }) => {
        if (!isActive) stopMusic();
        else if (musicOn && musicPrimed) playWanted();
      });
    }
  })();
  document.addEventListener("visibilitychange", () => {
    if (usingNativeAppState) return;   // в приложении это делает App.appStateChange
    if (document.hidden) stopMusic();
    else if (musicOn && musicPrimed) playWanted();
  });


  /* ---------- профиль ---------- */
  function loadProfile() {
    try { profile = JSON.parse(localStorage.getItem(KEY)); } catch { profile = null; }
    musicOn = profile ? profile.music !== false : true;    // по умолчанию вкл
    return profile;
  }
  function saveProfile(p) {
    profile = p; localStorage.setItem(KEY, JSON.stringify(p));
  }

  /* ---------- шапка ---------- */
  function statusText(s) {
    return s === "OPEN" ? I18N.t("status_open") : I18N.t("status_closed");
  }
  // unix-секунды -> "23:05" (24ч, без секунд)
  function fmtTime(ts) {
    if (!ts) return "";
    const d = new Date(Number(ts) * 1000);
    if (isNaN(d.getTime())) return "";
    const h = String(d.getHours()).padStart(2, "0");
    const m = String(d.getMinutes()).padStart(2, "0");
    return `${h}:${m}`;
  }
  function setHeader(info) {
    // info: {user, country, state, at} или null (никто ещё не ходил)
    if (!info || !info.user) {
      $("hdr-flag").src = profile ? `assets/flags/${profile.country}.png` : "";
      $("hdr-text").textContent = I18N.t("nobody_yet");
      return;
    }
    $("hdr-flag").src = `assets/flags/${info.country}.png`;
    let txt;
    if (info.kind === "sink") txt = I18N.t("action_sink", { name: info.user });
    else if (info.kind === "fleet") txt = I18N.t("action_fleet", { name: info.user });
    else txt = I18N.t("last_action", {
      name: info.user, time: fmtTime(info.at), status: statusText(info.state)
    });
    $("hdr-text").textContent = txt;
  }

  /* ---------- тумблер ---------- */
  function applyState(s) {
    state = s;
    document.body.classList.toggle("state-open", s === "OPEN");
    document.body.classList.toggle("state-closed", s === "CLOSED");
    const img = $("toggle-img");
    if (img) img.src = (s === "OPEN")
      ? "assets/switch_toggle_open.png"
      : "assets/switch_toggle_close.png";
    $("status-top").textContent = statusText(s);
    $("toggle").classList.toggle("locked", strLocked);
    refreshPaid();
    updateMusic();
  }

  // Контекстная плашка платного действия (одна за раз):
  //   OPEN   -> «Потопить баржи» (sink, закрывает)  — показываем act-sink
  //   CLOSED -> «Позвать флот»   (fleet, открывает) — показываем act-fleet
  function refreshPaid() {
    const sl = $("act-sink-label"), fl = $("act-fleet-label");
    if (sl) sl.textContent = I18N.t("btn_sink");
    if (fl) fl.textContent = I18N.t("btn_fleet");
    const showSink = state === "OPEN";               // OPEN -> sink(лево), CLOSED -> fleet(право)
    const s = $("act-sink"), f = $("act-fleet");
    if (s) s.classList.toggle("act-hidden", !showSink);
    if (f) f.classList.toggle("act-hidden", showSink);
  }

  function applyLock(info) {
    strLocked = !!(info && info.locked);
    lockKind = strLocked ? (info.lock_kind || null) : null;
    $("toggle").classList.toggle("locked", strLocked);
    $("unlock").classList.toggle("hidden", !strLocked);
    $("watch-ad").classList.toggle("hidden", !strLocked);
    if (strLocked) {
      $("unlock-hint").textContent = I18N.t("locked_hint");
      $("watch-ad").textContent = I18N.t("watch_ad", { bonus: CFG.AD_BONUS || 75 });
      setProgress(info.taps || 0, info.threshold || CFG.UNLOCK_TAPS || 750);
    }
    refreshPaid();                                   // подтянуть сторону оверлея
    if (Game && Game.setLock) Game.setLock(strLocked ? lockKind : null);
    updateMusic();
  }

  function setProgress(taps, threshold) {
    const pct = Math.max(0, Math.min(100, Math.round(taps / threshold * 100)));
    $("unlock-fill").style.width = pct + "%";
    $("unlock-count").textContent = taps + " / " + threshold;
  }

  function bindControls() {
    const fire = (kind) => { if (profile) onPaid(kind); };
    $("act-sink").addEventListener("click", () => fire("sink"));
    $("act-fleet").addEventListener("click", () => fire("fleet"));
    $("watch-ad").addEventListener("click", () => { if (profile) onAdWatch(); });
  }
  function bindToggle() {
    $("toggle").addEventListener("click", () => {
      if (!profile) return;
      if (strLocked) {                       // заперто -> тап в общий счётчик разлока
        playSfx("tap");
        onTap();
        localTaps++;
        if (adEvery > 0 && localTaps % adEvery === 0) onAdDue();
        return;
      }
      if (locked) return;                    // debounce обычного тумблера
      locked = true;
      $("toggle").setAttribute("disabled", "");
      const next = state === "OPEN" ? "CLOSED" : "OPEN";
      playSfx(next);
      applyState(next);
      Game.setState(next);
      onToggle(next);
      setTimeout(() => {                      // debounce 500 мс
        locked = false;
        $("toggle").removeAttribute("disabled");
      }, 500);
    });
  }

  /* ---------- модалка ---------- */
  function fillSelect(sel, items, val) {
    sel.innerHTML = "";
    for (const it of items) {
      const o = document.createElement("option");
      o.value = it.value; o.textContent = it.label;
      if (it.value === val) o.selected = true;
      sel.appendChild(o);
    }
  }
  // Выпадающий список «Выбор флага»: кнопка с текущим флагом + меню.
  // items: [{id, key}] (key — ключ локали с названием), val — выбранный id.
  function fillFlagSelect(sel, items, val) {
    sel.innerHTML = "";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "flag-select-btn";
    const img = document.createElement("img");
    img.alt = "";
    const name = document.createElement("span");
    name.className = "flag-select-name";
    const caret = document.createElement("span");
    caret.className = "flag-select-caret";
    caret.textContent = "\u25be";
    btn.appendChild(img); btn.appendChild(name); btn.appendChild(caret);

    const menu = document.createElement("div");
    menu.className = "flag-menu hidden";

    function pick(id) {
      flagSel = id;
      const it = items.find(x => x.id === id);
      img.src = `assets/flags/${id}.png`;
      name.textContent = it ? I18N.t(it.key) : "";
      menu.querySelectorAll(".flag-opt").forEach(x =>
        x.classList.toggle("sel", x.dataset.id === id));
      closeMenu();
    }
    function closeMenu() {
      menu.classList.add("hidden");
      btn.classList.remove("open");
    }

    for (const it of items) {
      const o = document.createElement("button");
      o.type = "button";
      o.className = "flag-opt" + (it.id === val ? " sel" : "");
      o.dataset.id = it.id;
      const oi = document.createElement("img");
      oi.src = `assets/flags/${it.id}.png`;
      oi.alt = "";
      const on = document.createElement("span");
      on.className = "flag-name";
      on.textContent = I18N.t(it.key);
      o.appendChild(oi); o.appendChild(on);
      o.addEventListener("click", () => pick(it.id));
      menu.appendChild(o);
    }

    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const willOpen = menu.classList.contains("hidden");
      document.querySelectorAll(".flag-menu").forEach(m => {
        if (m !== menu) m.classList.add("hidden");
      });
      if (willOpen) {
        menu.classList.remove("hidden");
        btn.classList.add("open");
      } else {
        closeMenu();
      }
    });

    sel.appendChild(btn); sel.appendChild(menu);

    // начальный выбор: val или первый флаг
    const init = items.find(x => x.id === val) || items[0];
    if (init) {
      flagSel = init.id;
      img.src = `assets/flags/${init.id}.png`;
      name.textContent = I18N.t(init.key);
    }
  }

  // клик мимо дропдауна — закрыть меню
  document.addEventListener("pointerdown", (e) => {
    const sel = document.getElementById("f-flag");
    if (!sel || sel.contains(e.target)) return;
    const menu = sel.querySelector(".flag-menu");
    const btn = sel.querySelector(".flag-select-btn");
    if (menu && !menu.classList.contains("hidden")) {
      menu.classList.add("hidden");
      if (btn) btn.classList.remove("open");
    }
  });

  function validateName(v) {
    if (v.length < 2 || v.length > 16) return "err_name_len";
    if (!/^[\p{L}\p{N} _-]+$/u.test(v)) return "err_name_chars";
    return null;
  }

  async function openModal(mode) {   // mode: "onboarding" | "settings"
    // язык модалки: текущий профиль или дефолт
    const curLang = (profile && profile.lang) || I18N.lang || "en";
    await I18N.load(curLang);

    // тексты окна «Как играть» (заголовок кнопки + содержимое отдельного окна)
    function fillHelpTexts() {
      $("help-open").textContent = I18N.t("help_title");
      $("help-modal-title").textContent = I18N.t("help_title");
      $("help-toggle").textContent = I18N.t("help_toggle");
      $("help-actions").textContent = I18N.t("help_actions");
      $("help-lock").textContent = I18N.t("help_lock");
      $("help-ok").textContent = I18N.t("btn_ok");
    }

    $("modal-title").textContent =
      I18N.t(mode === "settings" ? "settings_title" : "onboarding_title");
    $("lbl-lang").textContent = I18N.t("label_language");
    $("lbl-name").textContent = I18N.t("label_username");
    $("lbl-flag").textContent = I18N.t("label_flag");
    $("lbl-music").textContent = I18N.t("label_music");
    $("lbl-sound").textContent = I18N.t("label_sound");
    if ($("lbl-push")) $("lbl-push").textContent = I18N.t("label_push");
    $("f-name").placeholder = I18N.t("placeholder_username");
    $("btn-save").textContent = I18N.t(mode === "settings" ? "btn_save" : "btn_start");
    $("btn-cancel").textContent = I18N.t("btn_cancel");
    $("btn-cancel").classList.toggle("hidden", mode !== "settings");
    $("btn-reset").textContent = I18N.t("btn_reset");
    $("btn-reset").classList.toggle("hidden", mode !== "settings");

    // «Как играть» — кнопка только в настройках; открывает отдельное окно
    $("help-open").classList.toggle("hidden", mode !== "settings");
    fillHelpTexts();

    fillSelect($("f-lang"),
      cfg.LANGS.map(l => ({ value: l.code, label: l.label })), curLang);
    flagSel = profile ? profile.country
                      : ((cfg.FLAGS && cfg.FLAGS[0]) ? cfg.FLAGS[0].id : "");
    fillFlagSelect($("f-flag"),
      (cfg.FLAGS || []).map(f => ({ id: f.id, key: f.name })), flagSel);
    $("f-name").value = profile ? profile.name : "";
    $("f-music").checked = profile ? profile.music !== false : true;   // по умолчанию вкл
    $("f-sound").checked = profile ? profile.sound !== false : true;   // по умолчанию вкл
    if ($("f-push")) $("f-push").checked = profile ? profile.push !== false : true;
    $("name-err").textContent = "";

    // живая смена языка прямо в модалке
    $("f-lang").onchange = async () => {
      await I18N.load($("f-lang").value);
      $("modal-title").textContent =
        I18N.t(mode === "settings" ? "settings_title" : "onboarding_title");
      $("lbl-lang").textContent = I18N.t("label_language");
      $("lbl-name").textContent = I18N.t("label_username");
      $("lbl-flag").textContent = I18N.t("label_flag");
      $("lbl-music").textContent = I18N.t("label_music");
      $("lbl-sound").textContent = I18N.t("label_sound");
      if ($("lbl-push")) $("lbl-push").textContent = I18N.t("label_push");
      $("f-name").placeholder = I18N.t("placeholder_username");
      $("btn-save").textContent = I18N.t(mode === "settings" ? "btn_save" : "btn_start");
      $("btn-cancel").textContent = I18N.t("btn_cancel");
      fillFlagSelect($("f-flag"),
        (cfg.FLAGS || []).map(f => ({ id: f.id, key: f.name })), flagSel);
      fillHelpTexts();
    };

    return new Promise((resolve) => {
      $("modal").classList.remove("hidden");
      const close = (result) => {
        $("modal").classList.add("hidden");
        $("help-modal").classList.add("hidden");
        $("btn-save").onclick = null; $("btn-cancel").onclick = null;
        $("btn-reset").onclick = null;
        $("help-open").onclick = null; $("help-ok").onclick = null;
        $("help-modal").onclick = null;
        resolve(result);
      };
      // отдельное окно подсказки (тот же фон, кнопка ОК; фон настроек не тянется)
      $("help-open").onclick = () => { fillHelpTexts(); $("help-modal").classList.remove("hidden"); };
      $("help-ok").onclick = () => $("help-modal").classList.add("hidden");
      $("help-modal").onclick = (e) => {
        if (e.target === $("help-modal")) $("help-modal").classList.add("hidden");
      };
      $("btn-reset").onclick = () => {
        // сменить профиль: стереть и открыть онбординг заново (как при первом входе)
        try { localStorage.removeItem(KEY); } catch (e) {}
        profile = null;
        close(null);
        openModal("onboarding");
      };
      $("btn-save").onclick = () => {
        const name = $("f-name").value.trim();
        const err = validateName(name);
        if (err) { $("name-err").textContent = I18N.t(err); return; }
        const p = {
          name, country: flagSel || ((cfg.FLAGS && cfg.FLAGS[0]) ? cfg.FLAGS[0].id : ""),
          lang: $("f-lang").value,
          music: $("f-music").checked,
          sound: $("f-sound").checked,
          push: $("f-push") ? $("f-push").checked : (profile ? profile.push !== false : true),
        };
        saveProfile(p);
        setSound(p.sound);
        setMusic(p.music);
        applyLangToChrome();
        close(p);
      };
      $("btn-cancel").onclick = () => {
        // вернуть язык профиля, если менялся, но не сохранили
        if (profile) I18N.load(profile.lang).then(applyLangToChrome);
        close(null);
      };
    });
  }

  /* обновляет статичные строки вне модалки (лейбл тумблера и шапку) */
  function applyLangToChrome() {
    applyState(state);
    if (strLocked) {
      $("unlock-hint").textContent = I18N.t("locked_hint");
      $("watch-ad").textContent = I18N.t("watch_ad", { bonus: CFG.AD_BONUS || 75 });
    }
    // шапку перерисует main.js через setHeader при следующем событии;
    // здесь обновим хотя бы «nobody_yet», если ходов ещё не было
    if ($("hdr-text").dataset.empty === "1") setHeader(null);
  }

  return {
    loadProfile, saveProfile, get profile() { return profile; },
    setHeader, applyState, bindToggle, bindControls, openModal, applyLangToChrome,
    setSound, setMusic, applyLock, setProgress, refreshPaid,
    playFx(name) { playSfx(name); },
    onToggle(cb) { onToggle = cb; },
    onPaid(cb) { onPaid = cb; },
    onTap(cb) { onTap = cb; },
    onAdWatch(cb) { onAdWatch = cb; },
    onAdDue(cb) { onAdDue = cb; },
    get state() { return state; }, set state(v) { state = v; },
    get locked() { return strLocked; },
    settingsButton() { return document.getElementById("btn-settings"); }
  };
})();
