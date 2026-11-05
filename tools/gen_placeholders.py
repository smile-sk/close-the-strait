#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_placeholders.py — генератор PNG-заглушек для игры «Ормузский пролив».

Рисует ВСЕ графические ассеты из раздела 4 ТЗ + иконки для Play Market.
Все элементы намеренно "плейсхолдерные" (простая геометрия, подпись ключа),
чтобы их было удобно заменить финальным артом, не трогая код клиента.

Требования: Python 3.8+, Pillow  ->  pip install Pillow
Запуск:      python tools/gen_placeholders.py
             python tools/gen_placeholders.py --out client   (указать корень client/)

Меняй цвета/размеры/формы прямо здесь и перегенерируй — имена файлов и пути
менять НЕ нужно, клиент грузит их по фиксированным ключам (assets/*.png).
"""

import argparse
import math
import os
import random
import struct
import wave

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ----------------------------------------------------------------------------
# Палитра (правь тут — весь арт пересоберётся согласованно)
# ----------------------------------------------------------------------------
WATER_DEEP   = (13, 59, 92)
WATER_MID    = (18, 85, 127)
WATER_SHAL   = (26, 111, 160)
LAND_IRAN    = (184, 154, 94)
LAND_SOUTH   = (169, 138, 78)
LAND_EDGE    = (120, 96, 52)
STEEL_DARK   = (43, 47, 54)
STEEL_MID    = (68, 75, 85)
STEEL_LIGHT  = (108, 118, 132)
STEEL_HI     = (150, 162, 178)
HULL         = (58, 65, 73)
DECK         = (92, 101, 112)
CARGO_A      = (138, 90, 43)
CARGO_B      = (70, 96, 120)
WARN_YELLOW  = (241, 196, 15)
LED_OPEN     = (39, 174, 96)
LED_CLOSED   = (192, 57, 43)
INK          = (26, 29, 34)
PAPER        = (232, 236, 240)
GHOST        = (255, 255, 255)

# ----------------------------------------------------------------------------
# Шрифты
# ----------------------------------------------------------------------------
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans-Bold.ttf",
    "arial.ttf",
]


def font(size, bold=True):
    for path in FONT_CANDIDATES:
        try:
            f = ImageFont.truetype(path, size)
            if bold and "Bold" not in path:
                continue
            return f
        except Exception:
            continue
    try:
        return ImageFont.truetype(FONT_CANDIDATES[1], size)
    except Exception:
        return ImageFont.load_default()


# ----------------------------------------------------------------------------
# Утилиты рисования
# ----------------------------------------------------------------------------
def new_rgba(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def centered_text(d, box, text, fnt, fill):
    x0, y0, x1, y1 = box
    l, t, r, b = d.textbbox((0, 0), text, font=fnt)
    tw, th = r - l, b - t
    d.text((x0 + (x1 - x0 - tw) / 2 - l, y0 + (y1 - y0 - th) / 2 - t),
           text, font=fnt, fill=fill)


def bevel_rect(d, box, r, fill, hi, lo, bw=3):
    """Скруглённый прямоугольник с фаской (объём панели)."""
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=r, fill=fill)
    d.arc([x0, y0, x0 + 2 * r, y0 + 2 * r], 90, 180, fill=hi, width=bw)
    d.line([x0 + r, y0, x1 - r, y0], fill=hi, width=bw)
    d.line([x0, y0 + r, x0, y1 - r], fill=hi, width=bw)
    d.line([x0 + r, y1, x1 - r, y1], fill=lo, width=bw)
    d.line([x1, y0 + r, x1, y1 - r], fill=lo, width=bw)


def watermark(img, key, corner=True):
    """Заглушечная подпись отключена (была 'PLACEHOLDER · <key>')."""
    return


def star(cx, cy, r_out, r_in, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        ang = math.radians(rot + i * 180.0 / n)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


# ----------------------------------------------------------------------------
# 1. bg_strait_map — фоновая карта пролива (1080x1920, портрет)
# ----------------------------------------------------------------------------
def make_bg(out):
    """Фон-карта пролива 1080x1920 (портрет).
    Если рядом лежит реальная карта tools/source_map.(jpg|png) — берём её и
    кадрируем «cover» с фокусом на проливе. Иначе рисуем схематичную заглушку.
    BG_FOCUS_X/Y — точка кадра (0..1) в исходнике; правь при замене карты."""
    W, H = 1080, 1920
    here = os.path.dirname(__file__)
    src_path = None
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(here, "source_map" + ext)
        if os.path.exists(p):
            src_path = p
            break

    if src_path:
        BG_FOCUS_X, BG_FOCUS_Y = 0.64, 0.50   # центр пролива в исходной карте
        src = Image.open(src_path).convert("RGB")
        sw, sh = src.size
        s = max(W / sw, H / sh)
        nw, nh = round(sw * s), round(sh * s)
        src = src.resize((nw, nh), Image.LANCZOS)
        cx, cy = BG_FOCUS_X * nw, BG_FOCUS_Y * nh
        left = int(round(cx - W / 2))
        top = int(round(cy - H / 2))
        left = max(0, min(nw - W, left))
        top = max(0, min(nh - H, top))
        img = src.crop((left, top, left + W, top + H))
        # квантуем палитру: фотокарта в PNG весит мегабайты, 256 цветов — сотни КБ
        img = img.quantize(colors=256, method=Image.FASTOCTREE,
                           dither=Image.FLOYDSTEINBERG)
        img.save(os.path.join(out, "assets", "bg_strait_map.png"), optimize=True)
        return

    _make_bg_synthetic(out)


def _make_bg_synthetic(out):
    W, H = 1080, 1920
    img = Image.new("RGBA", (W, H), WATER_MID + (255,))
    d = ImageDraw.Draw(img)

    # вертикальный градиент воды
    for y in range(H):
        t = y / H
        c = tuple(int(WATER_DEEP[i] + (WATER_SHAL[i] - WATER_DEEP[i]) *
                      (0.5 + 0.5 * math.sin(t * math.pi))) for i in range(3))
        d.line([(0, y), (W, y)], fill=c + (255,))

    # суша: Иран (север) — волнистая береговая линия
    iran = [(0, 0), (W, 0), (W, 470)]
    for x in range(W, -1, -40):
        iran.append((x, 430 + 55 * math.sin(x / 150.0)))
    iran.append((0, 470))
    d.polygon(iran, fill=LAND_IRAN + (255,))
    # мыс Мусандам (Оман) / берег ОАЭ — юг
    south = [(0, H), (W, H), (W, H - 430)]
    for x in range(W, -1, -40):
        south.append((x, H - 400 + 60 * math.sin(x / 130.0 + 1)))
    south.append((0, H - 430))
    d.polygon(south, fill=LAND_SOUTH + (255,))

    # береговые кромки
    d.line([(0, 470)] + [(x, 430 + 55 * math.sin(x / 150.0)) for x in range(0, W, 40)],
           fill=LAND_EDGE + (255,), width=6)

    # судоходный фарватер — пунктир через центр пролива
    lane_y = H // 2
    for x in range(60, W - 60, 70):
        d.line([(x, lane_y - 40), (x + 40, lane_y + 40)], fill=(255, 255, 255, 60), width=6)

    # подписи суши
    fL = font(58, bold=True)
    centered_text(d, (0, 150, W, 260), "ИРАН / IRAN", fL, (60, 48, 20, 220))
    centered_text(d, (0, H - 250, W, H - 140), "ОМАН · ОАЭ / OMAN · UAE", fL, (60, 48, 20, 220))
    fZ = font(40, bold=True)
    centered_text(d, (0, lane_y - 30, W, lane_y + 30),
                  "ОРМУЗСКИЙ ПРОЛИВ", fZ, (235, 240, 245, 150))

    # координатная сетка-плейсхолдер
    for gx in range(0, W, 120):
        d.line([(gx, 0), (gx, H)], fill=(255, 255, 255, 12), width=1)
    for gy in range(0, H, 120):
        d.line([(0, gy), (W, gy)], fill=(255, 255, 255, 12), width=1)

    watermark(img, "bg_strait_map")
    img.save(os.path.join(out, "assets", "bg_strait_map.png"))


# ----------------------------------------------------------------------------
# 2. ship_barge — спрайт баржи (вид сверху, прозрачный фон)
# ----------------------------------------------------------------------------
def make_barge(out):
    W, H = 320, 120
    img = new_rgba(W, H)
    d = ImageDraw.Draw(img)

    # тень
    sh = new_rgba(W, H)
    ds = ImageDraw.Draw(sh)
    ds.polygon([(30, 30), (W - 55, 26), (W - 12, H / 2), (W - 55, H - 26), (30, H - 30)],
               fill=(0, 0, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(6))
    img.alpha_composite(sh, (4, 8))

    # корпус (нос справа)
    hull = [(24, 24), (W - 60, 20), (W - 16, H / 2), (W - 60, H - 20), (24, H - 24)]
    d.polygon(hull, fill=HULL + (255,))
    d.line(hull + [hull[0]], fill=(28, 32, 37, 255), width=3)

    # палуба
    d.polygon([(40, 34), (W - 74, 31), (W - 40, H / 2), (W - 74, H - 31), (40, H - 34)],
              fill=DECK + (255,))

    # груз-контейнеры
    cols = [CARGO_A, CARGO_B, CARGO_A, CARGO_B]
    x = 58
    for i, c in enumerate(cols):
        d.rounded_rectangle([x, 40, x + 34, H - 40], radius=4, fill=c + (255,),
                            outline=(20, 24, 28, 255), width=2)
        x += 42

    # рубка у кормы
    d.rounded_rectangle([28, 42, 52, H - 42], radius=4, fill=STEEL_LIGHT + (255,),
                        outline=(20, 24, 28, 255), width=2)

    img.save(os.path.join(out, "assets", "ship_barge.png"))


# ----------------------------------------------------------------------------
# 3-5. switch_base + switch_toggle_open/close (индустриальный тумблер)
#      base — статичная панель, toggle_* — накладываемые сверху рукоятки.
# ----------------------------------------------------------------------------
PANEL_W, PANEL_H = 600, 340


def _panel_img():
    """Общая панель рубильника (корпус, полосы, жёлоб, болты)."""
    W, H = PANEL_W, PANEL_H
    img = new_rgba(W, H)
    d = ImageDraw.Draw(img)

    # корпус панели
    bevel_rect(d, (10, 10, W - 10, H - 10), 30, STEEL_DARK + (255,),
               STEEL_LIGHT + (255,), (16, 18, 22, 255), bw=5)
    # предупредительные полосы сверху/снизу
    for sx in range(24, W - 24, 48):
        d.polygon([(sx, 26), (sx + 24, 26), (sx + 11, 46), (sx - 13, 46)],
                  fill=WARN_YELLOW + (255,))
        d.polygon([(sx, H - 26), (sx + 24, H - 26), (sx + 11, H - 46), (sx - 13, H - 46)],
                  fill=INK + (255,))
    # утопленный жёлоб под рукоятку
    d.rounded_rectangle([100, H / 2 - 48, W - 100, H / 2 + 48], radius=48,
                        fill=(18, 20, 24, 255), outline=(8, 10, 12, 255), width=5)
    # крепёжные болты по углам
    for bx, by in [(40, 40), (W - 40, 40), (40, H - 40), (W - 40, H - 40)]:
        d.ellipse([bx - 12, by - 12, bx + 12, by + 12], fill=STEEL_MID + (255,),
                  outline=(12, 14, 17, 255), width=2)
        d.line([bx - 7, by, bx + 7, by], fill=(12, 14, 17, 255), width=2)
    return img


def make_switch_base(out):
    # оставляем отдельный файл для справки; клиент его больше не накладывает
    _panel_img().save(os.path.join(out, "assets", "switch_base.png"))


def _lever(out, name, side, knob_color, led_color):
    """Готовая ЦЕЛЬНАЯ картинка рубильника в одном состоянии.
    side: 'right' (OPEN) или 'left' (CLOSED). Всё в одном PNG — на вёрстке
    ничего не разъезжается, клиент просто меняет src."""
    W, H = PANEL_W, PANEL_H
    img = _panel_img()
    cy = H / 2
    x_left, x_right = 150, W - 150
    kx = x_right if side == "right" else x_left

    # мягкое свечение под рукояткой
    glow = new_rgba(W, H)
    gd = ImageDraw.Draw(glow)
    gr = 74
    gd.ellipse([kx - gr, cy - gr, kx + gr, cy + gr], fill=knob_color + (80,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(16)))

    d = ImageDraw.Draw(img)
    # шток от центра к рукоятке
    d.line([(W / 2, cy), (kx, cy)], fill=STEEL_HI + (255,), width=18)
    d.line([(W / 2, cy), (kx, cy)], fill=STEEL_LIGHT + (255,), width=9)
    # рукоятка
    r = 52
    d.ellipse([kx - r, cy - r, kx + r, cy + r], fill=knob_color + (255,),
              outline=(12, 14, 17, 255), width=5)
    d.ellipse([kx - r + 12, cy - r + 10, kx + r - 22, cy + r - 26],
              fill=(255, 255, 255, 55))  # блик
    # LED-индикатор состояния
    d.ellipse([kx - 14, cy - 14, kx + 14, cy + 14], fill=led_color + (255,),
              outline=(255, 255, 255, 170), width=2)

    img.save(os.path.join(out, "assets", name))


def make_toggles(out):
    # Если рядом лежат готовые состояния (напр. вырезанные из рендера
    # Leonardo/Midjourney) — берём их и НЕ перерисовываем. Заменить рубильник:
    # положи свои tools/switch_open.png и tools/switch_close.png (или удали их,
    # чтобы вернуть рисованную заглушку).
    import shutil
    here = os.path.dirname(__file__)
    src_open = os.path.join(here, "switch_open.png")
    src_close = os.path.join(here, "switch_close.png")
    if os.path.exists(src_open) and os.path.exists(src_close):
        shutil.copyfile(src_open, os.path.join(out, "assets", "switch_toggle_open.png"))
        shutil.copyfile(src_close, os.path.join(out, "assets", "switch_toggle_close.png"))
        return
    _lever(out, "switch_toggle_open.png", "right", LED_OPEN, (140, 255, 170))
    _lever(out, "switch_toggle_close.png", "left", LED_CLOSED, (255, 150, 140))


# ----------------------------------------------------------------------------
# 6. icon_settings — шестерёнка (прозрачный фон)
# ----------------------------------------------------------------------------
def make_settings(out):
    S = 128
    img = new_rgba(S, S)
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    teeth, r_out, r_in, hole = 8, 52, 40, 18
    poly = []
    steps = teeth * 2
    for i in range(steps * 2):
        ang = math.radians(i * 360.0 / (steps * 2))
        r = r_out if (i // 2) % 2 == 0 else r_in
        poly.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    d.polygon(poly, fill=PAPER + (235,))
    d.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(0, 0, 0, 0))
    d.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], outline=(120, 130, 145, 255), width=3)
    img.save(os.path.join(out, "assets", "icon_settings.png"))


# ----------------------------------------------------------------------------
# 7. ui_panel_bg — фон модальных окон (прозрачные углы)
# ----------------------------------------------------------------------------
def make_panel(out):
    W, H = 900, 640
    img = new_rgba(W, H)
    d = ImageDraw.Draw(img)
    bevel_rect(d, (6, 6, W - 6, H - 6), 34, (34, 38, 45, 240),
               STEEL_LIGHT + (255,), (16, 18, 22, 255), bw=4)
    # шапка модалки
    d.rounded_rectangle([6, 6, W - 6, 96], radius=34, fill=(24, 27, 32, 255))
    d.rectangle([6, 60, W - 6, 96], fill=(24, 27, 32, 255))
    d.line([30, 96, W - 30, 96], fill=WARN_YELLOW + (180,), width=3)
    watermark(img, "ui_panel_bg", corner=True)
    img.save(os.path.join(out, "assets", "ui_panel_bg.png"))


# ----------------------------------------------------------------------------
# 8. Флаги стран (160x120, 4:3). Упрощённая геометрия = заглушки.
# ----------------------------------------------------------------------------
FLAG_W, FLAG_H = 160, 120

FLAGS = {
    "ua": ("h", [(0, 87, 183), (255, 215, 0)]),
    "ru": ("h", [(255, 255, 255), (0, 57, 166), (213, 43, 30)]),
    "de": ("h", [(0, 0, 0), (221, 0, 0), (255, 206, 0)]),
    "pl": ("h", [(255, 255, 255), (220, 20, 60)]),
    "ir": ("h", [(35, 159, 64), (255, 255, 255), (218, 0, 0)]),
    "fr": ("v", [(0, 85, 164), (255, 255, 255), (239, 65, 53)]),
    "it": ("v", [(0, 146, 70), (255, 255, 255), (206, 43, 55)]),
    "us": ("special", "us"),
    "gb": ("special", "gb"),
    "cn": ("special", "cn"),
    "tr": ("special", "tr"),
    "in": ("special", "in"),
    "jp": ("special", "jp"),
    "sa": ("special", "sa"),
    "ae": ("special", "ae"),
    "om": ("special", "om"),
}


def _flag_canvas():
    img = Image.new("RGBA", (FLAG_W, FLAG_H), (255, 255, 255, 255))
    return img, ImageDraw.Draw(img)


def _flag_frame(img):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, FLAG_W - 1, FLAG_H - 1], outline=(40, 44, 50, 255), width=2)
    return img


def draw_flag(iso, spec, out):
    kind = spec[0]
    img, d = _flag_canvas()
    if kind == "h":
        cols = spec[1]
        n = len(cols)
        for i, c in enumerate(cols):
            d.rectangle([0, i * FLAG_H / n, FLAG_W, (i + 1) * FLAG_H / n], fill=c + (255,))
    elif kind == "v":
        cols = spec[1]
        n = len(cols)
        for i, c in enumerate(cols):
            d.rectangle([i * FLAG_W / n, 0, (i + 1) * FLAG_W / n, FLAG_H], fill=c + (255,))
    else:
        name = spec[1]
        if name == "jp":
            d.rectangle([0, 0, FLAG_W, FLAG_H], fill=(255, 255, 255, 255))
            r = 34
            d.ellipse([FLAG_W/2-r, FLAG_H/2-r, FLAG_W/2+r, FLAG_H/2+r], fill=(188, 0, 45, 255))
        elif name == "us":
            for i in range(13):
                c = (178, 34, 52) if i % 2 == 0 else (255, 255, 255)
                d.rectangle([0, i*FLAG_H/13, FLAG_W, (i+1)*FLAG_H/13], fill=c+(255,))
            cw, ch = FLAG_W*0.42, FLAG_H*7/13
            d.rectangle([0, 0, cw, ch], fill=(60, 59, 110, 255))
            for ry in range(5):
                for rx in range(6):
                    x = 8 + rx*(cw-14)/5
                    y = 6 + ry*(ch-10)/4
                    d.ellipse([x-2, y-2, x+2, y+2], fill=(255, 255, 255, 255))
        elif name == "gb":
            d.rectangle([0, 0, FLAG_W, FLAG_H], fill=(1, 33, 105, 255))
            d.line([0, 0, FLAG_W, FLAG_H], fill=(255, 255, 255, 255), width=16)
            d.line([FLAG_W, 0, 0, FLAG_H], fill=(255, 255, 255, 255), width=16)
            d.line([0, 0, FLAG_W, FLAG_H], fill=(200, 16, 46, 255), width=7)
            d.line([FLAG_W, 0, 0, FLAG_H], fill=(200, 16, 46, 255), width=7)
            d.rectangle([FLAG_W/2-16, 0, FLAG_W/2+16, FLAG_H], fill=(255, 255, 255, 255))
            d.rectangle([0, FLAG_H/2-16, FLAG_W, FLAG_H/2+16], fill=(255, 255, 255, 255))
            d.rectangle([FLAG_W/2-8, 0, FLAG_W/2+8, FLAG_H], fill=(200, 16, 46, 255))
            d.rectangle([0, FLAG_H/2-8, FLAG_W, FLAG_H/2+8], fill=(200, 16, 46, 255))
        elif name == "cn":
            d.rectangle([0, 0, FLAG_W, FLAG_H], fill=(222, 41, 16, 255))
            d.polygon(star(40, 34, 22, 9), fill=(255, 222, 0, 255))
            for sx, sy in [(74, 16), (86, 30), (86, 48), (74, 60)]:
                d.polygon(star(sx, sy, 7, 3), fill=(255, 222, 0, 255))
        elif name == "tr":
            d.rectangle([0, 0, FLAG_W, FLAG_H], fill=(227, 10, 23, 255))
            d.ellipse([46, 34, 106, 94], fill=(255, 255, 255, 255))
            d.ellipse([60, 34, 116, 94], fill=(227, 10, 23, 255))
            d.polygon(star(118, 64, 15, 6), fill=(255, 255, 255, 255))
        elif name == "in":
            for i, c in enumerate([(255, 153, 51), (255, 255, 255), (19, 136, 8)]):
                d.rectangle([0, i*FLAG_H/3, FLAG_W, (i+1)*FLAG_H/3], fill=c+(255,))
            d.ellipse([FLAG_W/2-16, FLAG_H/2-16, FLAG_W/2+16, FLAG_H/2+16],
                      outline=(0, 0, 128, 255), width=3)
            for a in range(0, 360, 30):
                x = FLAG_W/2 + 14*math.cos(math.radians(a))
                y = FLAG_H/2 + 14*math.sin(math.radians(a))
                d.line([FLAG_W/2, FLAG_H/2, x, y], fill=(0, 0, 128, 255), width=1)
        elif name == "sa":
            d.rectangle([0, 0, FLAG_W, FLAG_H], fill=(0, 108, 53, 255))
            d.rectangle([26, 52, FLAG_W-26, 64], fill=(255, 255, 255, 255))
            d.line([26, 82, FLAG_W-26, 82], fill=(255, 255, 255, 255), width=4)
        elif name == "ae":
            d.rectangle([0, 0, FLAG_W*0.28, FLAG_H], fill=(255, 0, 0, 255))
            bands = [(0, 122, 61), (255, 255, 255), (0, 0, 0)]
            for i, c in enumerate(bands):
                d.rectangle([FLAG_W*0.28, i*FLAG_H/3, FLAG_W, (i+1)*FLAG_H/3], fill=c+(255,))
        elif name == "om":
            d.rectangle([0, 0, FLAG_W*0.30, FLAG_H], fill=(215, 20, 26, 255))
            bands = [(255, 255, 255), (215, 20, 26), (0, 122, 61)]
            for i, c in enumerate(bands):
                d.rectangle([FLAG_W*0.30, i*FLAG_H/3, FLAG_W, (i+1)*FLAG_H/3], fill=c+(255,))
    _flag_frame(img)
    img.save(os.path.join(out, "assets", "flags", f"{iso}.png"))


def make_flags(out):
    for iso, spec in FLAGS.items():
        draw_flag(iso, spec, out)


# ----------------------------------------------------------------------------
# 9. Иконки приложения для Play Market + PWA
# ----------------------------------------------------------------------------
def _app_icon(size, maskable=False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(size * 0.14) if maskable else 0          # safe-zone для maskable
    pad = m
    # фон-плитка
    d.rounded_rectangle([pad, pad, size - pad, size - pad],
                        radius=int(size * 0.18), fill=(16, 42, 66, 255))
    # вода
    d.rounded_rectangle([pad, size*0.42, size-pad, size-pad],
                        radius=int(size*0.10), fill=(26, 111, 160, 255))
    # мини-тумблер
    cx, cy = size/2, size*0.66
    tw = (size - 2*pad) * 0.5
    d.rounded_rectangle([cx-tw/2, cy-tw*0.16, cx+tw/2, cy+tw*0.16],
                        radius=int(tw*0.16), fill=(34, 38, 45, 255))
    r = tw*0.2
    d.ellipse([cx+tw/2-r*1.6, cy-r, cx+tw/2-r*1.6+2*r, cy+r], fill=(39, 174, 96, 255))
    # баржа-силуэт сверху
    d.polygon([(size*0.30, size*0.30), (size*0.66, size*0.30),
               (size*0.72, size*0.37), (size*0.30, size*0.37)],
              fill=(232, 236, 240, 255))
    return img


def make_icons(out):
    icons = out.replace("assets", "icons") if out.endswith("assets") else os.path.join(out, "icons")
    os.makedirs(icons, exist_ok=True)
    _app_icon(192).save(os.path.join(icons, "icon-192.png"))
    _app_icon(512).save(os.path.join(icons, "icon-512.png"))
    _app_icon(512, maskable=True).save(os.path.join(icons, "icon-maskable-512.png"))

    # feature graphic 1024x500 для карточки в Play Market
    fg = Image.new("RGBA", (1024, 500), (13, 59, 92, 255))
    d = ImageDraw.Draw(fg)
    for y in range(500):
        c = tuple(int(WATER_DEEP[i] + (WATER_SHAL[i]-WATER_DEEP[i]) * y/500) for i in range(3))
        d.line([(0, y), (1024, y)], fill=c+(255,))
    ic = _app_icon(300)
    fg.alpha_composite(ic, (70, 100))
    d.text((420, 180), "ОРМУЗСКИЙ", font=font(72), fill=(255, 255, 255, 255))
    d.text((420, 260), "ПРОЛИВ", font=font(72), fill=(241, 196, 15, 255))
    d.text((422, 350), "placeholder · feature graphic", font=font(28), fill=(200, 210, 220, 200))
    fg.convert("RGB").save(os.path.join(icons, "feature-graphic-1024x500.png"))


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
# Звуки. switch_off/on — скрежет металла как при закрывании броневых ворот
# (свип резонансного фильтра по шуму + скрежещущая амплитудная модуляция +
# финальный лязг). sink — бульканье тонущих барж. fleet — очередь взрывов.
# ----------------------------------------------------------------------------
def _gate(closing=True, seed=1):
    sr = 44100; dur = 0.85; n = int(sr * dur)
    rnd = random.Random(seed)
    low = band = lp = 0.0
    Q = 8.0; q = 1.0 / Q
    out = [0.0] * n
    for i in range(n):
        t = i / sr; p = t / dur
        fc = (1200 * (1 - p) + 300 * p) if closing else (300 * (1 - p) + 1200 * p)
        f = 2 * math.sin(math.pi * fc / sr)
        # шум со «скрежещущей» модуляцией
        x = rnd.uniform(-1, 1)
        gr = (0.55 + 0.45 * abs(math.sin(2 * math.pi * 30 * t))) * (0.8 + 0.2 * rnd.uniform(-1, 1))
        x *= gr
        low += f * band
        high = x - low - q * band
        band += f * high
        lp += 0.02 * (rnd.uniform(-1, 1) - lp)          # низкий гул массы ворот
        s = 1.2 * band + 0.5 * lp * math.sin(2 * math.pi * 70 * t)
        for r, a in ((1.0, 0.25), (2.7, 0.15), (5.1, 0.1)):  # металлические подвывания
            s += a * 0.3 * math.sin(2 * math.pi * fc * r * 0.5 * t)
        env = min(1.0, t / 0.05) * (1.0 if p < 0.85 else max(0.0, (1 - p) / 0.15))
        out[i] = s * env
    # финальный лязг (ворота бьются об упор): в конце для закрытия, в начале для открытия
    clang = int((0.80 if closing else 0.02) * n)
    for j in range(clang, min(n, clang + int(0.18 * sr))):
        tt = (j - clang) / sr
        c = rnd.uniform(-1, 1) * math.exp(-tt / 0.004) * 0.8
        c += math.sin(2 * math.pi * 90 * tt) * math.exp(-tt / 0.06) * 0.9
        for r, a in ((1.0, 0.5), (1.58, 0.35), (2.24, 0.25)):
            c += a * math.sin(2 * math.pi * 180 * r * tt) * math.exp(-tt / 0.05)
        out[j] += c
    return sr, _normfade(out, sr, 0.85)


def _bubbles(seed=1):
    sr = 44100; dur = 1.3; n = int(sr * dur)
    rnd = random.Random(seed)
    out = [0.0] * n
    lp = 0.0
    for i in range(n):                                  # низкий водяной гул
        lp += 0.008 * (rnd.uniform(-1, 1) - lp)
        out[i] += lp * 0.35 * min(1.0, i / (0.1 * sr)) * max(0.0, 1 - i / n)
    for _ in range(16):                                 # пузыри-«блоопы» со скольжением вверх
        start = rnd.uniform(0.05, dur - 0.16)
        f0 = rnd.uniform(250, 500); f1 = f0 * rnd.uniform(1.8, 3.0)
        bl = rnd.uniform(0.05, 0.12); amp = rnd.uniform(0.4, 0.9)
        s0 = int(start * sr); ln = int(bl * sr); ph = 0.0
        for j in range(ln):
            pp = j / ln; f = f0 * (1 - pp) + f1 * pp
            ph += 2 * math.pi * f / sr
            si = s0 + j
            if 0 <= si < n:
                out[si] += amp * 0.5 * math.sin(ph) * math.sin(math.pi * pp)
    return sr, _normfade(out, sr, 0.8)


def _booms(seed=1):
    sr = 44100; dur = 1.1; n = int(sr * dur)
    rnd = random.Random(seed)
    out = [0.0] * n
    for k in range(6):                                  # очередь из 6 взрывов
        start = 0.02 + k * 0.11 + rnd.uniform(-0.02, 0.02)
        s0 = int(start * sr); blen = int(0.28 * sr); lp = 0.0
        f_thump = rnd.uniform(55, 85)
        for j in range(blen):
            tt = j / sr; si = s0 + j
            if not (0 <= si < n):
                continue
            lp += 0.05 * (rnd.uniform(-1, 1) - lp)      # тело взрыва (шум + LP)
            body = lp * math.exp(-tt / 0.10) * 1.2
            thump = math.sin(2 * math.pi * f_thump * tt) * math.exp(-tt / 0.09) * 0.9
            click = rnd.uniform(-1, 1) * math.exp(-tt / 0.003) * 0.5 if tt < 0.02 else 0.0
            out[si] += (body + thump + click) * rnd.uniform(0.8, 1.0)
    return sr, _normfade(out, sr, 0.85)


def _normfade(out, sr, peaklvl):
    peak = max(1e-9, max(abs(v) for v in out)); g = peaklvl / peak
    fade = int(0.025 * sr); n = len(out)
    for i in range(n):
        v = out[i] * g
        if i > n - fade:
            v *= (n - i) / fade
        out[i] = v
    return out


def _write_wav(path, sr, samples):
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        buf = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            buf += struct.pack("<h", v)
        w.writeframes(bytes(buf))


def make_sfx(out):
    sfx_dir = os.path.join(out, "assets", "sfx")
    os.makedirs(sfx_dir, exist_ok=True)
    sr, on = _gate(closing=False, seed=5)      # открытие ворот
    _write_wav(os.path.join(sfx_dir, "switch_on.wav"), sr, on)
    sr, off = _gate(closing=True, seed=9)      # закрытие ворот (скрежет + лязг)
    _write_wav(os.path.join(sfx_dir, "switch_off.wav"), sr, off)
    sr, sk = _bubbles(seed=3)                  # тонущие баржи
    _write_wav(os.path.join(sfx_dir, "sink.wav"), sr, sk)
    sr, bo = _booms(seed=7)                    # атака флота — очередь взрывов
    _write_wav(os.path.join(sfx_dir, "fleet.wav"), sr, bo)



# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "client"),
                    help="корень client/ (по умолчанию ../client)")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(os.path.join(out, "assets", "flags"), exist_ok=True)
    os.makedirs(os.path.join(out, "icons"), exist_ok=True)

    make_bg(out)
    make_barge(out)
    make_switch_base(out)
    make_toggles(out)
    make_settings(out)
    make_panel(out)
    make_sfx(out)
    make_flags(out)
    make_icons(out)

    print("Готово. Ассеты записаны в:", out)
    for root, _, files in os.walk(os.path.join(out, "assets")):
        for f in sorted(files):
            print("  ", os.path.relpath(os.path.join(root, f), out))
    for f in sorted(os.listdir(os.path.join(out, "icons"))):
        print("   icons/" + f)


if __name__ == "__main__":
    main()
