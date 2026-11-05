#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сервер игры «Ормузский пролив» — БЕЗ внешних зависимостей (только stdlib).

Делает три вещи:
  1) отдаёт статику клиента (../client)      -> открывай http://localhost:8000
  2) REST:  GET /api/v1/state                -> текущее состояние пролива
  3) WebSocket /ws                           -> real-time синхронизация

Протокол сокета (ТЗ §6.2):
  inbound  {"action":"TOGGLE","state":"OPEN|CLOSED","user":"...","country":"UA"}
           {"action":"PAID","kind":"sink|fleet","user":"...","country":"..","token":".."}
           {"action":"TAP","user":"..."}   {"action":"AD","user":"..."}
  outbound {"event":"STATE_CHANGED", state,user,country, locked,lock_kind,taps,threshold,...}
           {"event":"ACTION", kind,user,country,state,locked_until}
           {"event":"TAP_PROGRESS", taps,threshold,ad_every}
           {"event":"UNLOCKED", state}

Запуск:   python3 server/server.py
Опции:    HOST/PORT/CLIENT_DIR/STATE_FILE через переменные окружения.

Прод на Lubuntu: держи за nginx (TLS -> wss). См. README.
"""

import base64
import hashlib
import json
import os
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("ORMUZ_HOST", "0.0.0.0")
PORT = int(os.environ.get("ORMUZ_PORT", "8123"))
CLIENT_DIR = os.path.abspath(os.environ.get(
    "ORMUZ_CLIENT_DIR", os.path.join(os.path.dirname(__file__), "..", "client")))
STATE_FILE = os.path.abspath(os.environ.get(
    "ORMUZ_STATE_FILE", os.path.join(os.path.dirname(__file__), "state.json")))

# --- механика платных действий и бесплатного разлока (правится через env) ---
LOCK_SECONDS = int(os.environ.get("ORMUZ_LOCK_SECONDS", str(12 * 3600)))  # время лока
UNLOCK_TAPS = int(os.environ.get("ORMUZ_UNLOCK_TAPS", "750"))             # порог разлока
AD_EVERY_TAPS = int(os.environ.get("ORMUZ_AD_EVERY", "150"))             # реклама каждые N
AD_BONUS_TAPS = int(os.environ.get("ORMUZ_AD_BONUS", "75"))             # бонус за рекламу

# --- пуш-уведомления (ТОЛЬКО на платные действия). Реальная отправка требует
# Firebase: pip install firebase-admin + сервис-аккаунт в ORMUZ_FCM_CRED.
# Без настройки — тихо пропускается (лог "push skipped"). ---
PUSH_FILE = os.path.abspath(os.environ.get(
    "ORMUZ_PUSH_FILE", os.path.join(os.path.dirname(__file__), "push_tokens.json")))
FCM_CRED = os.environ.get("ORMUZ_FCM_CRED", "")   # путь к serviceAccount.json
_push_lock = threading.Lock()
_fcm_app = None


def _load_push():
    try:
        with open(PUSH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)          # {token: lang}
    except Exception:
        return {}


def _save_push(d):
    try:
        tmp = PUSH_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, PUSH_FILE)
    except Exception:
        pass


PUSH_TOKENS = _load_push()


def register_push(token, lang):
    if not token:
        return
    with _push_lock:
        PUSH_TOKENS[token] = (lang or "en")[:5]
        _save_push(PUSH_TOKENS)


def _t(lang, key):
    """Строка перевода из client/assets/lang/<lang>.json (для текста пуша)."""
    for code in (lang, "en"):
        try:
            p = os.path.join(CLIENT_DIR, "assets", "lang", f"{code}.json")
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            if key in d:
                return d[key]
        except Exception:
            pass
    return key


def _fcm_ready():
    global _fcm_app
    if not FCM_CRED:
        return False
    if _fcm_app:
        return True
    try:
        import firebase_admin
        from firebase_admin import credentials
        _fcm_app = firebase_admin.initialize_app(credentials.Certificate(FCM_CRED))
        return True
    except Exception as e:
        print("[push] firebase init failed:", e)
        return False


def send_paid_push(kind, actor):
    """Локализованный пуш всем зарегистрированным устройствам. Только для PAID."""
    with _push_lock:
        tokens = dict(PUSH_TOKENS)
    if not tokens:
        return
    if not _fcm_ready():
        print(f"[push] skipped ({len(tokens)} tokens) — FCM не настроен (ORMUZ_FCM_CRED)")
        return
    try:
        from firebase_admin import messaging
    except Exception:
        return
    key = "action_fleet" if kind == "fleet" else "action_sink"
    sent = 0
    for token, lang in tokens.items():
        title = _t(lang, "app_title")
        body = _t(lang, key).replace("{name}", actor or "—")
        try:
            messaging.send(messaging.Message(
                token=token,
                notification=messaging.Notification(title=title, body=body)))
            sent += 1
        except Exception as e:
            print("[push] send failed:", e)
    print(f"[push] sent {sent}/{len(tokens)} ({kind})")



def _port_in_use(host, port):
    """Активная проверка: реально ли кто-то уже слушает этот порт.
    Нужна из-за Windows SO_REUSEADDR, где bind на занятый порт молча
    проходит, а отвечает чужой процесс."""
    probe = "127.0.0.1" if host in ("0.0.0.0", "") else host
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        return s.connect_ex((probe, port)) == 0
    finally:
        s.close()


def _find_free_port(host, start, tries=50):
    p = start
    for _ in range(tries):
        if not _port_in_use(host, p):
            return p
        p += 1
    return start

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".ico": "image/x-icon",
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg",
}

# ---------------------------------------------------------------------------
# Состояние + список подключённых сокетов
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()
_clients = []                 # список dict: {"sock":socket, "lock":Lock}
_clients_lock = threading.Lock()


def load_state():
    default = {"current_state": "CLOSED", "last_updated_by": None,
               "last_country": None, "updated_at": int(time.time()),
               "locked_until": 0, "lock_kind": None, "unlock_taps": 0,
               "last_action": None}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in default.items():
                data.setdefault(k, v)
            return data
    except Exception:
        return default


def save_state(st):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


STATE = load_state()


def _lock_active():
    return STATE.get("locked_until", 0) > time.time()


def _public_snapshot():
    """Снимок состояния для WS-события STATE_CHANGED (совместим со старым
    клиентом: state/user/country на месте, остальное — доп. поля)."""
    with _state_lock:
        st = dict(STATE)
    active = st.get("locked_until", 0) > time.time()
    return {
        "event": "STATE_CHANGED",
        "state": st["current_state"],
        "user": st["last_updated_by"],
        "country": st["last_country"],
        "locked": active,
        "lock_kind": st["lock_kind"] if active else None,
        "locked_until": st["locked_until"] if active else 0,
        "taps": st.get("unlock_taps", 0),
        "threshold": UNLOCK_TAPS,
        "ad_every": AD_EVERY_TAPS,
        "last_action": st.get("last_action"),
        "at": st.get("updated_at") or int(time.time()),
    }

# ---------------------------------------------------------------------------
# WebSocket: кодирование/декодирование кадров
# ---------------------------------------------------------------------------
def ws_encode(payload: bytes, opcode: int = 0x1) -> bytes:
    header = bytes([0x80 | opcode])
    n = len(payload)
    if n < 126:
        header += bytes([n])
    elif n < 65536:
        header += bytes([126]) + struct.pack(">H", n)
    else:
        header += bytes([127]) + struct.pack(">Q", n)
    return header + payload


def _recv_exact(rfile, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = rfile.read(n - len(buf))
        if not chunk:
            raise ConnectionError("socket closed")
        buf += chunk
    return buf


def ws_read_frame(rfile):
    """Читает один кадр от клиента (клиент всегда маскирует). Возвращает
    (opcode, payload_bytes)."""
    b1, b2 = _recv_exact(rfile, 2)
    opcode = b1 & 0x0F
    masked = b2 & 0x80
    length = b2 & 0x7F
    if length == 126:
        length = struct.unpack(">H", _recv_exact(rfile, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(rfile, 8))[0]
    mask = _recv_exact(rfile, 4) if masked else b"\x00\x00\x00\x00"
    data = _recv_exact(rfile, length)
    if masked:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return opcode, data


def _send_to(client, obj):
    frame = ws_encode(json.dumps(obj, ensure_ascii=False).encode("utf-8"))
    with client["lock"]:
        client["sock"].sendall(frame)


def broadcast(obj):
    dead = []
    with _clients_lock:
        targets = list(_clients)
    for c in targets:
        try:
            _send_to(c, obj)
        except Exception:
            dead.append(c)
    if dead:
        with _clients_lock:
            for c in dead:
                if c in _clients:
                    _clients.remove(c)


# ---------------------------------------------------------------------------
# HTTP + WS handler
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "OrmuzServer/1.0"

    def log_message(self, fmt, *args):
        # тихий лог: только сокет-события пишем сами
        pass

    # ---- helpers ----
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _static(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            path = "/index.html"
        rel = os.path.normpath(path.lstrip("/"))
        full = os.path.join(CLIENT_DIR, rel)
        if not os.path.abspath(full).startswith(CLIENT_DIR) or not os.path.isfile(full):
            self.send_error(404, "Not Found")
            return
        ext = os.path.splitext(full)[1].lower()
        ctype = MIME.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ---- routing ----
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        # WebSocket upgrade
        if path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            self._ws_serve()
            return

        if path == "/api/v1/state":
            with _state_lock:
                data = dict(STATE)
            data["locked"] = data.get("locked_until", 0) > time.time()
            data["threshold"] = UNLOCK_TAPS
            data["ad_every"] = AD_EVERY_TAPS
            self._json(data)
            return

        self._static()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/v1/push/register":
            try:
                ln = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(ln).decode("utf-8")) if ln else {}
            except Exception:
                body = {}
            register_push(str(body.get("token", ""))[:4096], str(body.get("lang", "en")))
            self._json({"ok": True})
            return
        self.send_error(404)

    # ---- websocket ----
    def _ws_serve(self):
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self.send_error(400, "Bad WS request")
            return
        accept = base64.b64encode(
            hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )
        self.wfile.write(resp.encode())
        self.wfile.flush()

        client = {"sock": self.connection, "lock": threading.Lock()}
        with _clients_lock:
            _clients.append(client)
        self._ws_client = client
        print(f"[ws] connect  {self.client_address[0]}  (clients={len(_clients)})")

        # сразу отдаём текущее состояние новому клиенту (с полями лока/тапов)
        try:
            _send_to(client, _public_snapshot())
        except Exception:
            pass

        try:
            while True:
                opcode, data = ws_read_frame(self.rfile)
                if opcode == 0x8:                       # close
                    break
                if opcode == 0x9:                       # ping -> pong
                    with client["lock"]:
                        client["sock"].sendall(ws_encode(data, 0xA))
                    continue
                if opcode not in (0x1, 0x2):
                    continue
                self._handle_ws_message(data)
        except Exception as e:
            print(f"[ws] drop {self.client_address[0]}: {e}")
        finally:
            with _clients_lock:
                if client in _clients:
                    _clients.remove(client)
            print(f"[ws] disconnect {self.client_address[0]}  (clients={len(_clients)})")
            self.close_connection = True

    def _handle_ws_message(self, data: bytes):
        try:
            msg = json.loads(data.decode("utf-8"))
        except Exception:
            return
        action = msg.get("action")
        user = str(msg.get("user", ""))[:16] or None
        country = (str(msg.get("country", "")) or "").strip()[:40] or None
        # country = id флага (blood_standard и т.п.), не код страны

        # ---- бесплатный тумблер (запрещён, пока активен лок) ----
        if action == "TOGGLE":
            with _state_lock:
                locked = _lock_active()
            if locked:
                # откатываем оптимистичный тумблер у этого клиента
                try:
                    _send_to(self._ws_client, _public_snapshot())
                except Exception:
                    pass
                return
            state = "OPEN" if msg.get("state") == "OPEN" else "CLOSED"
            with _state_lock:
                STATE["current_state"] = state
                STATE["last_updated_by"] = user
                STATE["last_country"] = country
                STATE["updated_at"] = int(time.time())
                STATE["last_action"] = {"kind": "toggle", "user": user,
                                        "country": country, "state": state,
                                        "at": int(time.time())}
                save_state(STATE)
            print(f"[toggle] {user} ({country}) -> {state}")
            broadcast(_public_snapshot())
            return

        # ---- платное действие: sink (закрыть) / fleet (открыть) ----
        if action == "PAID":
            kind = "fleet" if msg.get("kind") == "fleet" else "sink"
            token = msg.get("token")
            # TODO(prod): валидировать покупку через Google Play Developer API
            # по token+productId ПЕРЕД применением. Здесь принимаем любой не пустой
            # (веб-мок шлёт "MOCK"). Без токена — игнор.
            if not token:
                return
            new_state = "OPEN" if kind == "fleet" else "CLOSED"
            with _state_lock:
                STATE["current_state"] = new_state
                STATE["last_updated_by"] = user
                STATE["last_country"] = country
                STATE["updated_at"] = int(time.time())
                STATE["locked_until"] = int(time.time()) + LOCK_SECONDS
                STATE["lock_kind"] = kind
                STATE["unlock_taps"] = 0
                at = int(time.time())
                STATE["last_action"] = {"kind": kind, "user": user,
                                        "country": country, "state": new_state,
                                        "at": at}
                save_state(STATE)
                locked_until = STATE["locked_until"]
            print(f"[paid] {user} ({country}) {kind} -> {new_state} lock {LOCK_SECONDS}s")
            broadcast({"event": "ACTION", "kind": kind, "user": user,
                       "country": country, "state": new_state,
                       "locked_until": locked_until, "at": at})
            broadcast(_public_snapshot())
            # пуш ТОЛЬКО на платные действия, в фоне (не блокирует сокет)
            threading.Thread(target=send_paid_push, args=(kind, user), daemon=True).start()
            return

        # ---- бесплатный разлок: тап (+1) или просмотр рекламы (+бонус) ----
        if action in ("TAP", "AD"):
            inc = AD_BONUS_TAPS if action == "AD" else 1
            with _state_lock:
                if not _lock_active():
                    return
                STATE["unlock_taps"] = STATE.get("unlock_taps", 0) + inc
                reached = STATE["unlock_taps"] >= UNLOCK_TAPS
                if reached:
                    STATE["locked_until"] = 0
                    STATE["lock_kind"] = None
                    STATE["unlock_taps"] = 0
                taps = STATE["unlock_taps"]
                cur = STATE["current_state"]
                save_state(STATE)
            if reached:
                print("[unlock] пролив разлочен тапами")
                broadcast({"event": "UNLOCKED", "state": cur})
                broadcast(_public_snapshot())
            else:
                broadcast({"event": "TAP_PROGRESS", "taps": taps,
                           "threshold": UNLOCK_TAPS, "ad_every": AD_EVERY_TAPS})
            return


def main():
    if not os.path.isdir(CLIENT_DIR):
        print("!! CLIENT_DIR не найден:", CLIENT_DIR)
    port = _find_free_port(HOST, PORT)
    if port != PORT:
        print(f"!! Порт {PORT} занят другим процессом — беру {port}")
    srv = ThreadingHTTPServer((HOST, port), Handler)
    print("=" * 56)
    print("  Ормузский пролив — сервер запущен")
    print(f"  Открой:   http://localhost:{port}")
    print(f"  Статика:  {CLIENT_DIR}")
    print(f"  Состояние:{STATE_FILE}")
    print("  Ctrl+C — остановить")
    print("=" * 56)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановлено.")
        srv.shutdown()


if __name__ == "__main__":
    main()
