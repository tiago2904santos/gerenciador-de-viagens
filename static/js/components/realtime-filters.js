/**
 * Filtros em tempo real — Central de Viagens
 * Contrato: data-cv-realtime-filter-scope, data-cv-filter, data-cv-filter-item, etc.
 */
(function () {
  'use strict';

  var BOUND = 'data-cv-filter-bound';
  var scopeStore = typeof WeakMap !== 'undefined' ? new WeakMap() : null;
  var scopeStateFallback = typeof WeakMap === 'undefined' ? new Map() : null;

  function resolveRoot(root) {
    if (!root) return document;
    if (root.nodeType === 9 || root.nodeType === 1 || root.nodeType === 11) return root;
    return document;
  }

  function searchTerms(query) {
    var norm = window.CV.util.normalize(query).trim();
    if (!norm) return [];
    return norm.split(/\s+/).filter(Boolean);
  }

  function readFilters(scope) {
    var filters = { search: '', status: '' };
    var filterInputs = scope.querySelectorAll('[data-cv-filter]');
    Array.prototype.forEach.call(filterInputs, function (input) {
      var type = input.getAttribute('data-cv-filter') || input.dataset.cvFilter || '';
      var value = (input.value || '').trim();
      if (type === 'search') {
        filters.searchRaw = value;
        filters.search = window.CV.util.normalize(value).trim();
        filters.searchTerms = searchTerms(value);
      } else if (type === 'status') {
        filters.status = value;
        filters.statusNorm = value ? window.CV.util.normalize(value).trim() : '';
      }
    });
    return filters;
  }

  function matchesFilter(item, filters) {
    if (filters.searchTerms && filters.searchTerms.length) {
      var searchText = window.CV.util.normalize(item.getAttribute('data-search-text') || item.textContent || '').trim();
      for (var i = 0; i < filters.searchTerms.length; i++) {
        if (searchText.indexOf(filters.searchTerms[i]) === -1) {
          return false;
        }
      }
    }

    if (filters.status) {
      var statusValue = window.CV.util.normalize(item.getAttribute('data-status-value') || '').trim();
      if (!statusValue || statusValue !== filters.statusNorm) {
        return false;
      }
    }

    return true;
  }

  function updateCountEl(countEl, visibleCount, totalCount) {
    if (!countEl) return;
    var template = countEl.getAttribute('data-cv-results-count-template') || countEl.dataset.cvResultsCountTemplate;
    if (template) {
      countEl.textContent = template
        .replace(/\{\{visible\}\}/g, String(visibleCount))
        .replace(/\{\{total\}\}/g, String(totalCount));
    } else {
      countEl.textContent = String(visibleCount);
    }
    if (countEl.hasAttribute('hidden') && visibleCount >= 0) {
      countEl.removeAttribute('hidden');
    }
  }

  function emitUpdated(scope, detail) {
    try {
      scope.dispatchEvent(
        new CustomEvent('cv:filters:updated', {
          bubbles: true,
          detail: detail,
        })
      );
    } catch (e) {
      /* ignore */
    }
  }

  function applyFilters(scope) {
    if (!scope || !scope.querySelectorAll) {
      return { total: 0, visible: 0, hidden: 0, state: readFilters(scope || document) };
    }

    var filters = readFilters(scope);
    var items = Array.prototype.slice.call(scope.querySelectorAll('[data-cv-filter-item]'));
    var visibleCount = 0;

    items.forEach(function (item) {
      if (matchesFilter(item, filters)) {
        item.hidden = false;
        item.removeAttribute('hidden');
        visibleCount++;
      } else {
        item.hidden = true;
      }
    });

    updateCountEl(scope.querySelector('[data-cv-results-count]'), visibleCount, items.length);

    var emptyState = scope.querySelector('[data-cv-empty-state]');
    if (emptyState) {
      if (items.length > 0 && visibleCount === 0) {
        emptyState.hidden = false;
        emptyState.removeAttribute('hidden');
      } else {
        emptyState.hidden = true;
      }
    }

    var result = {
      scope: scope,
      total: items.length,
      visible: visibleCount,
      hidden: Math.max(0, items.length - visibleCount),
      state: filters,
    };

    if (scopeStore) {
      scopeStore.set(scope, result);
    } else if (scopeStateFallback) {
      scopeStateFallback.set(scope, result);
    }

    emitUpdated(scope, result);
    return result;
  }

  function clear(scope) {
    if (!scope) return applyFilters(document);
    var filterInputs = scope.querySelectorAll('[data-cv-filter]');
    Array.prototype.forEach.call(filterInputs, function (input) {
      input.value = '';
    });
    return applyFilters(scope);
  }

  function getState(scope) {
    if (!scope) return null;
    if (scopeStore && scopeStore.has(scope)) {
      return scopeStore.get(scope);
    }
    if (scopeStateFallback && scopeStateFallback.has(scope)) {
      return scopeStateFallback.get(scope);
    }
    return applyFilters(scope);
  }

  function update(scope) {
    return applyFilters(scope);
  }

  function bindScope(scope) {
    if (!scope || scope.getAttribute(BOUND) === 'true') {
      return false;
    }
    // Cede o controle quando o motor server-side (live-search-submit) é o
    // responsável pelo filtro neste escopo: evita os dois motores brigando.
    if (scope.querySelector && scope.querySelector('[data-cv-live-submit-form]')) {
      scope.setAttribute(BOUND, 'true');
      return false;
    }
    scope.setAttribute(BOUND, 'true');

    var filterInputs = Array.prototype.slice.call(scope.querySelectorAll('[data-cv-filter]'));

    filterInputs.forEach(function (input) {
      var tagName = (input.tagName || '').toLowerCase();
      var isSelect = tagName === 'select';
      var isText =
        tagName === 'input' &&
        (input.type === 'text' || input.type === 'search' || input.type === '');

      if (isText) {
        var debouncedApply = window.CV.util.debounce(function () {
          applyFilters(scope);
        }, 250);
        input.addEventListener('input', debouncedApply);
      } else if (isSelect) {
        input.addEventListener('change', function () {
          applyFilters(scope);
        });
      }
    });

    var clearButtons = Array.prototype.slice.call(scope.querySelectorAll('[data-cv-filter-clear]'));
    clearButtons.forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        clear(scope);
      });
    });

    applyFilters(scope);
    return true;
  }

  function findScopes(root) {
    var scope = resolveRoot(root);
    if (scope.matches && scope.matches('[data-cv-realtime-filter-scope]')) {
      return [scope];
    }
    return Array.prototype.slice.call(
      scope.querySelectorAll('[data-cv-realtime-filter-scope]')
    );
  }

  function init(root) {
    var scopes = findScopes(root);
    scopes.forEach(bindScope);
    return scopes.length;
  }

  var filtersApi = {
    init: init,
    update: update,
    clear: clear,
    getState: getState,
    applyFilters: applyFilters,
    normalizeText: normalizeText,
    matchesFilter: matchesFilter,
  };

  window.CV = window.CV || {};
  window.CV.filters = filtersApi;

  window.CVRealtimeFilters = {
    init: init,
    applyFilters: applyFilters,
    update: update,
    clear: clear,
    getState: getState,
    normalizeText: normalizeText,
    matchesFilter: matchesFilter,
  };

  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('realtimeFilters', init);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      init(document);
    });
  } else {
    init(document);
  }
})();
