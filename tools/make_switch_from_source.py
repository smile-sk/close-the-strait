#!/usr/bin/env python3
"""Из ОДНОГО рендера рубильника делает ДВА состояния для игры.

Берёт картинку рубильника (по умолчанию tools/source_switch.jpg) в положении
«рычаг влево, красное свечение», и создаёт:
  tools/switch_close.png  — как есть (ЗАКРЫТО: красный, рычаг влево)
  tools/switch_open.png   — зеркально + свечение перекрашено в зелёный
                            (ОТКРЫТО: зелёный, рычаг вправо)
Фон (светло-серый/белый) удаляется в прозрачность.

Потом эти два файла подхватывает gen_placeholders.py (копирует в client/assets),
либо скопируй их в client/assets/ вручную под именами
switch_toggle_close.png / switch_toggle_open.png.

Требуется: pillow, numpy, scipy.
    pip install pillow numpy scipy
Запуск:
    python make_switch_from_source.py [путь_к_рендеру.jpg]

Если рычаг на твоём рендере уже смотрит ВПРАВО или свечение другого цвета —
поменяй флаги MIRROR_FOR_OPEN / RECOLOR ниже.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageOps, ImageFilter
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))

# --- настройки ---
TARGET_WIDTH = 800          # ширина итоговых PNG (в игре тянется по ширине)
BG_BRIGHT = 120             # фон считаем «светлым», если яркость выше
BG_SAT = 45                 # ...и малонасыщенным (серый/белый)
MIRROR_FOR_OPEN = True      # отзеркалить для состояния OPEN (рычаг в другую сторону)
RECOLOR_OPEN_TO_GREEN = True  # перекрасить красное свечение в зелёное для OPEN
GREEN_HUE = 90              # тон зелёного в шкале PIL HSV (0..255); 90 ≈ 127°


def cut_background(src):
    """Удаляет внешний светлый фон (связанный с рамкой) в прозрачность."""
    a = np.asarray(src.convert("RGB")).astype(np.int16)
    bright = a.mean(axis=2)
    sat = a.max(axis=2) - a.min(axis=2)
    bg_cand = (bright > BG_BRIGHT) & (sat < BG_SAT)
    lbl, _ = ndimage.label(bg_cand)
    border = set(np.unique(np.concatenate(
        [lbl[0, :], lbl[-1, :], lbl[:, 0], lbl[:, -1]])))
    border.discard(0)
    bg = np.isin(lbl, list(border))
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    al = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3))  # эрозия 1px
    al = al.filter(ImageFilter.GaussianBlur(0.6))                 # сглаживание
    out = src.convert("RGBA")
    out.putalpha(al)
    return out.crop(out.getbbox())


def recolor_red_to_green(img):
    rgba = np.asarray(img).copy()
    hsv = np.asarray(Image.fromarray(rgba[..., :3], "RGB").convert("HSV")).astype(np.int16)
    Hh, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    red = ((Hh < 16) | (Hh > 240)) & (S > 60) & (V > 40)
    hsv[..., 0] = np.where(red, GREEN_HUE, Hh)
    rgb = np.asarray(Image.fromarray(hsv.astype("uint8"), "HSV").convert("RGB"))
    return Image.fromarray(np.dstack([rgb, rgba[..., 3]]), "RGBA")


def main():
    src_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "source_switch.jpg")
    if not os.path.exists(src_path):
        sys.exit(f"Не найден исходник: {src_path}")

    cut = cut_background(Image.open(src_path))
    w, h = cut.size
    cut = cut.resize((TARGET_WIDTH, round(h * TARGET_WIDTH / w)), Image.LANCZOS)

    # CLOSED — как есть
    cut.save(os.path.join(HERE, "switch_close.png"), optimize=True)

    # OPEN — зеркало + зелёный
    op = ImageOps.mirror(cut) if MIRROR_FOR_OPEN else cut.copy()
    if RECOLOR_OPEN_TO_GREEN:
        op = recolor_red_to_green(op)
    op.save(os.path.join(HERE, "switch_open.png"), optimize=True)

    print("Готово:")
    print("  tools/switch_close.png  (ЗАКРЫТО)")
    print("  tools/switch_open.png   (ОТКРЫТО)")
    print("Дальше: python gen_placeholders.py --out ../client  (скопирует их в игру)")


if __name__ == "__main__":
    main()
