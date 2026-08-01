(function () {
  "use strict";

  var DETACHED = "is-detached";
  var ROOT = "[data-wizard-sticky-header]";
  var BAND = "[data-wizard-sticky-band]";
  var STEPPER = "[data-wizard-sticky-stepper]";
  var SENTINEL = "[data-wizard-sticky-sentinel]";

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function applyMotion(el) {
    if (!el) return;
    if (prefersReducedMotion()) {
      el.style.transition = "none";
    } else {
      el.style.removeProperty("transition");
    }
  }

  function syncDetached(root, band, stepper, detached) {
    var on = Boolean(detached);
    if (band) {
      band.classList.toggle(DETACHED, on);
      applyMotion(band);
    }
    if (stepper) {
      stepper.classList.toggle(DETACHED, on);
      applyMotion(stepper);
    }
    root.classList.toggle(DETACHED, on);
  }

  function measureDetached(band, stepper) {
    var bandBottom = band.getBoundingClientRect().bottom;
    var stepperTop = stepper.getBoundingClientRect().top;
    return bandBottom < stepperTop - 0.5;
  }

  function bind(root) {
    if (!root || root.dataset.wizardStickyBound === "true") return;
    var band = root.querySelector(BAND);
    var stepper = root.querySelector(STEPPER);
    var sentinel = root.querySelector(SENTINEL);
    if (!band || !stepper) return;

    root.dataset.wizardStickyBound = "true";

    var ticking = false;
    var observer = null;

    function update() {
      ticking = false;
      syncDetached(root, band, stepper, measureDetached(band, stepper));
    }

    function requestUpdate() {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(update);
    }

    update();

    window.addEventListener("scroll", requestUpdate, { passive: true, capture: true });
    document.addEventListener("scroll", requestUpdate, { passive: true, capture: true });
    window.addEventListener("resize", requestUpdate, { passive: true });

    if (sentinel && typeof IntersectionObserver === "function") {
      observer = new IntersectionObserver(function () {
        requestUpdate();
      }, { threshold: [0, 0.01, 1] });
      observer.observe(sentinel);
      observer.observe(band);
    }

    root._wizardStickyCleanup = function () {
      window.removeEventListener("scroll", requestUpdate, { capture: true });
      document.removeEventListener("scroll", requestUpdate, { capture: true });
      window.removeEventListener("resize", requestUpdate);
      if (observer) {
        observer.disconnect();
        observer = null;
      }
    };
  }

  function matching(root, selector) {
    var scope = root && root.querySelectorAll ? root : document;
    var matches = Array.from(scope.querySelectorAll(selector));
    if (scope.matches && scope.matches(selector)) matches.unshift(scope);
    return matches;
  }

  function init(root) {
    matching(root, ROOT).forEach(bind);
  }

  function destroy(root) {
    matching(root, ROOT).forEach(function (node) {
      if (typeof node._wizardStickyCleanup === "function") {
        node._wizardStickyCleanup();
        delete node._wizardStickyCleanup;
      }
      delete node.dataset.wizardStickyBound;
    });
  }

  window.CV = window.CV || {};
  window.CV.wizardStickyHeader = { init: init, destroy: destroy };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("wizardStickyHeader", init, destroy);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }
})();
