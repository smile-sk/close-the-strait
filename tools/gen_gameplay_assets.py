#!/usr/bin/env python3
"""Спрайты новой механики (заглушки, потом можно переделать своими).

Пишет в client/assets/:
  tanker.png       — танкер (вид сверху, нос вправо, прозрачный фон)
  cargo.png        — контейнеровоз
  warship.png      — военный корабль (флот)
  barge_wreck.png  — затопленная баржа (торчит из воды)
  explosion.png    — мультяшный взрыв (для расчистки флотом)
  icon_sink.png    — иконка платного действия «потопить баржи»
  icon_fleet.png   — иконка платного действия «позвать флот»

НЕ трогает bg_strait_map.png и switch_*.png. Запуск:
    python gen_gameplay_assets.py [--out ../client]
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFilter

SS = 3  # суперсэмплинг для гладких краёв


def canvas(w, h):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def finish(img, w, h):
    return img.resize((w, h), Image.LANCZOS)


def hull_poly(x0, y0, x1, y1, bow=0.22, stern_round=0.12):
    """Полигон корпуса: нос (справа) заострён, корма (слева) скруглена."""
    h = y1 - y0
    bx = x1 - (x1 - x0) * bow            # начало носового клина
    pts = [
        (x0 + (x1 - x0) * stern_round, y0),
        (bx, y0),
        (x1, (y0 + y1) / 2),             # кончик носа
        (bx, y1),
        (x0 + (x1 - x0) * stern_round, y1),
        (x0, y1 - h * 0.30),
        (x0, y0 + h * 0.30),
    ]
    return pts


def save(img, out, name):
    img.save(os.path.join(out, "assets", name))


# ---------------------------------------------------------------- корабли
def make_tanker(out):
    W, H = 360, 110
    img = canvas(W, H)
    d = ImageDraw.Draw(img)
    s = SS
    d.polygon([(x * s, y * s) for x, y in hull_poly(6, 14, 354, 96)],
              fill=(70, 48, 52, 255), outline=(24, 18, 20, 255))
    # палуба
    d.polygon([(x * s, y * s) for x, y in hull_poly(20, 26, 336, 84, bow=0.24)],
              fill=(180, 170, 150, 255))
    # трубопровод по центру
    d.rectangle([40 * s, 52 * s, 300 * s, 58 * s], fill=(120, 115, 105, 255))
    # люки танков
    for cx in range(70, 300, 46):
        d.ellipse([(cx - 12) * s, 42 * s, (cx + 12) * s, 68 * s],
                  fill=(150, 140, 122, 255), outline=(90, 84, 74, 255), width=2 * s)
    # надстройка на корме
    d.rectangle([26 * s, 30 * s, 58 * s, 80 * s], fill=(235, 238, 240, 255),
                outline=(60, 66, 72, 255), width=2 * s)
    d.rectangle([30 * s, 36 * s, 54 * s, 50 * s], fill=(70, 90, 110, 255))
    save(finish(img, W, H), out, "tanker.png")


def make_cargo(out):
    W, H = 360, 120
    img = canvas(W, H)
    d = ImageDraw.Draw(img)
    s = SS
    d.polygon([(x * s, y * s) for x, y in hull_poly(6, 16, 354, 104)],
              fill=(40, 58, 96, 255), outline=(18, 26, 44, 255))
    # палуба
    d.polygon([(x * s, y * s) for x, y in hull_poly(20, 28, 338, 92, bow=0.24)],
              fill=(30, 40, 60, 255))
    # контейнеры (ряды разноцветных блоков)
    cols = [(200, 70, 60), (70, 150, 90), (70, 120, 190),
            (210, 180, 70), (180, 90, 160), (90, 170, 170)]
    x = 70
    ci = 0
    while x < 300:
        for row, yy in enumerate(range(36, 86, 16)):
            c = cols[(ci + row) % len(cols)]
            d.rectangle([x * s, yy * s, (x + 26) * s, (yy + 13) * s],
                        fill=c + (255,), outline=(20, 22, 26, 255), width=1 * s)
        x += 30
        ci += 1
    # мостик на корме
    d.rectangle([28 * s, 30 * s, 60 * s, 90 * s], fill=(235, 238, 240, 255),
                outline=(60, 66, 72, 255), width=2 * s)
    d.rectangle([33 * s, 38 * s, 55 * s, 54 * s], fill=(70, 90, 110, 255))
    save(finish(img, W, H), out, "cargo.png")


def make_warship(out):
    W, H = 340, 92
    img = canvas(W, H)
    d = ImageDraw.Draw(img)
    s = SS
    # узкий острый корпус
    d.polygon([(x * s, y * s) for x, y in hull_poly(6, 22, 334, 70, bow=0.30)],
              fill=(92, 100, 110, 255), outline=(40, 46, 54, 255))
    # палуба
    d.polygon([(x * s, y * s) for x, y in hull_poly(18, 30, 320, 62, bow=0.32)],
              fill=(70, 78, 88, 255))
    # надстройка (угловатая)
    d.polygon([(120 * s, 32 * s), (175 * s, 34 * s), (170 * s, 58 * s),
               (120 * s, 60 * s)], fill=(120, 128, 138, 255),
              outline=(50, 56, 64, 255))
    # мачта
    d.line([150 * s, 46 * s, 150 * s, 18 * s], fill=(40, 46, 54, 255), width=3 * s)
    # орудийные башни к носу
    for cx in (210, 250):
        d.ellipse([(cx - 12) * s, 34 * s, (cx + 12) * s, 58 * s],
                  fill=(60, 66, 74, 255), outline=(30, 34, 40, 255), width=2 * s)
        d.rectangle([cx * s, 44 * s, (cx + 26) * s, 48 * s], fill=(40, 46, 54, 255))
    # вертолётная площадка на корме
    d.ellipse([40 * s, 36 * s, 78 * s, 56 * s], outline=(210, 214, 220, 200), width=2 * s)
    d.line([54 * s, 40 * s, 64 * s, 52 * s], fill=(210, 214, 220, 200), width=2 * s)
    d.line([64 * s, 40 * s, 54 * s, 52 * s], fill=(210, 214, 220, 200), width=2 * s)
    save(finish(img, W, H), out, "warship.png")


def make_barge_wreck(out):
    W, H = 320, 130
    big = canvas(W, H)
    d = ImageDraw.Draw(big)
    s = SS
    cx, cy = W / 2, H / 2
    ang = math.radians(-12)                 # крен

    def rot(px, py):
        dx, dy = px - cx, py - cy
        return ((cx + dx * math.cos(ang) - dy * math.sin(ang)) * s,
                (cy + dx * math.sin(ang) + dy * math.cos(ang)) * s)

    # ржавый корпус баржи (накренён)
    hull = [(60, 46), (250, 40), (270, 66), (250, 92), (60, 96), (44, 70)]
    d.polygon([rot(*p) for p in hull], fill=(120, 74, 46, 255),
              outline=(60, 36, 22, 255))
    # ржавые потёки / отсеки
    for hx in range(90, 250, 34):
        d.line([rot(hx, 48), rot(hx, 90)], fill=(80, 48, 30, 255), width=2 * s)
    # вода поверх нижней части (полупрозрачная) — баржа «в воде»
    water = canvas(W, H)
    wd = ImageDraw.Draw(water)
    wd.rectangle([0, int(72 * s), W * s, H * s], fill=(60, 120, 140, 150))
    big.alpha_composite(water)
    # пена/рябь у ватерлинии
    dd = ImageDraw.Draw(big)
    for fx in range(40, 290, 26):
        dd.ellipse([fx * s, int(66 * s), (fx + 20) * s, int(78 * s)],
                   fill=(255, 255, 255, 70))
    save(finish(big, W, H), out, "barge_wreck.png")


# ---------------------------------------------------------------- взрыв
def make_explosion(out):
    W = H = 256
    img = canvas(W, H)
    d = ImageDraw.Draw(img)
    s = SS
    cx = cy = W / 2 * s

    def star(cx, cy, r_out, r_in, n, color, rot=0):
        pts = []
        for i in range(n * 2):
            r = r_out if i % 2 == 0 else r_in
            a = rot + math.pi * i / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        d.polygon(pts, fill=color)

    star(cx, cy, 120 * s, 66 * s, 12, (210, 60, 30, 255), rot=0.1)
    star(cx, cy, 96 * s, 54 * s, 11, (250, 140, 30, 255), rot=0.35)
    star(cx, cy, 70 * s, 40 * s, 10, (255, 210, 60, 255), rot=0.6)
    d.ellipse([cx - 42 * s, cy - 42 * s, cx + 42 * s, cy + 42 * s],
              fill=(255, 248, 210, 255))
    # искры/обломки
    import random
    rnd = random.Random(5)
    for _ in range(16):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(90, 122) * s
        px, py = cx + rr * math.cos(a), cy + rr * math.sin(a)
        d.ellipse([px - 5 * s, py - 5 * s, px + 5 * s, py + 5 * s],
                  fill=(60, 44, 40, 255))
    img = img.filter(ImageFilter.GaussianBlur(1))
    save(finish(img, W, H), out, "explosion.png")


# ---------------------------------------------------------------- иконки
def _waves(d, W, H, s, y):
    for wy, alpha in ((y, 230), (y + 16, 150)):
        pts = []
        for x in range(0, W + 8, 8):
            pts.append((x * s, (wy + 5 * math.sin(x / 12.0)) * s))
        for x in range(W, -8, -8):
            pts.append((x * s, (wy + 22) * s))
        d.polygon(pts, fill=(70, 130, 160, alpha))


def make_icon_sink(out):
    W = H = 128
    img = canvas(W, H)
    d = ImageDraw.Draw(img)
    s = SS
    # тонущий сухогруз (накренён носом вниз)
    cx, cy = 64, 56
    ang = math.radians(28)

    def rot(px, py):
        dx, dy = px - cx, py - cy
        return ((cx + dx * math.cos(ang) - dy * math.sin(ang)) * s,
                (cy + dx * math.sin(ang) + dy * math.cos(ang)) * s)
    d.polygon([rot(*p) for p in [(28, 40), (92, 40), (104, 54), (92, 66), (28, 66), (18, 53)]],
              fill=(60, 70, 96, 255), outline=(26, 30, 44, 255))
    for bx in range(40, 92, 14):
        d.rectangle([rot(bx, 34)[0], rot(bx, 34)[1], rot(bx + 10, 46)[0], rot(bx + 10, 46)[1]],
                    fill=(200, 80, 66, 255))
    _waves(d, W, H, s, 74)
    # пузырьки
    for bx, by, r in ((44, 96, 5), (54, 104, 4), (40, 108, 3)):
        d.ellipse([(bx - r) * s, (by - r) * s, (bx + r) * s, (by + r) * s],
                  outline=(230, 240, 245, 220), width=2 * s)
    save(finish(img, W, H), out, "icon_sink.png")


def make_icon_fleet(out):
    W = H = 128
    img = canvas(W, H)
    d = ImageDraw.Draw(img)
    s = SS
    # силуэт военного корабля (вид сбоку) + вспышки орудий
    d.polygon([(18 * s, 70 * s), (110 * s, 70 * s), (100 * s, 84 * s), (28 * s, 84 * s)],
              fill=(90, 100, 112, 255), outline=(40, 46, 54, 255))          # корпус
    d.rectangle([48 * s, 50 * s, 78 * s, 70 * s], fill=(120, 128, 138, 255),
                outline=(40, 46, 54, 255), width=2 * s)                     # надстройка
    d.line([63 * s, 50 * s, 63 * s, 30 * s], fill=(40, 46, 54, 255), width=3 * s)  # мачта
    # стволы к носу
    d.rectangle([84 * s, 60 * s, 108 * s, 64 * s], fill=(40, 46, 54, 255))
    # вспышки
    for fx in (110, 112):
        d.polygon([(fx * s, 56 * s), ((fx + 14) * s, 62 * s), (fx * s, 68 * s),
                   ((fx + 8) * s, 62 * s)], fill=(255, 210, 70, 255))
    _waves(d, W, H, s, 86)
    save(finish(img, W, H), out, "icon_fleet.png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="../client")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.out, "assets"), exist_ok=True)
    make_tanker(a.out)
    make_cargo(a.out)
    make_warship(a.out)
    make_barge_wreck(a.out)
    make_explosion(a.out)
    make_icon_sink(a.out)
    make_icon_fleet(a.out)
    print("Спрайты механики готовы (карта/рубильник не тронуты).")


if __name__ == "__main__":
    main()
