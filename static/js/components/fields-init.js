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
        console.warn('[CV.fields]', label, err);
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
      if (window.MaskEngine && typeof window.MaskEngine.scan === 'function') {
        window.MaskEngine.scan(root);
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
    return safeCall('customSelect', function () {
      var api = (window.CV && window.CV.customSelect) || window.CvCustomSelect;
      if (api && typeof api.init === 'function') {
        api.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initSearchPickers(root) {
    return safeCall('searchPicker', function () {
      var api = (window.CV && window.CV.searchPicker) || window.CvSearchPicker;
      if (api && typeof api.init === 'function') {
        api.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initDatePickers(root) {
    return safeCall('datePicker', function () {
      var api = (window.CV && window.CV.datePicker) || window.CvDatePicker;
      if (api && typeof api.init === 'function') {
        api.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initDropdowns(root) {
    return safeCall('dropdowns', function () {
      var api = (window.CV && window.CV.dropdowns) || window.CvSelect;
      if (api && typeof api.init === 'function') {
        api.init(root);
        return 1;
      }
      return 0;
    });
  }

  function initMultiselects(root) {
    return safeCall('multiselect', function () {
      var api = (window.CV && window.CV.multiselect) || window.AppMultiselect;
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
      selects: initSelects(scope),
      searchPickers: initSearchPickers(scope),
      datePickers: initDatePickers(scope),
      dropdowns: initDropdowns(scope),
      multiselects: initMultiselects(scope),
      filterableMultiselects: initFilterableMultiselects(scope),
    };
    emitInit(scope, counts);
    return counts;
  }

  var fieldsApi = {
    init: init,
    initSelects: initSelects,
    initSearchPickers: initSearchPickers,
    initDatePickers: initDatePickers,
    initDropdowns: initDropdowns,
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
