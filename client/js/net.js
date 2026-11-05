/* Сеть: REST (первичная загрузка) + WebSocket (real-time синхронизация).
 * Протокол — по ТЗ §6.2:
 *   inbound  {action:"TOGGLE", state:"OPEN|CLOSED", user, country}
 *   outbound {event:"STATE_CHANGED", state, user, country}
 */
const Net = (() => {
  const cfg = window.ORMUZ_CONFIG || {};
  const base = (cfg.SERVER_URL && cfg.SERVER_URL.replace(/\/$/, "")) || location.origin;
  const wsUrl = base.replace(/^http/, "ws") + "/ws";

  let ws = null;
  let onStateCb = () => {};
  let onConnCb = () => {};
  let onActionCb = () => {};
  let onProgressCb = () => {};
  let onUnlockedCb = () => {};
  let retry = 0;
  let closedByUser = false;

  async function fetchState() {
    const r = await fetch(base + "/api/v1/state", { cache: "no-cache" });
    if (!r.ok) throw new Error("state http " + r.status);
    return r.json(); // {current_state, last_updated_by, last_country, updated_at}
  }

  function connect() {
    closedByUser = false;
    onConnCb("wait");
    try { ws = new WebSocket(wsUrl); }
    catch (e) { return scheduleReconnect(); }

    ws.onopen = () => { retry = 0; onConnCb("ok"); };
    ws.onmessage = (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.event === "STATE_CHANGED") onStateCb(msg);
      else if (msg.event === "ACTION") onActionCb(msg);
      else if (msg.event === "TAP_PROGRESS") onProgressCb(msg);
      else if (msg.event === "UNLOCKED") onUnlockedCb(msg);
    };
    ws.onclose = () => { onConnCb("bad"); if (!closedByUser) scheduleReconnect(); };
    ws.onerror = () => { try { ws.close(); } catch {} };
  }

  function scheduleReconnect() {
    retry = Math.min(retry + 1, 6);
    const delay = 500 * Math.pow(1.6, retry); // экспоненциальный бэкофф
    setTimeout(connect, delay);
  }

  function sendToggle(state, user, country) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify({ action: "TOGGLE", state, user, country }));
    return true;
  }
  function _send(obj) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(obj));
    return true;
  }
  function sendTap(user) { return _send({ action: "TAP", user }); }
  function sendAd(user) { return _send({ action: "AD", user }); }
  function sendPaid(kind, user, country, token) {
    return _send({ action: "PAID", kind, user, country, token });
  }

  return {
    fetchState, connect, sendToggle, sendTap, sendAd, sendPaid,
    onState(cb) { onStateCb = cb; },
    onConn(cb) { onConnCb = cb; },
    onAction(cb) { onActionCb = cb; },
    onProgress(cb) { onProgressCb = cb; },
    onUnlocked(cb) { onUnlockedCb = cb; },
    close() { closedByUser = true; if (ws) ws.close(); }
  };
})();
