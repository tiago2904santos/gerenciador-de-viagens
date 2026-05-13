(function (global) {
  "use strict";

  var STORAGE_KEY = "cv-theme";
  var VALID_THEMES = ["dark-dark", "light-dark", "dark-light", "light-light"];
  var LEGACY_THEMES = {
    "dark-dark": "dark",
    "light-dark": "dark",
    "dark-light": "dark",
    "light-light": "light",
    "variant-a": "dark",
    "variant-b": "light",
    dark: "dark",
    light: "light",
  };

  function getSystemPreferredTheme() {
    return global.matchMedia("(prefers-color-scheme: dark)").matches ? "dark-dark" : "light-light";
  }

  function normalizeTheme(rawTheme) {
    if (typeof rawTheme !== "string" || !rawTheme) {
      return getSystemPreferredTheme();
    }
    if (isValidTheme(rawTheme)) return rawTheme;
    if (rawTheme === "dark" || rawTheme === "variant-a") return "dark-dark";
    if (rawTheme === "light" || rawTheme === "variant-b") return "light-light";
    if (LEGACY_THEMES[rawTheme] === "dark") return "dark-dark";
    if (LEGACY_THEMES[rawTheme] === "light") return "light-light";
    return getSystemPreferredTheme();
  }

  function isValidTheme(theme) {
    return VALID_THEMES.indexOf(theme) >= 0;
  }

  function readStoredTheme() {
    try {
      return normalizeTheme(global.localStorage.getItem(STORAGE_KEY));
    } catch (e) {
      return getSystemPreferredTheme();
    }
  }

  function writeStoredTheme(theme) {
    try {
      global.localStorage.setItem(STORAGE_KEY, normalizeTheme(theme));
    } catch (e) {}
  }

  global.CVThemeShared = {
    STORAGE_KEY: STORAGE_KEY,
    VALID_THEMES: VALID_THEMES,
    normalizeTheme: normalizeTheme,
    isValidTheme: isValidTheme,
    readStoredTheme: readStoredTheme,
    writeStoredTheme: writeStoredTheme,
  };
})(window);
