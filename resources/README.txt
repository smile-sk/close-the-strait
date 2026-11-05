Исходники для генерации иконки и заставки Android (Capacitor).
  icon.png         — иконка приложения (1024x1024). Замени на финальную при желании.
  splash.png       — заставка (2732x2732), логотип CreaDev Apps по центру.
  splash-dark.png  — то же для тёмной темы.
Логотип на splash.png/splash-dark.png уже отцентрован с большими полями (~34%
ширины) — под равномерным масштабированием он не искажается. Растяжение на
Android шло от режима масштабирования сплеша (по умолчанию FIT_XY — тянет по
обеим осям). Исправлено в capacitor.config.json: "androidScaleType":"CENTER_CROP".
Эти PNG менять не требуется.

Генерация (в корне проекта, после `npx cap add android`):
  npm install @capacitor/assets --save-dev
  npx @capacitor/assets generate --android --iconBackgroundColor "#0e1016" --splashBackgroundColor "#070707"
