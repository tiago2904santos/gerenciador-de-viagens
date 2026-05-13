(function () {
  "use strict";

  var shared = window.CVThemeShared;
  if (!shared) return;
  var theme = shared.readStoredTheme();
  document.documentElement.setAttribute("data-theme", theme);
  shared.writeStoredTheme(theme);
})();
