/**
 * realtime-filters.js — Filtros em tempo real para listas da Central de Viagens
 *
 * Padrão de data-attributes:
 *   data-cv-realtime-filter-scope        — Elemento raiz do escopo de filtragem
 *   data-cv-filter="search"              — Input de texto para busca
 *   data-cv-filter="status"              — Select para filtro de status
 *   data-cv-filter-item                  — Cada item filtrável da lista
 *   data-search-text="..."              — Texto indexado para busca (no item)
 *   data-status-value="..."             — Valor de status do item (no item)
 *   data-cv-results-count               — Elemento que exibe contagem de resultados
 *   data-cv-empty-state                 — Elemento de empty state (usa hidden)
 *   data-cv-filter-clear                — Botão/link que limpa todos os filtros
 */

(function () {
  "use strict";

  /**
   * Normaliza texto: remove acentos, converte para minúsculas e trim.
   * @param {string} value
   * @returns {string}
   */
  function normalizeText(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  /**
   * Verifica se um item corresponde a todos os filtros ativos.
   * @param {Element} item
   * @param {{ search: string, status: string }} filters
   * @returns {boolean}
   */
  function matchesFilter(item, filters) {
    // Filtro de texto
    if (filters.search) {
      var searchText = normalizeText(item.dataset.searchText || item.textContent);
      if (searchText.indexOf(filters.search) === -1) {
        return false;
      }
    }

    // Filtro de status
    if (filters.status) {
      var statusValue = normalizeText(item.dataset.statusValue || "");
      if (statusValue !== normalizeText(filters.status)) {
        return false;
      }
    }

    return true;
  }

  /**
   * Aplica todos os filtros ativos num escopo.
   * @param {Element} scope
   */
  function applyFilters(scope) {
    var filters = {
      search: "",
      status: ""
    };

    // Lê todos os inputs/selects de filtro dentro do escopo
    var filterInputs = Array.prototype.slice.call(
      scope.querySelectorAll("[data-cv-filter]")
    );
    filterInputs.forEach(function (input) {
      var type = input.dataset.cvFilter;
      var value = (input.value || "").trim();
      if (type === "search") {
        filters.search = normalizeText(value);
      } else if (type === "status") {
        filters.status = value;
      }
    });

    // Filtra os itens
    var items = Array.prototype.slice.call(
      scope.querySelectorAll("[data-cv-filter-item]")
    );
    var visibleCount = 0;

    items.forEach(function (item) {
      if (matchesFilter(item, filters)) {
        item.hidden = false;
        visibleCount++;
      } else {
        item.hidden = true;
      }
    });

    // Atualiza contador de resultados
    var countEl = scope.querySelector("[data-cv-results-count]");
    if (countEl) {
      countEl.textContent = visibleCount;
    }

    // Mostra/oculta empty state
    var emptyState = scope.querySelector("[data-cv-empty-state]");
    if (emptyState) {
      if (items.length > 0 && visibleCount === 0) {
        emptyState.hidden = false;
      } else {
        emptyState.hidden = true;
      }
    }
  }

  /**
   * Cria função debounced.
   * @param {Function} fn
   * @param {number} delay
   * @returns {Function}
   */
  function debounce(fn, delay) {
    var timer = null;
    return function () {
      var args = arguments;
      var ctx = this;
      if (timer) { window.clearTimeout(timer); }
      timer = window.setTimeout(function () {
        fn.apply(ctx, args);
        timer = null;
      }, delay);
    };
  }

  /**
   * Inicializa os filtros em tempo real para todos os escopos encontrados.
   */
  function initRealtimeFilters() {
    var scopes = Array.prototype.slice.call(
      document.querySelectorAll("[data-cv-realtime-filter-scope]")
    );

    scopes.forEach(function (scope) {
      var filterInputs = Array.prototype.slice.call(
        scope.querySelectorAll("[data-cv-filter]")
      );

      filterInputs.forEach(function (input) {
        var tagName = input.tagName.toLowerCase();
        var isSelect = tagName === "select";
        var isText = tagName === "input" && (input.type === "text" || input.type === "search" || input.type === "");

        if (isText) {
          // Debounce em inputs de texto (250ms)
          var debouncedApply = debounce(function () {
            applyFilters(scope);
          }, 250);
          input.addEventListener("input", debouncedApply);
        } else if (isSelect) {
          // Selects aplicam imediatamente
          input.addEventListener("change", function () {
            applyFilters(scope);
          });
        }
      });

      // Botão/link de limpar filtros
      var clearButtons = Array.prototype.slice.call(
        scope.querySelectorAll("[data-cv-filter-clear]")
      );
      clearButtons.forEach(function (btn) {
        btn.addEventListener("click", function (e) {
          // Previne a navegação e limpa os filtros localmente
          e.preventDefault();
          filterInputs.forEach(function (input) {
            input.value = "";
          });
          applyFilters(scope);
        });
      });

      // Aplica filtros iniciais (respeita valor já preenchido pelo servidor)
      applyFilters(scope);
    });
  }

  // Inicializa no DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initRealtimeFilters);
  } else {
    initRealtimeFilters();
  }

  // Expõe API pública para uso externo se necessário
  window.CVRealtimeFilters = {
    init: initRealtimeFilters,
    applyFilters: applyFilters,
    normalizeText: normalizeText,
    matchesFilter: matchesFilter
  };
}());
