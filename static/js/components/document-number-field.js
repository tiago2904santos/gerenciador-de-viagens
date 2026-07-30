(function () {
  function onlyDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function resolveYear(wrapper, hidden) {
    const raw =
      (wrapper && wrapper.dataset.documentYear) ||
      (hidden && hidden.dataset.documentYear) ||
      (hidden && hidden.dataset.maskYear) ||
      "";
    const y = parseInt(String(raw), 10);
    if (y >= 1900 && y <= 2100) {
      return y;
    }
    return new Date().getFullYear();
  }

  function parseNumeroFromHidden(hidden) {
    const v = (hidden.value || "").trim();
    if (!v) {
      return "";
    }
    const head = v.split("/")[0];
    return onlyDigits(head).slice(0, 3);
  }

  function syncFromHidden(wrapper) {
    const hidden = wrapper.querySelector("[data-document-number-value]");
    const num = wrapper.querySelector("[data-document-number-input]");
    if (!hidden || !num) {
      return;
    }
    num.value = parseNumeroFromHidden(hidden);
  }

  function syncToHidden(wrapper) {
    const hidden = wrapper.querySelector("[data-document-number-value]");
    const num = wrapper.querySelector("[data-document-number-input]");
    if (!hidden || !num) {
      return;
    }
    const year = resolveYear(wrapper, hidden);
    let digits = onlyDigits(num.value).slice(0, 3);
    num.value = digits;
    hidden.value = digits ? `${digits}/${year}` : "";
    hidden.dispatchEvent(new Event("input", { bubbles: true }));
    hidden.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function initWrapper(wrapper) {
    if (wrapper.dataset.documentNumberBound === "true") {
      return;
    }
    const hidden = wrapper.querySelector("[data-document-number-value]");
    const num = wrapper.querySelector("[data-document-number-input]");
    if (!hidden || !num) {
      return;
    }
    wrapper.dataset.documentNumberBound = "true";
    syncFromHidden(wrapper);
    ["input", "blur"].forEach(function (ev) {
      num.addEventListener(ev, function () {
        syncToHidden(wrapper);
      });
    });
  }

  function init(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (scope.matches && scope.matches("[data-document-number-field]")) {
      initWrapper(scope);
    }
    scope.querySelectorAll("[data-document-number-field]").forEach(initWrapper);
  }

  window.CV = window.CV || {};
  window.CV.documentNumberField = { init: init };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("documentNumberField", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
})();
