(function () {
  "use strict";

  function readSummaries() {
    return window.CV.documentSource.read("termos-oficios-summary");
  }

  function resetSearchPicker(select) {
    if (window.CV && window.CV.locationRows && typeof window.CV.locationRows.resetSearchPicker === "function") {
      window.CV.locationRows.resetSearchPicker(select);
      return;
    }
    if (!select) return;
    if (select.dataset.entityPickerReady === "true") {
      delete select.dataset.entityPickerReady;
      var rendered = window.CV.picker.rootFor(select);
      if (rendered && rendered !== select) {
        rendered.parentNode.removeChild(rendered);
      }
    }
  }

  function initSearchPickers(scope) {
    if (window.CV && window.CV.locationRows && typeof window.CV.locationRows.initSearchPickers === "function") {
      window.CV.locationRows.initSearchPickers(scope || document);
      return;
    }
    if (window.CV && window.CV.picker && window.CV.picker.initSearch) {
      window.CV.picker.initSearch(scope || document);
    }
  }

  function isoToDisplay(iso) {
    if (!iso) return "";
    var p = (iso || "").split("-");
    if (p.length !== 3) return "";
    return [p[2], p[1], p[0]].join("/");
  }

  function setDateFields(form, startIso, endIso) {
    var startHidden  = form.querySelector("input[name='data_evento_inicio']");
    var endHidden    = form.querySelector("input[name='data_evento_fim']");
    var startDisplay = form.querySelector("#termo-evento-date-picker [data-cv-date-picker-start-display]");
    var endDisplay   = form.querySelector("#termo-evento-date-picker [data-cv-date-picker-end-display]");
    var picker       = form.querySelector("#termo-evento-date-picker");
    var safeEnd = endIso || startIso;
    if (startHidden)  startHidden.value  = startIso || "";
    if (endHidden)    endHidden.value    = safeEnd  || "";
    if (startDisplay) startDisplay.value = isoToDisplay(startIso);
    if (endDisplay)   endDisplay.value   = isoToDisplay(safeEnd);
    if (picker && picker._cvDatePicker && typeof picker._cvDatePicker.setRange === "function") {
      picker._cvDatePicker.setRange(startIso || "", safeEnd || "");
    }
  }

  function setMultiSelectValues(select, ids, form) {
    if (!select) return;
    var idSet = new Set(ids.map(String));
    Array.from(select.options).forEach(function (opt) {
      opt.selected = idSet.has(String(opt.value));
    });
    resetSearchPicker(select);
    initSearchPickers(form);
  }

  function applyOficioSource(form, summary) {
    window.CV.documentSource.apply(form, summary ? [summary] : [], [
      {
        type: "date-range",
        startName: "data_evento_inicio",
        endName: "data_evento_fim",
        startPath: "data_inicio",
        endPath: "data_fim",
        picker: "#termo-evento-date-picker",
        clear: true,
      },
      {
        type: "location",
        stateName: "destino_estado",
        cityName: "destino_cidade",
        statePath: "estado_id",
        cityPath: "cidade_id",
        clear: true,
      },
      { type: "multi", name: "servidores", path: "servidor_ids", strategy: "union", clear: true },
      { type: "value", name: "viatura", path: "viatura_id", clear: true },
    ]);
  }

  function syncOficioSummary(form, summaries, destinosApi) {
    var select = form.querySelector("select[name='oficio']");
    var root = form.querySelector("[data-termo-oficio-summary]");
    var search = form.querySelector("#id_oficio_busca");
    var list = form.querySelector("#termo-oficio-lista");
    if (!select || !search || !list) return;

    var grid = root ? root.querySelector(".termo-oficio-summary__grid") : null;
    var destino = root ? root.querySelector("[data-termo-oficio-destino]") : null;
    var periodo = root ? root.querySelector("[data-termo-oficio-periodo]") : null;
    var servidores = root ? root.querySelector("[data-termo-oficio-servidores]") : null;
    var viatura = root ? root.querySelector("[data-termo-oficio-viatura]") : null;

    var items = Object.keys(summaries).map(function (key) {
      return summaries[key];
    });
    items.sort(function (a, b) {
      return (a.order || 0) - (b.order || 0);
    });

    function selectedSummary() {
      return summaries[String(select.value || "")] || null;
    }

    function refreshTrechos() {
      if (destinosApi && typeof destinosApi.refreshTrechosPreview === "function") {
        destinosApi.refreshTrechosPreview();
      }
    }

    function renderSummary() {
      var summary = selectedSummary();
      var hasSummary = !!summary;
      if (root) root.hidden = !hasSummary;
      if (grid) grid.hidden = !hasSummary;
      if (!hasSummary) {
        if (destino) destino.textContent = "-";
        if (periodo) periodo.textContent = "-";
        if (servidores) servidores.textContent = "-";
        if (viatura) viatura.textContent = "-";
        return;
      }
      if (destino) destino.textContent = summary.destino || "-";
      if (periodo) periodo.textContent = summary.periodo || "-";
      if (servidores) servidores.textContent = String(summary.servidores || 0);
      if (viatura) viatura.textContent = summary.viatura || "-";
    }

    function renderList(filterText) {
      var emptyEl = form.querySelector("#termo-oficio-lista-empty");
      var term = window.CV.util.normalize(filterText);
      var tokens = term.split(/\s+/).filter(Boolean);
      var filtered = items.filter(function (summary) {
        var text = window.CV.util.normalize(summary.search_text || [summary.label, summary.numero, summary.protocolo, summary.destino, summary.periodo].join(" "));
        return !tokens.length || tokens.every(function (token) {
          return text.indexOf(token) !== -1;
        });
      });

      list.innerHTML = "";
      if (!filtered.length) {
        if (emptyEl) emptyEl.hidden = false;
        return;
      }
      if (emptyEl) emptyEl.hidden = true;

      filtered.forEach(function (summary) {
        var active = String(summary.id) === String(select.value || "");
        var button = window.CV.pickerParts.createRouteCard(summary, { active: active });
        button.addEventListener("click", function () {
          var alreadySelected = String(select.value || "") === String(summary.id);
          select.value = alreadySelected ? "" : String(summary.id);
          select.dispatchEvent(new Event("change", { bubbles: true }));
          renderList(search.value);
          renderSummary();
        });
        list.appendChild(button);
      });
    }

    select.addEventListener("change", function () {
      renderList(search.value);
      renderSummary();
      applyOficioSource(form, selectedSummary());
      refreshTrechos();
    });
    search.addEventListener("input", function () {
      renderList(search.value);
    });

    /* NOVO-07: os candidatos deixaram de vir todos no HTML. Os resumos novos
       entram em `summaries` tambem, e nao so em `items`, porque e de la que
       `selectedSummary()` le o que preenche a tela. */
    window.CV.documentSearch.attach({
      select: select,
      input: search,
      onResults: function (novos) {
        novos.forEach(function (resumo) {
          var chave = String(resumo.id);
          if (summaries[chave]) return;
          summaries[chave] = resumo;
          items.push(resumo);
        });
        renderList(search.value);
      },
    });

    renderList(search.value);
    renderSummary();
  }

  function clearCitySelect(form, citySelect) {
    window.CV.locationRows.clearSelect(citySelect, { scope: form });
  }

  function loadCitiesForState(form, citySelect, stateId, selectedCityId) {
    return window.CV.locationRows.loadCities({
      citySelect: citySelect,
      stateId: stateId,
      selectedId: selectedCityId,
      form: form,
      scope: form,
    });
  }

  function syncDestinationCities(form) {
    return window.CV.locationRows.initManagedRows({
      form: form,
      managedFlag: "termoDestinosManaged",
      getOriginLabel: function () {
        return String(form.getAttribute("data-sede-label") || "").trim();
      },
      originFallback: "Sede",
    });
  }

  function syncAddDestinationButton(form) {
    if (form.dataset.termoDestinosManaged === "true") return;
    // No layout `split` o botao mora dentro da linha, sem id proprio; o id so
    // existe no layout com header. Sem o fallback isto virava no-op silencioso.
    var button = form.querySelector("#termo-btn-adicionar-destino")
      || form.querySelector("#termo-evento-destinos [data-location-add]");
    var destinationSection = form.querySelector("#termo-evento-destinos");
    if (!button || !destinationSection) return;

    button.addEventListener("click", function () {
      window.CV.locationRows.focusFirstEmptyPicker(destinationSection);
    });
  }

  function draftStorageKey() {
    return "termoFormDraft:" + window.location.pathname + window.location.search;
  }

  function serializeFormEntries(form) {
    var data = new FormData(form);
    var entries = [];
    data.forEach(function (value, key) {
      if (key === "csrfmiddlewaretoken") return;
      entries.push([key, value]);
    });
    return entries;
  }

  function saveDraft(form) {
    try {
      window.sessionStorage.setItem(draftStorageKey(), JSON.stringify(serializeFormEntries(form)));
    } catch (err) {
      /* armazenamento indisponivel (modo privado, quota etc.) */
    }
  }

  function takeDraft() {
    var key = draftStorageKey();
    var raw;
    try {
      raw = window.sessionStorage.getItem(key);
    } catch (err) {
      return null;
    }
    if (!raw) return null;
    try {
      window.sessionStorage.removeItem(key);
    } catch (err) {
      /* ignore */
    }
    var entries;
    try {
      entries = JSON.parse(raw);
    } catch (err) {
      return null;
    }
    if (!Array.isArray(entries)) return null;
    var byName = {};
    entries.forEach(function (pair) {
      var name = pair[0];
      var value = pair[1];
      if (!byName[name]) byName[name] = [];
      byName[name].push(value);
    });
    return byName;
  }

  function applyDraftSimpleFields(form, draft) {
    if (draft.oficio && draft.oficio.length) {
      var oficioSelect = form.querySelector("select[name='oficio']");
      if (oficioSelect) oficioSelect.value = draft.oficio[0];
    }

    var startIso = draft.data_evento_inicio ? draft.data_evento_inicio[0] : "";
    var endIso = draft.data_evento_fim ? draft.data_evento_fim[0] : "";
    if (startIso) {
      setDateFields(form, startIso, endIso || startIso);
    }

    if (draft.servidores && draft.servidores.length) {
      var servidoresSelect = form.querySelector("select[name='servidores']");
      setMultiSelectValues(servidoresSelect, draft.servidores, form);
    }

    if (draft.viatura && draft.viatura.length) {
      var viaturaSelect = form.querySelector("select[name='viatura']");
      if (viaturaSelect) {
        viaturaSelect.value = draft.viatura[0];
        resetSearchPicker(viaturaSelect);
        initSearchPickers(form);
      }
    }
  }

  function collectDestinoEntries(draft) {
    var entries = {};
    Object.keys(draft).forEach(function (name) {
      var stateMatch = name.match(/^destino_estado(?:_(\d+))?$/);
      var cityMatch = name.match(/^destino_cidade(?:_(\d+))?$/);
      if (stateMatch) {
        var stateIdx = stateMatch[1] ? parseInt(stateMatch[1], 10) : 0;
        entries[stateIdx] = entries[stateIdx] || {};
        entries[stateIdx].estado = draft[name][0];
      }
      if (cityMatch) {
        var cityIdx = cityMatch[1] ? parseInt(cityMatch[1], 10) : 0;
        entries[cityIdx] = entries[cityIdx] || {};
        entries[cityIdx].cidade = draft[name][0];
      }
    });
    return entries;
  }

  function applyDraftDestinos(form, draft) {
    var entries = collectDestinoEntries(draft);
    var indexes = Object.keys(entries)
      .map(Number)
      .filter(function (idx) {
        var entry = entries[idx];
        return entry && (entry.estado || entry.cidade);
      })
      .sort(function (a, b) { return a - b; });
    if (!indexes.length) return;

    var addButton = form.querySelector("#termo-btn-adicionar-destino")
      || form.querySelector("#termo-evento-destinos [data-location-add]");
    var rowsNeeded = indexes[indexes.length - 1] + 1;

    function rowsCount() {
      return form.querySelectorAll("[data-location-row]").length;
    }

    var guard = 0;
    while (rowsCount() < rowsNeeded && addButton && guard < 50) {
      addButton.click();
      guard += 1;
      addButton = form.querySelector("#termo-btn-adicionar-destino")
        || form.querySelector("#termo-evento-destinos [data-location-add]");
    }

    var rows = Array.prototype.slice.call(form.querySelectorAll("[data-location-row]"));
    indexes.forEach(function (idx) {
      var row = rows[idx];
      var entry = entries[idx];
      if (!row || !entry) return;
      var stateSelect = row.querySelector("[data-location-state]");
      var citySelect = row.querySelector("[data-location-city]");
      if (!stateSelect) return;
      stateSelect.value = entry.estado || "";
      resetSearchPicker(stateSelect);
      initSearchPickers(form);
      if (entry.estado && citySelect) {
        loadCitiesForState(form, citySelect, entry.estado, entry.cidade || "").then(function () {
          initSearchPickers(form);
        });
      }
    });
  }

  function bindDraftAutosaveLinks(form) {
    form.addEventListener("click", function (event) {
      var link = event.target.closest('[data-autosave-link="1"]');
      if (!link || !form.contains(link)) return;
      saveDraft(form);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-termo-form]");
    if (!form) return;

    var draft = takeDraft();
    if (draft) applyDraftSimpleFields(form, draft);

    var destinosApi = syncDestinationCities(form);
    syncOficioSummary(form, readSummaries(), destinosApi);
    syncAddDestinationButton(form);
    if (draft) applyDraftDestinos(form, draft);

    bindDraftAutosaveLinks(form);
  });
})();
