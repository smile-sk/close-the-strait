/* Canvas-сцена: карта + баржи + траффик + флот/взрывы.
 *
 * CLOSED — баржи стенкой поперёк фарватера; траффик встаёт (по одному с каждой
 *          стороны). Если закрыто платно (sink) — баржи затоплены (wreck).
 * OPEN   — баржи на стоянке у иранского берега; танкеры/сухогрузы снуют.
 * Флот   — playFleet(): военные корабли проходят вдоль стены, мультяшные взрывы,
 *          после чего сервер переводит статус в OPEN (баржи расходятся).
 *
 * Всё привязано к КАРТЕ (нормализованные координаты 0..1 -> экран через ту же
 * cover-трансформацию, что рисует фон).
 */
const Game = (() => {
  const N = 6;
  const LERP = 0.09;

  const WALL_A = { u: 0.40, v: 0.43 };
  const WALL_B = { u: 0.70, v: 0.37 };
// Опорная точка в районе открытого пролива
  const OPEN_CENTER = { u: 0.60, v: 0.35 };

  // Позиции [dU, dV, angle] для каждой из 6 барж:
  const OPEN_SPREAD = [
    // 1. Слева вверху (вертикально у левого берега)
    [-0.20,  0.03,  2.00], 

    // 2. Слева внизу (горизонтально у мыса)
    [-0.2,  0.08,  0.5], 

    // 3. Слева у самого мыса (чуть правее второй)
    [-0.1,  0.12, 1.1], 

    // 4. Справа вверху (горизонтальная, носом влево)
    [ 0.00, 0.01, 1.40], 

    // 5. Справа у верхнего песчаного берега
    [ 0.12, 0.06,  2.30], 

    // 6. Справа внизу (вертикально у правого берега)
    [ 0.13,  0.15,  1.40], 
  ];
  const BARGE_FRAC = 0.075;

   // фарватер траффика — КРИВОЙ путь строго по воде . Точки в координатах карты (0..1).
 const PATH = [
   [0.90, 0.16], // Начало справа вверху
   [0.72, 0.16], // Движение влево по верхнему рукаву
   [0.52, 0.19], // Поворот на излучине
   [0.41, 0.28], // Выход на изгиб вниз
   [0.55, 0.44], // Центр реки 
   [0.70, 0.58], // Огибание мыса справа
   [0.56, 0.73], // Поворот в левый нижний рукав
   [0.37, 0.84], // Движение вниз-влево
   [0.13, 0.93]  // Конец слева внизу
 ];
  const LANE_SEP = 0.018;                   // разнос встречных «полос» (доля ширины карты)
  const STOP_FWD = 0.44, STOP_BWD = 0.56;   // где встают у стены (стена ~0.5 пути)
  const TRAFFIC_MAX = 5;

  const canvas = document.getElementById("map");
  const ctx = canvas.getContext("2d");

  const imgs = {};
  let W = 0, H = 0, dpr = 1;
  let barges = [];
  let traffic = [];
  let explos = [];
  let state = "CLOSED";
  let lockKind = null;                       // 'sink' -> баржи затоплены
  let ready = false;
  let last = 0, spawnTimer = 1.5;

  function loadImages() {
    const list = {
      bg: "assets/bg_strait_map.png", barge: "assets/ship_barge.png",
      wreck: "assets/barge_wreck.png", tanker: "assets/tanker.png",
      cargo: "assets/cargo.png", warship: "assets/warship.png",
      explosion: "assets/explosion.png",
    };
    const jobs = Object.entries(list).map(([k, src]) => new Promise((res) => {
      const im = new Image();
      im.onload = () => { imgs[k] = im; res(); };
      im.onerror = () => res();               // отсутствующий спрайт не ломает сцену
      im.src = src;
    }));
    return Promise.all(jobs);
  }

  function resize() {
    dpr = Math.max(1, Math.min(3, window.devicePixelRatio || 1));
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    computeTargets();
  }

  function coverRect() {
    const im = imgs.bg;
    if (!im) return { dw: W, dh: H, ox: 0, oy: 0 };
    const s = Math.max(W / im.width, H / im.height);
    const dw = im.width * s, dh = im.height * s;
    return { dw, dh, ox: (W - dw) / 2, oy: (H - dh) / 2 };
  }
  function img2scr(u, v, r) { return { x: r.ox + u * r.dw, y: r.oy + v * r.dh }; }

  // точка и касательная на ломаном пути PATH при параметре p∈[0..1];
  // off — боковое смещение (полоса), в долях ширины карты
  function lanePoint(p, off, r) {
    const n = PATH.length - 1;
    let fp = Math.max(0, Math.min(0.9999, p)) * n;
    let i = Math.floor(fp), t = fp - i;
    const a = PATH[i], b = PATH[i + 1];
    const A = img2scr(a[0], a[1], r), B = img2scr(b[0], b[1], r);
    const x = A.x + (B.x - A.x) * t, y = A.y + (B.y - A.y) * t;
    const ang = Math.atan2(B.y - A.y, B.x - A.x);
    const ox = Math.cos(ang + Math.PI / 2) * (off || 0) * r.dw;
    const oy = Math.sin(ang + Math.PI / 2) * (off || 0) * r.dw;
    return { x: x + ox, y: y + oy, ang };
  }

  function initBarges() {
    barges = [];
    for (let i = 0; i < N; i++)
      barges.push({ x: W / 2, y: H / 2, ang: Math.PI / 2, tx: 0, ty: 0, tang: 0 });
    computeTargets();
    barges.forEach(b => { b.x = b.tx; b.y = b.ty; b.ang = b.tang; });
  }

  function computeTargets() {
    if (!barges.length) return;
    const r = coverRect();
    if (state === "CLOSED") {
      const pA = img2scr(WALL_A.u, WALL_A.v, r), pB = img2scr(WALL_B.u, WALL_B.v, r);
      const ang = Math.atan2(pB.y - pA.y, pB.x - pA.x);
      for (let i = 0; i < N; i++) {
        const t = N > 1 ? i / (N - 1) : 0.5;
        barges[i].tx = pA.x + (pB.x - pA.x) * t;
        barges[i].ty = pA.y + (pB.y - pA.y) * t;
        barges[i].tang = ang;
      }
    } else {
      for (let i = 0; i < N; i++) {
        const s = OPEN_SPREAD[i % OPEN_SPREAD.length];
        const p = img2scr(OPEN_CENTER.u + s[0], OPEN_CENTER.v + s[1], r);
        barges[i].tx = p.x; barges[i].ty = p.y; barges[i].tang = s[2];
      }
    }
  }

  function setState(s) {
    state = (s === "OPEN") ? "OPEN" : "CLOSED";
    computeTargets();
  }
  function setLock(kind) { lockKind = kind || null; }   // 'sink' | 'fleet' | null

  function lerpAngle(a, b, t) {
    let d = ((b - a + Math.PI) % (2 * Math.PI)) - Math.PI;
    return a + d * t;
  }

  // --- траффик ---
  function spawnTraffic() {
    if (traffic.length >= TRAFFIC_MAX) return;
    const dir = Math.random() < 0.5 ? 1 : -1;
    const sprite = Math.random() < 0.5 ? "tanker" : "cargo";
    // встречные — по РАЗНЫМ полосам (не идут насквозь друг через друга)
    const off = dir * LANE_SEP + (Math.random() - 0.5) * 0.01;
    traffic.push({
      p: dir > 0 ? -0.05 : 1.05, dir, sprite,
      speed: 0.05 + Math.random() * 0.05, off, warship: false,
    });
  }

  function updateTraffic(dt) {
    for (const s of traffic) {
      s.p += s.dir * s.speed * dt;
      if (state === "CLOSED" && !s.warship) {           // встают у стены
        if (s.dir > 0 && s.p > STOP_FWD) s.p = STOP_FWD;
        if (s.dir < 0 && s.p < STOP_BWD) s.p = STOP_BWD;
      }
    }
    // максимум по одному ждущему с каждой стороны
    if (state === "CLOSED") {
      for (const d of [1, -1]) {
        const stop = d > 0 ? STOP_FWD : STOP_BWD;
        const waiters = traffic.filter(s => !s.warship && s.dir === d &&
          Math.abs(s.p - stop) < 0.09);
        waiters.sort((a, b) => d > 0 ? b.p - a.p : a.p - b.p);   // ближний к стене — первый
        for (let i = 1; i < waiters.length; i++) waiters[i]._dead = true;
      }
    }
    traffic = traffic.filter(s => !s._dead && s.p > -0.12 && s.p < 1.12);
  }

  function drawShip(s, r) {
    const im = imgs[s.sprite];
    const pt = lanePoint(s.p, s.off, r);
    const len = r.dw * (s.warship ? 0.10 : 0.11);
    const h = len * (im ? im.height / im.width : 0.33);
    ctx.save();
    ctx.translate(pt.x, pt.y);
    ctx.rotate(pt.ang + (s.dir < 0 ? Math.PI : 0));
    if (im) ctx.drawImage(im, -len / 2, -h / 2, len, h);
    else { ctx.fillStyle = "#556"; ctx.fillRect(-len / 2, -h / 2, len, h); }
    ctx.restore();
  }

  // --- взрывы ---
  function boom(x, y) { explos.push({ x, y, t0: performance.now() }); }
  function playFleet() {
    const r = coverRect();
    const A = img2scr(WALL_A.u, WALL_A.v, r), B = img2scr(WALL_B.u, WALL_B.v, r);
    for (let i = 0; i < N; i++) {
      const t = i / (N - 1);
      setTimeout(() => boom(A.x + (B.x - A.x) * t, A.y + (B.y - A.y) * t), 110 * i);
    }
    for (let k = 0; k < 2; k++)
      traffic.push({ p: -0.05, dir: 1, sprite: "warship", speed: 0.16,
                     off: (k ? 0.05 : -0.05), warship: true });
  }
  function drawExplos() {
    const im = imgs.explosion;
    const now = performance.now();
    for (const e of explos) {
      const age = now - e.t0, life = 650;
      if (age > life) { e._dead = true; continue; }
      const k = age / life, size = coverRect().dw * (0.06 + k * 0.10);
      ctx.save();
      ctx.globalAlpha = 1 - k;
      ctx.translate(e.x, e.y);
      if (im) ctx.drawImage(im, -size / 2, -size / 2, size, size);
      else { ctx.fillStyle = "#ff7a2a"; ctx.beginPath();
             ctx.arc(0, 0, size / 2, 0, 7); ctx.fill(); }
      ctx.restore();
    }
    explos = explos.filter(e => !e._dead);
  }

  function drawBg() {
    const im = imgs.bg;
    if (!im) { ctx.fillStyle = "#2b6e8c"; ctx.fillRect(0, 0, W, H); return; }
    const r = coverRect();
    ctx.drawImage(im, r.ox, r.oy, r.dw, r.dh);
  }

  function drawBarge(b, bargeLen) {
    const im = (lockKind === "sink" && imgs.wreck) ? imgs.wreck : imgs.barge;
    ctx.save();
    ctx.translate(b.x, b.y);
    ctx.rotate(b.ang);
    const bw = bargeLen, bh = bw * (im ? im.height / im.width : 0.375);
    if (im) ctx.drawImage(im, -bw / 2, -bh / 2, bw, bh);
    else { ctx.fillStyle = "#3a4149"; ctx.fillRect(-bw / 2, -bh / 2, bw, bh); }
    ctx.restore();
  }

  function frame(now) {
    if (!ready) return;
    const dt = last ? Math.min(0.05, (now - last) / 1000) : 0.016;
    last = now;

    spawnTimer -= dt;
    if (spawnTimer <= 0 && state === "OPEN") { spawnTraffic(); spawnTimer = 1.4 + Math.random() * 2.2; }
    else if (spawnTimer <= 0) spawnTimer = 1.0;
    updateTraffic(dt);

    for (const b of barges) {
      b.x += (b.tx - b.x) * LERP;
      b.y += (b.ty - b.y) * LERP;
      b.ang = lerpAngle(b.ang, b.tang, LERP);
    }

    const r = coverRect();
    const bargeLen = Math.max(40, r.dw * BARGE_FRAC);
    ctx.clearRect(0, 0, W, H);
    drawBg();
    for (const s of traffic) if (!s.warship) drawShip(s, r);   // танкеры/сухогрузы под баржами
    for (const b of barges) drawBarge(b, bargeLen);
    for (const s of traffic) if (s.warship) drawShip(s, r);    // военные — поверх
    drawExplos();
    requestAnimationFrame(frame);
  }

  async function start(initialState) {
    await loadImages();
    resize();
    state = (initialState === "OPEN") ? "OPEN" : "CLOSED";
    initBarges();
    ready = true;
    window.addEventListener("resize", resize);
    requestAnimationFrame(frame);
  }

  return {
    start, setState, setLock, playFleet,
    get state() { return state; },
  };
})();
