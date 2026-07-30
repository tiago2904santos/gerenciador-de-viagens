(function () {
  "use strict";

  window.CV = window.CV || {};

  var COLLECTION_SELECTOR = "[data-collection]";
  var FILTER_SELECTOR = "[data-collection-filter]";
  var ITEM_SELECTOR = "[data-collection-item]";
  var BOUND = "data-collection-bound";
  var DEBOUNCE_MS = 300;
  var stateByCollection = typeof WeakMap !== "undefined" ? new WeakMap() : new Map();

  function normalize(value) {
    return window.CV.util.normalize(value).trim();
  }

  function collectionsIn(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var collections = Array.prototype.slice.call(scope.querySelectorAll(COLLECTION_SELECTOR));
    if (scope.matches && scope.matches(COLLECTION_SELECTOR)) collections.unshift(scope);
    return collections;
  }

  function filtersIn(collection) {
    return Array.prototype.slice.call(collection.querySelectorAll(FILTER_SELECTOR));
  }

  function readClientFilters(collection) {
    var filters = { searchTerms: [], status: "" };
    filtersIn(collection).forEach(function (input) {
      var role = input.getAttribute("data-collection-filter") || "";
      var value = String(input.value || "").trim();
      if (role === "search") {
        var search = normalize(value);
        filters.searchTerms = search ? search.split(/\s+/).filter(Boolean) : [];
      } else if (role === "status") {
        filters.status = normalize(value);
      }
    });
    return filters;
  }

  function matchesClientFilters(item, filters) {
    var searchText = normalize(item.getAttribute("data-search-text") || item.textContent || "");
    for (var i = 0; i < filters.searchTerms.length; i += 1) {
      if (searchText.indexOf(filters.searchTerms[i]) === -1) return false;
    }
    if (filters.status) {
      return normalize(item.getAttribute("data-status-value") || "") === filters.status;
    }
    return true;
  }

  function updateCount(collection, visible, total) {
    var count = collection.querySelector("[data-collection-count]");
    if (!count) return;
    var template = count.getAttribute("data-collection-count-template");
    count.textContent = template
      ? template.replace(/\{\{visible\}\}/g, String(visible)).replace(/\{\{total\}\}/g, String(total))
      : String(visible);
    count.hidden = false;
  }

  function applyClient(collection) {
    var filters = readClientFilters(collection);
    var items = Array.prototype.slice.call(collection.querySelectorAll(ITEM_SELECTOR));
    var visible = 0;
    items.forEach(function (item) {
      var matches = matchesClientFilters(item, filters);
      item.hidden = !matches;
      if (matches) visible += 1;
    });

    var empty = collection.querySelector("[data-collection-empty]");
    if (empty) empty.hidden = !(items.length && visible === 0);
    updateCount(collection, visible, items.length);

    var state = {
      collection: collection,
      filters: filters,
      hidden: items.length - visible,
      total: items.length,
      visible: visible,
    };
    stateByCollection.set(collection, state);
    collection.dispatchEvent(new CustomEvent("cv:collection:updated", {
      bubbles: true,
      detail: state,
    }));
    return state;
  }

  function clearControls(collection) {
    filtersIn(collection).forEach(function (control) {
      if ((control.tagName || "").toLowerCase() === "select") control.selectedIndex = 0;
      else control.value = "";
    });
  }

  function buildUrl(form) {
    var action = form.getAttribute("action") || window.location.pathname;
    var params = new URLSearchParams();
    new FormData(form).forEach(function (value, key) {
      var text = value == null ? "" : String(value).trim();
      if (text) params.append(key, text);
    });
    var query = params.toString();
    return query ? action + "?" + query : action;
  }

  function swapPanel(collection, htmlText) {
    var nextDocument = new DOMParser().parseFromString(htmlText, "text/html");
    var nextPanel = nextDocument.querySelector(".list-panel");
    var currentPanel = collection.querySelector(".list-panel");
    if (!nextPanel || !currentPanel) return false;
    if (window.CV.registry && typeof window.CV.registry.destroy === "function") {
      window.CV.registry.destroy(currentPanel);
    }
    currentPanel.replaceWith(nextPanel);
    return true;
  }

  function bindClient(collection) {
    var run = window.CV.util.debounce(function () {
      applyClient(collection);
    }, 250);
    filtersIn(collection).forEach(function (control) {
      var eventName = (control.tagName || "").toLowerCase() === "select" ? "change" : "input";
      control.addEventListener(eventName, run);
    });
    collection.querySelectorAll("[data-collection-clear]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        clearControls(collection);
        applyClient(collection);
      });
    });
    applyClient(collection);
  }

  function bindServer(collection) {
    var form = collection.querySelector("[data-collection-form]");
    if (!form || !collection.querySelector(".list-panel")) return false;
    var controls = filtersIn(form);
    if (!controls.length) return false;

    var lastUrl = buildUrl(form);
    var requestId = 0;

    function run() {
      var url = buildUrl(form);
      if (url === lastUrl) return;
      lastUrl = url;
      var active = document.activeElement;
      var keepSelection =
        active && active.tagName === "INPUT" && form.contains(active) &&
        typeof active.selectionStart === "number";
      var selectionStart = keepSelection ? active.selectionStart : null;
      var selectionEnd = keepSelection ? active.selectionEnd : null;
      var currentRequest = ++requestId;

      window.CV.http.fetchText(url, {
        headers: { "X-Requested-With": "fetch" },
      }).then(function (result) {
        if (!result.ok) throw new Error("request_failed");
        if (currentRequest !== requestId) return;
        if (!swapPanel(collection, result.data)) {
          window.location.assign(url);
          return;
        }
        window.history.replaceState({}, "", url);
        if (keepSelection && document.contains(active)) {
          active.focus();
          try {
            active.setSelectionRange(selectionStart, selectionEnd);
          } catch (error) {
            /* input type without selection support */
          }
        }
      }).catch(function () {
        window.location.assign(url);
      });
    }

    var debouncedRun = window.CV.util.debounce(run, DEBOUNCE_MS);
    controls.forEach(function (control) {
      if ((control.tagName || "").toLowerCase() === "select") {
        control.addEventListener("change", run);
      } else {
        control.addEventListener("input", debouncedRun);
        control.addEventListener("change", debouncedRun);
      }
    });
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      run();
    });
    form.querySelectorAll("[data-collection-clear]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.preventDefault();
        clearControls(collection);
        run();
      });
    });
    return true;
  }

  function bind(collection) {
    if (!collection || collection.getAttribute(BOUND) === "true") return false;
    var mode = collection.getAttribute("data-collection-mode");
    if (mode !== "client" && mode !== "server") return false;
    collection.setAttribute(BOUND, "true");
    if (mode === "client") bindClient(collection);
    else if (mode === "server" && !bindServer(collection)) collection.removeAttribute(BOUND);
    return true;
  }

  function init(root) {
    var collections = collectionsIn(root);
    collections.forEach(bind);
    return collections.length;
  }

  function clear(collection) {
    if (!collection) return null;
    clearControls(collection);
    return collection.getAttribute("data-collection-mode") === "client"
      ? applyClient(collection)
      : null;
  }

  window.CV.collection = {
    apply: applyClient,
    clear: clear,
    getState: function (collection) { return stateByCollection.get(collection) || null; },
    init: init,
    matches: matchesClientFilters,
    normalize: normalize,
  };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("collection", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
}());
