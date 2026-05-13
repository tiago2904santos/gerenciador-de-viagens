(function () {
  "use strict";

  var shared = window.CVThemeShared;
  if (!shared) return;

  function applyTheme(theme) {
    if (!shared.isValidTheme(theme)) {
      theme = shared.readStoredTheme();
    }
    document.documentElement.setAttribute("data-theme", theme);
    shared.writeStoredTheme(theme);

    document.querySelectorAll("[data-theme-mode]").forEach(function (btn) {
      var mode = btn.getAttribute("data-theme-mode");
      var checked = mode === theme;
      btn.setAttribute("aria-pressed", checked ? "true" : "false");
      btn.setAttribute("aria-checked", checked ? "true" : "false");
      btn.setAttribute("tabindex", checked ? "0" : "-1");
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var initial = shared.readStoredTheme();
    applyTheme(initial);

    document.querySelectorAll("[data-theme-mode]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var mode = btn.getAttribute("data-theme-mode");
        if (shared.isValidTheme(mode)) {
          applyTheme(mode);
        }
      });

      btn.addEventListener("keydown", function (event) {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        var all = Array.prototype.slice.call(document.querySelectorAll("[data-theme-mode]"));
        var currentIndex = all.indexOf(btn);
        var delta = event.key === "ArrowRight" ? 1 : -1;
        var next = all[(currentIndex + delta + all.length) % all.length];
        if (!next) return;
        next.focus();
        var nextMode = next.getAttribute("data-theme-mode");
        if (shared.isValidTheme(nextMode)) {
          applyTheme(nextMode);
        }
      });
    });

    window.addEventListener("storage", function (event) {
      if (event.key !== shared.STORAGE_KEY) return;
      applyTheme(shared.normalizeTheme(event.newValue));
    });
  });
})();
