/* Página de detalhe do evento (wizard guiado) — extraído do script inline de eventos/detalhe.html.
   Etapa 1: destinos dinâmicos (UF→cidades) e abas de documentos vinculados.
   Dados de template chegam por data-attributes no form (.oficio-wizard__form):
   data-api-cidades-url e data-sede-uf. */
(function () {
  "use strict";

  var CIDADES_CACHE_D = {};

  function normStrD(s) {
    return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  }

  function populateCidadesD(cidadeSel, data, initialValue) {
    var normInitial = normStrD(initialValue);
    cidadeSel.innerHTML = '<option value="">---------</option>';
    data.forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c.id;
      opt.textContent = c.nome;
      if (normInitial && normStrD(c.id) === normInitial) opt.selected = true;
      cidadeSel.appendChild(opt);
    });
    cidadeSel.disabled = false;
    reinitPickerD(cidadeSel);
  }

  function reinitPickerD(select) {
    if (!select || !window.CV || !window.CV.fields || !window.CV.fields.initSearchPickers) return;
    if (select.dataset.cvSearchPickerReady === 'true') {
      delete select.dataset.cvSearchPickerReady;
      var nextEl = select.nextElementSibling;
      if (nextEl && nextEl.classList && nextEl.classList.contains('cv-search-picker')) {
        nextEl.parentNode.removeChild(nextEl);
      }
    }
    window.CV.fields.initSearchPickers(select.parentNode || document);
  }

  function loadCidadesForUfD(form, cidadeSel, uf, initialValue) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.loadCities === 'function') {
      return window.CV.destinos.loadCities({
        citySelect: cidadeSel,
        stateId: uf,
        selectedId: initialValue,
        form: form,
        cache: CIDADES_CACHE_D,
        requestAttr: 'eventoCitiesRequestD'
      });
    }
    uf = String(uf || '').trim();
    var urlTemplate = (form && form.dataset.apiCidadesUrl) || '';
    cidadeSel.innerHTML = '<option value="">---------</option>';
    if (!uf || !urlTemplate) {
      cidadeSel.disabled = true;
      reinitPickerD(cidadeSel);
      return;
    }
    var cached = CIDADES_CACHE_D[uf];
    if (cached) { populateCidadesD(cidadeSel, cached, initialValue); return; }
    cidadeSel.disabled = true;
    reinitPickerD(cidadeSel);
    var url = urlTemplate.replace('/0/', '/' + encodeURIComponent(uf) + '/');
    fetch(url, { headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        CIDADES_CACHE_D[uf] = data;
        populateCidadesD(cidadeSel, data, initialValue);
      })
      .catch(function () {
        cidadeSel.disabled = true;
        reinitPickerD(cidadeSel);
      });
  }

  function initCidadePickerD(form) {
    var ufSel = form.querySelector('select[name="destino_uf"]');
    var cidadeSel = form.querySelector('[data-destino-cidade-picker]');
    if (!ufSel || !cidadeSel || ufSel.dataset.eventoCityBound === 'true') return;
    ufSel.dataset.eventoCityBound = 'true';
    var initialValue = cidadeSel.dataset.initialValue || '';
    ufSel.addEventListener('change', function () {
      loadCidadesForUfD(form, cidadeSel, ufSel.value, '');
    });
    if (ufSel.value) {
      loadCidadesForUfD(form, cidadeSel, ufSel.value, initialValue);
    }
  }

  function serializeDestinosD() {
    var lista = document.getElementById('destinos-lista-d');
    var jsonInput = document.getElementById('id-destinos-json-d');
    if (!lista || !jsonInput) return;
    var rows = lista.querySelectorAll('[data-destino-index]');
    var result = [];
    rows.forEach(function (row) {
      var ufSel = row.querySelector('select[name="destino_uf"], [data-destino-uf-extra]');
      var cidadeSel = row.querySelector('[data-destino-cidade-picker], [data-destino-cidade-extra]');
      var uf = ufSel ? ufSel.value : '';
      var cidade = cidadeSel ? cidadeSel.value : '';
      result.push({ uf: uf, cidade: cidade });
    });
    jsonInput.value = JSON.stringify(result);
  }

  function refreshRemoveButtonsD(lista) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.updateSingleRowState === 'function') {
      window.CV.destinos.updateSingleRowState(lista, {
        rowSelector: '[data-destino-index]',
        removeSelector: '[data-remover-destino]'
      });
      return;
    }
    var rows = lista.querySelectorAll('[data-destino-index]');
    var count = rows.length;
    rows.forEach(function (row) {
      var btn = row.querySelector('[data-remover-destino]');
      if (btn) btn.hidden = count <= 1;
    });
  }

  function initAddDestinoD() {
    var btn = document.getElementById('btn-adicionar-destino-d');
    var lista = document.getElementById('destinos-lista-d');
    var tmpl = document.getElementById('tmpl-destino-extra-d');
    var cardEl = document.getElementById('evento-card-dados-d');
    var form = cardEl ? cardEl.closest('form') : null;
    if (!btn || !lista || !tmpl || btn.dataset.eventoDestinosBound === 'true') return;
    btn.dataset.eventoDestinosBound = 'true';

    var sedeUf = (form && form.dataset.sedeUf) || '';
    var extraCount = 0;

    if (window.CV && window.CV.destinos && typeof window.CV.destinos.initDragDrop === 'function') {
      window.CV.destinos.initDragDrop(lista, {
        rowSelector: '[data-destino-index]',
        removeSelector: '[data-remover-destino]',
        onReorder: function () { refreshRemoveButtonsD(lista); }
      });
    }

    function wireRow(row) {
      if (row.dataset.eventoRowBound === 'true') return;
      row.dataset.eventoRowBound = 'true';
      var removeBtn = row.querySelector('[data-remover-destino]');
      if (removeBtn) {
        removeBtn.addEventListener('click', function () {
          row.parentNode.removeChild(row);
          refreshRemoveButtonsD(lista);
        });
      }
      var ufExtra = row.querySelector('[data-destino-uf-extra]');
      var cidadeExtra = row.querySelector('[data-destino-cidade-extra]');
      if (ufExtra && cidadeExtra) {
        ufExtra.addEventListener('change', function () {
          loadCidadesForUfD(form, cidadeExtra, ufExtra.value, '');
        });
        // Destinos extras já persistidos: carrega as cidades da UF mantendo a
        // cidade salva selecionada.
        var savedCity = cidadeExtra.dataset.initialValue || '';
        if (ufExtra.value) {
          loadCidadesForUfD(form, cidadeExtra, ufExtra.value, savedCity);
        }
      }
    }

    lista.querySelectorAll('[data-destino-index]').forEach(wireRow);
    refreshRemoveButtonsD(lista);

    btn.addEventListener('click', function () {
      if (window.CV && window.CV.destinos && typeof window.CV.destinos.appendTemplateRow === 'function') {
        var appended = window.CV.destinos.appendTemplateRow({
          list: lista,
          template: tmpl,
          rowSelector: '[data-destino-index]',
          removeSelector: '[data-remover-destino]',
          indexAttr: 'destinoIndex',
          bindRow: wireRow,
          afterAppend: function (row) {
            refreshRemoveButtonsD(lista);
            if (sedeUf && row) {
              var ufExtra = row.querySelector('[data-destino-uf-extra]');
              if (ufExtra) {
                ufExtra.value = sedeUf;
                ufExtra.dispatchEvent(new Event('change', { bubbles: true }));
              }
            }
          }
        });
        if (appended) refreshRemoveButtonsD(lista);
        return;
      }
      extraCount += 1;
      var clone = tmpl.content.cloneNode(true);
      var row = clone.querySelector('[data-destino-index]');
      if (row) row.dataset.destinoIndex = String(extraCount);
      var ufSel = clone.querySelector('[data-destino-uf-extra]');
      if (ufSel) ufSel.removeAttribute('data-cv-search-picker-ready');
      lista.appendChild(clone);
      var newRow = lista.querySelector('[data-destino-index="' + extraCount + '"]');
      if (newRow) {
        wireRow(newRow);
        refreshRemoveButtonsD(lista);
        if (window.CV && window.CV.fields && window.CV.fields.initSearchPickers) {
          window.CV.fields.initSearchPickers(newRow);
        }
        if (sedeUf) {
          var ufExtra = newRow.querySelector('[data-destino-uf-extra]');
          if (ufExtra) {
            ufExtra.value = sedeUf;
            ufExtra.dispatchEvent(new Event('change', { bubbles: true }));
          }
        }
      }
    });

    if (form) {
      form.addEventListener('submit', function () { serializeDestinosD(); });
    }
  }

  function initDocTabsD(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var tabLists = Array.prototype.slice.call(scope.querySelectorAll('[data-evento-doc-tabs]'));
    if (scope.matches && scope.matches('[data-evento-doc-tabs]')) tabLists.unshift(scope);

    tabLists.forEach(function (tabs) {
      if (tabs.dataset.eventoTabsBound === 'true') return;
      tabs.dataset.eventoTabsBound = 'true';
      var card = tabs.closest('.cv-wizard-section-card') || document;
      var buttons = Array.prototype.slice.call(tabs.querySelectorAll('[data-doc-tab-target]'));
      var panels = Array.prototype.slice.call(card.querySelectorAll('[data-doc-tab-panel]'));
      if (!buttons.length || !panels.length) return;

      function activate(target, moveFocus) {
        buttons.forEach(function (button) {
          var active = button.dataset.docTabTarget === target;
          button.classList.toggle('is-active', active);
          button.setAttribute('aria-selected', String(active));
          button.tabIndex = active ? 0 : -1;
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

      var linkedPanel = panels.find(function (panel) {
        return Array.prototype.some.call(panel.querySelectorAll('select option:checked'), function (option) {
          return Boolean(String(option.value || '').trim());
        });
      });
      var initialButton = buttons.find(function (button) {
        return button.getAttribute('aria-selected') === 'true';
      }) || buttons[0];
      activate(linkedPanel ? linkedPanel.dataset.docTabPanel : initialButton.dataset.docTabTarget, false);
    });
  }

  function initD(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var forms = Array.prototype.slice.call(scope.querySelectorAll('[data-evento-guided-form]'));
    if (scope.matches && scope.matches('[data-evento-guided-form]')) forms.unshift(scope);
    forms.forEach(function (form) {
      if (form.dataset.eventoGuidedBound === 'true') return;
      form.dataset.eventoGuidedBound = 'true';
      initCidadePickerD(form);
      initAddDestinoD();
    });
    initDocTabsD(scope);
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
