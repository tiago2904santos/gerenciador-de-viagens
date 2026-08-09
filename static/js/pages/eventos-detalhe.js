/* Página de detalhe do evento (wizard guiado) — extraído do script inline de eventos/detalhe.html.
   Etapa 1: destinos dinâmicos (UF→cidades) e o picker de "Documentos vinculados"
   (toggle segmentado + lista estilo ofícios da OS com pré-filtro por datas).
   Dados de template chegam por data-attributes no form (.travel-document-wizard__form):
   data-api-cidades-url e data-sede-uf; e no #evento-doc-summaries (JSON). */
(function () {
  "use strict";

  function selectedText(select) {
    var option = select && select.options ? select.options[select.selectedIndex] : null;
    return option ? String(option.textContent || '').trim() : '';
  }

  function serializeDestinosD(form) {
    var jsonInput = form.querySelector('#id-destinos-json-d');
    if (!jsonInput) return;
    var result = Array.prototype.slice.call(form.querySelectorAll('[data-location-row]')).map(function (row) {
      var state = row.querySelector('[data-location-state]');
      var city = row.querySelector('[data-location-city]');
      var selectedState = state && state.options ? state.options[state.selectedIndex] : null;
      return {
        uf: selectedState ? String(selectedState.dataset.locationStateCode || '') : '',
        cidade: city && city.value ? selectedText(city) : '',
      };
    });
    jsonInput.value = JSON.stringify(result);
    var primary = result[0] || { uf: '', cidade: '' };
    var stateOutput = form.querySelector('[data-location-state-output]');
    var cityOutput = form.querySelector('[data-location-city-output]');
    if (stateOutput) stateOutput.value = primary.uf;
    if (cityOutput) cityOutput.value = primary.cidade;
  }

  function initAddDestinoD() {
    var card = document.getElementById('evento-card-dados-d');
    var form = card ? card.closest('form') : null;
    if (!form) return false;
    if (!window.CV || !window.CV.locationRows || typeof window.CV.locationRows.initManagedRows !== 'function') {
      return false;
    }
    var section = form.querySelector('#evento-wizard-destinos-d');
    var list = section ? section.querySelector('[data-location-list]') : null;
    var template = form.querySelector('#tmpl-destino-extra-d') || form.querySelector('template[data-location-template]');
    if (!section || !list || !template) return false;

    // Impede o listener delegado interno e trata o "+" neste módulo —
    // o clique no botão da linha precisa funcionar mesmo com o picker por cima.
    section.dataset.locationAddBound = 'true';
    var managed = window.CV.locationRows.initManagedRows({
      form: form,
      section: section,
      list: list,
      template: template,
      renameFields: false,
      getOriginLabel: function () {
        return String(form.getAttribute('data-sede-label') || '').trim();
      },
      originFallback: 'Sede',
      onChange: function () { serializeDestinosD(form); },
      onRow: function (row, index) {
        var badge = row.querySelector('[data-location-order]');
        if (badge) badge.textContent = String(index + 1);
      },
    });

    if (form.dataset.eventoDestinosAddBound !== 'true') {
      form.dataset.eventoDestinosAddBound = 'true';
      form.addEventListener('click', function (event) {
        var button = event.target.closest('#evento-wizard-destinos-d [data-location-add]');
        if (!button || !form.contains(button)) return;
        event.preventDefault();
        var sourceRow = button.closest('[data-location-row]');
        var referenceState = sourceRow ? sourceRow.querySelector('[data-location-state]') : null;
        var referenceStateId = referenceState
          ? String(referenceState.value || referenceState.dataset.pickerInitialValue || '').trim()
          : '';
        window.CV.locationRows.appendTemplateRow({
          list: list,
          template: template,
          rowSelector: '[data-location-row]',
          removeSelector: '[data-location-remove]',
          indexAttr: 'locationIndex',
          insertAfter: sourceRow || null,
          beforeAppend: function (row) {
            if (!row || !referenceStateId) return;
            var stateSelect = row.querySelector('[data-location-state]');
            if (stateSelect) {
              stateSelect.value = referenceStateId;
              stateSelect.dataset.pickerInitialValue = referenceStateId;
            }
          },
          bindRow: function (row) {
            if (managed && typeof managed.bindRow === 'function') managed.bindRow(row);
            if (managed && typeof managed.renameRows === 'function') managed.renameRows();
          },
          afterAppend: function () {
            if (managed) {
              if (typeof managed.renameRows === 'function') managed.renameRows();
              if (typeof managed.refreshRows === 'function') managed.refreshRows();
              if (typeof managed.refreshTrechosPreview === 'function') managed.refreshTrechosPreview();
            }
            if (typeof window.CV.locationRows.initSearchPickers === 'function') {
              window.CV.locationRows.initSearchPickers(list);
            }
            serializeDestinosD(form);
          },
        });
      });
    }

    form.addEventListener('submit', function () { serializeDestinosD(form); });
    serializeDestinosD(form);
    return true;
  }

  /* ── Documentos vinculados: toggle segmentado + lista com pré-filtro de datas ── */

  var DOC_AVATAR_ICON =
    '<svg class="icon related-route-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none">' +
      '<circle cx="6" cy="19" r="2.5" fill="currentColor"></circle>' +
      '<circle cx="18" cy="5" r="2.5" fill="currentColor"></circle>' +
      '<path d="M8.2 18.2h6.1a3.3 3.3 0 0 0 0-6.6H9.7a3.3 3.3 0 0 1 0-6.6h6.1" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"></path>' +
    '</svg>';

  var MS_PER_DAY = 24 * 60 * 60 * 1000;

  function readDocSummaries() {
    var script = document.getElementById('evento-doc-summaries');
    if (!script) return {};
    try {
      var parsed = JSON.parse(script.textContent || '{}');
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function isoToDayNumber(iso) {
    if (!iso) return null;
    var parts = String(iso).split('-');
    if (parts.length !== 3) return null;
    var t = Date.UTC(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    return isNaN(t) ? null : Math.round(t / MS_PER_DAY);
  }

  /* Distância (em dias) entre dois intervalos [a1,a2] e [b1,b2]; 0 se sobrepõem. */
  function rangeGap(a1, a2, b1, b2) {
    if (a2 < b1) return b1 - a2;
    if (b2 < a1) return a1 - b2;
    return 0;
  }

  function passesDateFilter(summary, eventStart, eventEnd, tolerance) {
    // Sem período de referência do evento → não filtra (mostra tudo).
    if (eventStart === null && eventEnd === null) return true;
    var refStart = eventStart === null ? eventEnd : eventStart;
    var refEnd = eventEnd === null ? eventStart : eventEnd;

    var docStart = isoToDayNumber(summary.data_inicio);
    var docEnd = isoToDayNumber(summary.data_fim);
    // Documento sem datas → mantém visível (não dá para comparar).
    if (docStart === null && docEnd === null) return true;
    if (docStart === null) docStart = docEnd;
    if (docEnd === null) docEnd = docStart;

    return rangeGap(docStart, docEnd, refStart, refEnd) <= tolerance;
  }

  function sourceSelectFor(root, key) {
    return root.querySelector('[data-evento-doc-field="' + key + '"]');
  }

  function selectedIdsFromSelect(select) {
    if (!select) return new Set();
    return new Set(
      Array.prototype.slice.call(select.options)
        .filter(function (o) { return o.selected && o.value; })
        .map(function (o) { return String(o.value); })
    );
  }

  function toggleSelectValue(select, id, selected) {
    if (!select) return;
    var target = String(id);
    Array.prototype.slice.call(select.options).forEach(function (opt) {
      if (String(opt.value) === target) opt.selected = !!selected;
    });
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function buildDocCard(summary, active) {
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'search-picker__selected-card related-route-item' + (active ? ' is-active' : '');
    button.dataset.value = String(summary.id);
    button.setAttribute('aria-pressed', active ? 'true' : 'false');

    var avatar = document.createElement('span');
    avatar.className = 'search-picker__selected-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.innerHTML = DOC_AVATAR_ICON;

    var main = document.createElement('div');
    main.className = 'search-picker__selected-main';

    var name = document.createElement('span');
    name.className = 'search-picker__selected-name';
    name.textContent = summary.title || '';

    var meta = document.createElement('span');
    meta.className = 'search-picker__selected-meta related-route-period';
    meta.textContent = summary.meta || '';

    main.appendChild(name);
    main.appendChild(meta);
    button.appendChild(avatar);
    button.appendChild(main);
    return button;
  }

  function initDocPanel(root, key, items, eventStart, eventEnd, tolerance) {
    var select = sourceSelectFor(root, key);
    var list = root.querySelector('[data-evento-doc-list="' + key + '"]');
    var search = root.querySelector('[data-evento-doc-search="' + key + '"]');
    var empty = root.querySelector('[data-evento-doc-empty="' + key + '"]');
    if (!select || !list) return;

    function render() {
      var selected = selectedIdsFromSelect(select);
      var term = window.CV.util.normalize(search ? search.value : '');
      var tokens = term.split(/\s+/).filter(Boolean);

      var visible = items.filter(function (summary) {
        var isSelected = selected.has(String(summary.id));
        // Documentos já vinculados aparecem sempre; os demais respeitam o filtro de datas.
        if (!isSelected && !passesDateFilter(summary, eventStart, eventEnd, tolerance)) return false;
        if (!tokens.length) return true;
        var haystack = window.CV.util.normalize(summary.search_text || (summary.title + ' ' + summary.meta));
        return tokens.every(function (token) { return haystack.indexOf(token) !== -1; });
      });

      list.innerHTML = '';
      if (!visible.length) {
        if (empty) empty.hidden = false;
        return;
      }
      if (empty) empty.hidden = true;

      visible.forEach(function (summary) {
        var active = selected.has(String(summary.id));
        var card = buildDocCard(summary, active);
        card.addEventListener('click', function () {
          toggleSelectValue(select, summary.id, !selected.has(String(summary.id)));
          render();
        });
        list.appendChild(card);
      });
    }

    if (search && search.dataset.eventoDocBound !== 'true') {
      search.dataset.eventoDocBound = 'true';
      search.addEventListener('input', render);
    }
    select.addEventListener('change', render);
    render();
  }

  function initDocPickersD(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var pickers = Array.prototype.slice.call(scope.querySelectorAll('[data-evento-doc-picker]'));
    if (scope.matches && scope.matches('[data-evento-doc-picker]')) pickers.unshift(scope);

    pickers.forEach(function (picker) {
      if (picker.dataset.eventoDocPickerBound === 'true') return;
      picker.dataset.eventoDocPickerBound = 'true';

      var summaries = readDocSummaries();
      var eventStart = isoToDayNumber(picker.dataset.eventoPeriodoInicio || '');
      var eventEnd = isoToDayNumber(picker.dataset.eventoPeriodoFim || '');
      var tolerance = parseInt(picker.dataset.eventoDocTolerancia || '5', 10);
      if (isNaN(tolerance)) tolerance = 5;

      Object.keys(summaries).forEach(function (key) {
        initDocPanel(picker, key, summaries[key] || [], eventStart, eventEnd, tolerance);
      });

      initDocToggle(picker);
    });
  }

  function initDocToggle(picker) {
    var toggle = picker.querySelector('[data-evento-doc-toggle]');
    if (!toggle) return;
    var buttons = Array.prototype.slice.call(toggle.querySelectorAll('[data-doc-tab-target]'));
    var panels = Array.prototype.slice.call(picker.querySelectorAll('[data-doc-tab-panel]'));
    if (!buttons.length || !panels.length) return;

    function activate(target, moveFocus) {
      buttons.forEach(function (button) {
        var active = button.dataset.docTabTarget === target;
        var wasActive = button.getAttribute('aria-pressed') === 'true';
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
        button.tabIndex = active ? 0 : -1;
        if (active && !wasActive) {
          button.classList.remove('segment-toggle__btn--pop');
          void button.offsetWidth;
          button.classList.add('segment-toggle__btn--pop');
        }
        if (active && moveFocus) button.focus();
      });
      panels.forEach(function (panel) {
        panel.hidden = panel.dataset.docTabPanel !== target;
      });
    }

    buttons.forEach(function (button, index) {
      button.addEventListener('click', function () {
        activate(button.dataset.docTabTarget, false);
      });
      button.addEventListener('keydown', function (event) {
        var nextIndex = index;
        if (event.key === 'ArrowRight') nextIndex = (index + 1) % buttons.length;
        else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + buttons.length) % buttons.length;
        else if (event.key === 'Home') nextIndex = 0;
        else if (event.key === 'End') nextIndex = buttons.length - 1;
        else return;
        event.preventDefault();
        activate(buttons[nextIndex].dataset.docTabTarget, true);
      });
    });

    // Abre na primeira aba que já tenha documento vinculado; senão, na primeira.
    var linkedPanel = panels.find(function (panel) {
      var select = panel.querySelector('.evento-doc-source-select');
      return select && Array.prototype.some.call(select.options, function (option) {
        return option.selected && String(option.value || '').trim();
      });
    });
    var initialButton = buttons.find(function (button) {
      return button.getAttribute('aria-pressed') === 'true';
    }) || buttons[0];
    activate(linkedPanel ? linkedPanel.dataset.docTabPanel : initialButton.dataset.docTabTarget, false);
  }

  function initD(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var forms = Array.prototype.slice.call(scope.querySelectorAll('[data-evento-guided-form]'));
    if (scope.matches && scope.matches('[data-evento-guided-form]')) forms.unshift(scope);
    forms.forEach(function (form) {
      if (form.dataset.eventoGuidedBound === 'true') return;
      // Só marca bound depois que locationRows estiver disponível (shell.bundle).
      if (!initAddDestinoD()) return;
      form.dataset.eventoGuidedBound = 'true';
    });
    initDocPickersD(scope);
  }

  window.CV = window.CV || {};
  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('eventoGuided', initD);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initD(document); });
  } else {
    initD(document);
  }
})();
