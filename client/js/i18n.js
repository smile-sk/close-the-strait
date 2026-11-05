/* Локализация: грузит assets/lang/<code>.json и подставляет строки. */
const I18N = (() => {
  let dict = {};
  let lang = "en";

  async function load(code) {
    try {
      const res = await fetch(`assets/lang/${code}.json`, { cache: "no-cache" });
      dict = await res.json();
      lang = code;
      document.documentElement.lang = code;
      document.documentElement.dir = dict.dir || "ltr";
      return true;
    } catch (e) {
      console.error("i18n load failed:", code, e);
      return false;
    }
  }

  // t("last_action", {name:"Иван", status:"ЗАКРЫТО"})
  function t(key, vars) {
    let s = dict[key] != null ? dict[key] : key;
    if (vars) for (const k in vars) s = s.replaceAll(`{${k}}`, vars[k]);
    return s;
  }

  return { load, t, get lang() { return lang; }, get dict() { return dict; } };
})();
