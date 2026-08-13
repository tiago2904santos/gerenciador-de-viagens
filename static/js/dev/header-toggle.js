(function () {
  "use strict";

  var ROOT = "[data-main-preview-header-toggle]";
  var ITEM = ".main-preview-header__toggle-item";
  var BOUND = "data-main-preview-header-toggle-bound";

  function activate(root, item) {
    Array.prototype.forEach.call(root.querySelectorAll(ITEM), function (candidate) {
      var isActive = candidate === item;
      candidate.setAttribute("aria-pressed", isActive ? "true" : "false");
      candidate.classList.toggle("main-preview-header__toggle-item--active", isActive);
    });

    var header = root.closest(".main-preview-header--toggle");
    var title = header && header.querySelector(".main-preview-header__title");
    if (title) title.textContent = item.textContent.trim();
  }

  function onClick(event) {
    var item = event.target.closest(ITEM);
    if (!item) return;
    var root = item.closest(ROOT);
    if (!root || !root.contains(item)) return;
    activate(root, item);
  }

  function bind(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var toggles = Array.prototype.slice.call(scope.querySelectorAll(ROOT));
    if (scope.matches && scope.matches(ROOT)) toggles.unshift(scope);
    toggles.forEach(function (toggle) {
      if (toggle.getAttribute(BOUND) === "true") return;
      toggle.setAttribute(BOUND, "true");
      toggle.addEventListener("click", onClick);
    });
  }

  function destroy(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var toggles = Array.prototype.slice.call(scope.querySelectorAll(ROOT));
    if (scope.matches && scope.matches(ROOT)) toggles.unshift(scope);
    toggles.forEach(function (toggle) {
      toggle.removeEventListener("click", onClick);
      toggle.removeAttribute(BOUND);
    });
  }

  window.CV = window.CV || {};
  window.CV.mainPreviewHeaderToggle = { init: bind, destroy: destroy };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("mainPreviewHeaderToggle", bind, destroy);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { bind(document); }, { once: true });
  } else {
    bind(document);
  }
})();
