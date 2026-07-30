(function () {
  "use strict";

  var shared = window.CV && window.CV.theme;
  if (!shared) return;
  var theme = shared.readStoredTheme();
  document.documentElement.setAttribute("data-theme", theme);
  shared.writeStoredTheme(theme);
})();
