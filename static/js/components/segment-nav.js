/**
 * Segment nav (list_toggle): anima a seleção antes de navegar.
 * Links full-page não passam por aria-pressed; sem isso o --pop nunca roda.
 */
(function () {
  "use strict";

  var NAV = ".cv-segment-toggle--nav";
  var BTN = "a.cv-segment-toggle__btn";
  var POP = "cv-segment-toggle__btn--pop";
  var BOUND = "data-cv-segment-nav-bound";
  var DURATION_MS = 280;

  function activate(btn, nav) {
    Array.prototype.forEach.call(nav.querySelectorAll(BTN), function (el) {
      el.removeAttribute("aria-current");
      el.classList.remove(POP);
    });
    btn.setAttribute("aria-current", "page");
    void btn.offsetWidth;
    btn.classList.add(POP);
  }

  function onClick(event) {
    if (event.defaultPrevented) return;
    if (event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    var btn = event.target.closest(BTN);
    if (!btn) return;
    var nav = btn.closest(NAV);
    if (!nav || !nav.contains(btn)) return;
    if (btn.getAttribute("aria-current") === "page") return;

    var href = btn.getAttribute("href");
    if (!href) return;

    event.preventDefault();
    activate(btn, nav);
    window.setTimeout(function () {
      window.location.assign(href);
    }, DURATION_MS);
  }

  function bind(root) {
    var scope = root && root.querySelectorAll ? root : document;
    Array.prototype.forEach.call(scope.querySelectorAll(NAV), function (nav) {
      if (nav.getAttribute(BOUND) === "true") return;
      nav.setAttribute(BOUND, "true");
      nav.addEventListener("click", onClick);
    });
  }

  window.CV = window.CV || {};
  window.CV.segmentNav = { init: bind };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      bind(document);
    });
  } else {
    bind(document);
  }
})();
