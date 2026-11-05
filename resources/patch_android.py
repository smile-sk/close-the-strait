#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Патч Android-проекта Capacitor под «Close The Strait!».
Запускать ИЗ КОРНЯ проекта ПОСЛЕ `npx cap add android`
(и, если гонял, после `npx @capacitor/assets generate ...`):

    python3 resources/patch_android.py

Что делает (идемпотентно — можно запускать повторно):
  1) Блокирует ориентацию активности в ПОРТРЕТ (android:screenOrientation).
  2) Убирает растяжение логотипа на ПЕРВОМ кадре запуска: тема запуска по
     умолчанию рисует splash.png как windowBackground, а Android тянет bitmap
     на весь экран (отсюда «плющит»). Ставим сплошной цвет #070707 — логотип
     покажет центрированно плагин SplashScreen (androidScaleType=CENTER_CROP из
     capacitor.config.json) и веб-заставка #splash в index.html.

Папка android/ пересоздаётся `cap add android`, поэтому скрипт — шаг после
каждой чистой генерации (или не пересоздавай android/ без нужды).
"""
import re, sys, pathlib

SPLASH_HEX = "#FF070707"   # ARGB, #070707 непрозрачный (как в resources/splash*.png)

root = pathlib.Path("android/app/src/main")
if not root.exists():
    sys.exit("[patch_android] Нет android/app/src/main — сначала `npx cap add android`.")

# ---------- 1. Портретная ориентация в манифесте ----------
manifest = root / "AndroidManifest.xml"
m = manifest.read_text(encoding="utf-8")
if "android:screenOrientation" not in m:
    # активность-лаунчер (обычно *.MainActivity)
    m2 = re.sub(
        r'(<activity\b(?:(?!</activity>).)*?android:name="[^"]*MainActivity"[^>]*?)>',
        r'\1\n            android:screenOrientation="portrait">',
        m, count=1, flags=re.S)
    if m2 == m:                                   # запасной вариант: первая <activity>
        m2 = re.sub(r'(<activity\b)',
                    r'\1 android:screenOrientation="portrait"', m, count=1)
    manifest.write_text(m2, encoding="utf-8")
    print("[patch_android] манифест: android:screenOrientation=portrait добавлен")
else:
    print("[patch_android] манифест: ориентация уже задана — пропуск")

# ---------- 1b. Разрешение Google Play Billing (для @capgo/native-purchases) ----------
m = manifest.read_text(encoding="utf-8")
if "com.android.vending.BILLING" not in m:
    perm = '    <uses-permission android:name="com.android.vending.BILLING" />\n'
    m2 = re.sub(r'(\n\s*<application\b)', "\n" + perm + r"\1", m, count=1)
    if m2 == m:                                   # запасной вариант: после <manifest ...>
        m2 = re.sub(r'(<manifest\b[^>]*>)', r'\1\n' + perm, m, count=1)
    manifest.write_text(m2, encoding="utf-8")
    print("[patch_android] манифест: разрешение BILLING добавлено")
else:
    print("[patch_android] манифест: разрешение BILLING уже есть — пропуск")

# ---------- 2. Сплошной цвет фона заставки ----------
res = root / "res"

colors = res / "values" / "colors.xml"
if colors.exists():
    col = colors.read_text(encoding="utf-8")
else:
    col = '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n</resources>\n'
if 'name="splash_bg"' not in col:
    col = col.replace("</resources>",
                      f'    <color name="splash_bg">{SPLASH_HEX}</color>\n</resources>')
    colors.parent.mkdir(parents=True, exist_ok=True)
    colors.write_text(col, encoding="utf-8")
    print("[patch_android] colors.xml: добавлен splash_bg")
else:
    print("[patch_android] colors.xml: splash_bg уже есть — пропуск")

patched = False
for styles in res.glob("values*/styles.xml"):
    s = styles.read_text(encoding="utf-8")
    orig = s
    # windowBackground / background со splash-картинкой -> цвет (первый кадр)
    s = re.sub(
        r'(<item name="android:(?:windowBackground|background)">)\s*@drawable/splash\s*(</item>)',
        r'\1@color/splash_bg\2', s)
    # Android 12 splash background -> тот же цвет
    s = re.sub(
        r'(<item name="(?:android:)?windowSplashScreenBackground">)[^<]*(</item>)',
        r'\1@color/splash_bg\2', s)
    if s != orig:
        styles.write_text(s, encoding="utf-8")
        patched = True
        print(f"[patch_android] {styles.relative_to(root)}: фон заставки -> сплошной цвет")

if not patched:
    print("[patch_android] styles.xml: растянутого @drawable/splash не найдено "
          "(уже цвет или другой шаблон) — проверь вручную, если растяжение осталось")

print("[patch_android] Готово. Пересобери: cd android && ./gradlew assembleDebug")
