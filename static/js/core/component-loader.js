(function () {
  "use strict";

  window.CV = window.CV || {};

  var config = document.querySelector("script[data-cv-lazy-components]");
  var entries = [
    {
      name: "form-components",
      selector: "[data-entity-picker], [data-location-rows], [data-cv-date-picker]",
      sourceAttribute: "data-cv-lazy-form-components-src",
      loadedSelector: 'script[data-cv-component-bundle="forms"]',
    },
    {
      name: "card-toggle",
      selector: "[data-card-toggle]",
      sourceAttribute: "data-cv-lazy-card-toggle-src",
    },
    {
      name: "file-picker",
      selector: "[data-file-picker]",
      sourceAttribute: "data-cv-lazy-file-picker-src",
    },
    {
      name: "attach-signed-modal",
      selector: "[data-attach-signed-modal], [data-attach-signed-trigger]",
      sourceAttribute: "data-cv-lazy-attach-signed-modal-src",
    },
    {
      name: "signature-actions",
      selector: "[data-cv-signature-copy], [data-cv-signature-wa]",
      sourceAttribute: "data-cv-lazy-signature-actions-src",
    },
    {
      name: "extra-download",
      selector: "[data-extra-download-url]",
      sourceAttribute: "data-cv-lazy-extra-download-src",
    },
    {
      name: "wizard-sticky-header",
      selector: "[data-wizard-sticky-header]",
      sourceAttribute: "data-cv-lazy-wizard-sticky-header-src",
    },
  ];
  var requested = Object.create(null);
  var observer = null;

  function containsMatch(root, selector) {
    if (!root) return false;
    if (root.matches && root.matches(selector)) return true;
    return Boolean(root.querySelector && root.querySelector(selector));
  }

  function request(entry) {
    if (requested[entry.name] || !config) return;
    if (entry.loadedSelector && document.querySelector(entry.loadedSelector)) {
      requested[entry.name] = true;
      return;
    }
    var source = config.getAttribute(entry.sourceAttribute);
    if (!source) return;
    requested[entry.name] = true;

    var script = document.createElement("script");
    script.src = source;
    script.async = false;
    script.dataset.cvLazyComponent = entry.name;
    script.addEventListener("error", function () {
      delete requested[entry.name];
      document.dispatchEvent(new CustomEvent("cv:lazy-component-error", {
        detail: { name: entry.name, source: source },
      }));
    }, { once: true });
    document.head.appendChild(script);
  }

  function scan(root) {
    entries.forEach(function (entry) {
      if (containsMatch(root || document, entry.selector)) request(entry);
    });
  }

  function start() {
    scan(document);
    if (observer || typeof MutationObserver !== "function") return;
    observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        Array.prototype.forEach.call(mutation.addedNodes, function (node) {
          if (node.nodeType === 1) scan(node);
        });
      });
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  function destroy() {
    if (!observer) return;
    observer.disconnect();
    observer = null;
  }

  window.CV.lazyComponents = { destroy: destroy, scan: scan };
  start();
}());
