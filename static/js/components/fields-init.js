/**
 * Orquestrador global de campos — máscaras, toggles, selects, pickers, dropdowns.
 */
(function () {
  'use strict';

  var DEBUG = !!window.DEBUG_CV_FIELDS;

  function resolveRoot(root) {
    if (!root) return document;
    if (root.nodeType === 9) return root;
    if (root.nodeType === 1 || root.nodeType === 11) return root;
    return document;
  }

  function safeCall(label, fn) {
    try {
      return fn() || 0;
    } catch (err) {
      if (DEBUG) {
        window.CV.log.warn('CV.fields', label, err);
      }
      return 0;
    }
  }

  function initMasks(root) {
    return safeCall('masks', function () {
      if (window.CV && window.CV.masks && typeof window.CV.masks.scan === 'function') {
        window.CV.masks.scan(root);
        return 1;
      }
      return 0;
    });
  }

  function initStateToggles(root) {
    return safeCall('stateToggle', function () {
      if (window.CV && window.CV.stateToggle && typeof window.CV.stateToggle.init === 'function') {
        window.CV.stateToggle.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initSelects(root) {
    return safeCall('pickerSelect', function () {
      var api = window.CV && window.CV.picker;
      if (api && typeof api.initSelect === 'function') {
        api.initSelect(root);
        return 1;
      }
      return 0;
    });
  }

  function initSearchPickers(root) {
    return safeCall('pickerSearch', function () {
      var api = window.CV && window.CV.picker;
      if (api && typeof api.initSearch === 'function') {
        api.initSearch(root);
        return 1;
      }
      return 0;
    });
  }

  function initDatePickers(root) {
    return safeCall('datePicker', function () {
      var api = window.CV && window.CV.datePicker;
      if (api && typeof api.init === 'function') {
        api.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initMultiselects(root) {
    return safeCall('multiselect', function () {
      var api = window.CV && window.CV.multiselect;
      if (api && typeof api.init === 'function') {
        api.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initFilterableMultiselects(root) {
    return safeCall('filterableMultiselect', function () {
      var api = window.CV && window.CV.filterableMultiselect;
      if (api && typeof api.init === 'function') {
        api.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initSegmentNav(root) {
    return safeCall('segmentNav', function () {
      if (window.CV && window.CV.segmentNav && typeof window.CV.segmentNav.init === 'function') {
        window.CV.segmentNav.init(root);
        return 1;
      }
      return 0;
    });
  }

  var resumoDeErrosJaFocado = false;

  /**
   * `HT-03`: leva o foco ao resumo de erro do formulário.
   *
   * `role="alert"` sozinho não resolve: região viva anuncia **mudança**, e o
   * resumo já está no HTML quando a página carrega — o comportamento varia por
   * leitor de tela e não dá para contar com ele. Mover o foco para o resumo é o
   * que garante que quem submeteu chegue à mensagem, e é o padrão de resumo de
   * erro do WCAG.
   *
   * Uma vez por carga de página, e não uma vez por passada do enhancer: `init`
   * roda de novo a cada re-render parcial, e roubar o foco no meio da digitação
   * seria pior que o defeito. A trava é a variável de módulo, que morre com a
   * página.
   */
  function initResumoDeErros(root) {
    return safeCall('formErrors', function () {
      if (resumoDeErrosJaFocado) return 0;
      var resumo = resolveRoot(root).querySelector('[data-form-errors]');
      if (!resumo) return 0;
      resumoDeErrosJaFocado = true;
      resumo.focus();
      return 1;
    });
  }

  function emitInit(root, counts) {
    try {
      root.dispatchEvent(
        new CustomEvent('cv:fields:init', {
          bubbles: true,
          detail: {
            root: root,
            initialized: counts,
          },
        })
      );
    } catch (e) {
      /* ignore */
    }
  }

  function init(root) {
    var scope = resolveRoot(root);
    var counts = {
      masks: initMasks(scope),
      stateToggles: initStateToggles(scope),
      segmentNav: initSegmentNav(scope),
      selects: initSelects(scope),
      searchPickers: initSearchPickers(scope),
      datePickers: initDatePickers(scope),
      multiselects: initMultiselects(scope),
      filterableMultiselects: initFilterableMultiselects(scope),
      resumoDeErros: initResumoDeErros(scope),
    };
    emitInit(scope, counts);
    return counts;
  }

  var fieldsApi = {
    init: init,
    initSelects: initSelects,
    initSearchPickers: initSearchPickers,
    initDatePickers: initDatePickers,
    initMultiselects: initMultiselects,
  };

  window.CV = window.CV || {};
  window.CV.fields = fieldsApi;
  window.CV.initFields = init;

  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('fields', init);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(document); });
  } else {
    init(document);
  }
})();
