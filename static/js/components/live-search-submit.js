(function () {
  'use strict';

  // Motor de filtro padrão das listas (server-side).
  // Contrato: <form data-cv-live-submit-form> contendo controles [data-cv-filter].
  // Ao digitar/selecionar, busca a página filtrada e troca o .list-panel,
  // preservando o foco/cursor para não cortar a digitação. Quando não há
  // .list-panel substituível, deixa o envio nativo (GET) acontecer.
  var FORM_SELECTOR = '[data-cv-live-submit-form]';
  var FORM_BOUND = 'data-cv-live-submit-bound';
  var FILTER_SELECTOR = '[data-cv-filter]';
  var LIST_PANEL_SELECTOR = '.list-panel';
  var DEBOUNCE_MS = 300;

  function debounce(fn, delay) {
    var timer = null;
    return function () {
      var args = arguments;
      var ctx = this;
      if (timer) window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        timer = null;
        fn.apply(ctx, args);
      }, delay);
    };
  }

  function hasListPanel() {
    return !!document.querySelector(LIST_PANEL_SELECTOR);
  }

  function buildUrl(form) {
    var action = form.getAttribute('action') || window.location.pathname;
    var formData = new FormData(form);
    var params = new URLSearchParams();
    formData.forEach(function (value, key) {
      if (value == null) return;
      var text = String(value).trim();
      if (!text) return;
      params.append(key, text);
    });
    var query = params.toString();
    return query ? action + '?' + query : action;
  }

  function swapListPanel(htmlText) {
    var parser = new DOMParser();
    var nextDoc = parser.parseFromString(htmlText, 'text/html');
    var nextPanel = nextDoc.querySelector(LIST_PANEL_SELECTOR);
    var currentPanel = document.querySelector(LIST_PANEL_SELECTOR);
    if (!nextPanel || !currentPanel) return false;
    currentPanel.replaceWith(nextPanel);
    return true;
  }

  function bindForm(form) {
    if (!form || form.getAttribute(FORM_BOUND) === 'true') return;

    var controls = Array.prototype.slice.call(form.querySelectorAll(FILTER_SELECTOR));
    if (!controls.length) return;
    // Só assume a busca quando há painel substituível na página; caso
    // contrário deixa o GET nativo cuidar do filtro.
    if (!hasListPanel()) return;

    form.setAttribute(FORM_BOUND, 'true');

    var lastUrl = buildUrl(form);
    var requestId = 0;

    function run() {
      var url = buildUrl(form);
      if (url === lastUrl) return;
      lastUrl = url;

      var activeEl = document.activeElement;
      var keepFocus =
        activeEl &&
        activeEl.tagName === 'INPUT' &&
        form.contains(activeEl) &&
        typeof activeEl.selectionStart === 'number';
      var selStart = keepFocus ? activeEl.selectionStart : null;
      var selEnd = keepFocus ? activeEl.selectionEnd : null;

      var currentRequest = ++requestId;

      window.CV.http
        .fetchText(url, {
          headers: { 'X-Requested-With': 'fetch' },
        })
        .then(function (result) {
          if (!result.ok) throw new Error('request_failed');
          var htmlText = result.data;
          if (currentRequest !== requestId) return;
          if (!swapListPanel(htmlText)) {
            window.location.assign(url);
            return;
          }
          window.history.replaceState({}, '', url);
          if (keepFocus && document.contains(activeEl)) {
            activeEl.focus();
            if (activeEl.setSelectionRange) {
              try {
                activeEl.setSelectionRange(selStart, selEnd);
              } catch (e) {
                /* ignore */
              }
            }
          }
        })
        .catch(function () {
          window.location.assign(url);
        });
    }

    var debouncedRun = debounce(run, DEBOUNCE_MS);

    controls.forEach(function (control) {
      var tag = (control.tagName || '').toLowerCase();
      if (tag === 'select') {
        control.addEventListener('change', run);
      } else {
        control.addEventListener('input', debouncedRun);
        control.addEventListener('change', debouncedRun);
      }
    });

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      run();
    });

    // Botão "Limpar filtros" dentro/associado ao form.
    var clearButtons = Array.prototype.slice.call(form.querySelectorAll('[data-cv-filter-clear]'));
    clearButtons.forEach(function (btn) {
      btn.addEventListener('click', function (event) {
        event.preventDefault();
        controls.forEach(function (control) {
          if ((control.tagName || '').toLowerCase() === 'select') {
            control.selectedIndex = 0;
          } else {
            control.value = '';
          }
        });
        run();
      });
    });
  }

  function init(root) {
    var scope = root && root.querySelectorAll ? root : document;
    if (!hasListPanel()) return;
    if (scope.matches && scope.matches(FORM_SELECTOR)) bindForm(scope);
    scope.querySelectorAll(FORM_SELECTOR).forEach(bindForm);
  }

  window.CV = window.CV || {};
  window.CV.liveSearch = { init: init };

  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('liveSearch', init);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      init(document);
    });
  } else {
    init(document);
  }
})();
