(function () {
  "use strict";

  window.CV = window.CV || {};

  var config = document.querySelector("script[data-cv-lazy-components]");
  var entries = [
    {
      name: "card-toggle",
      selector: "[data-card-toggle]",
      sourceAttribute: "data-cv-lazy-card-toggle-src",
    },
    {
      name: "segment-nav",
      selector: ".segment-toggle--nav",
      sourceAttribute: "data-cv-lazy-segment-nav-src",
    },
    {
      name: "file-picker",
      selector: "[data-file-picker]",
      sourceAttribute: "data-cv-lazy-file-picker-src",
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
