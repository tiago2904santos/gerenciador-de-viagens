(function () {
  "use strict";


  var ROUTE_AVATAR_ICON =
    '<svg class="cv-icon related-route-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none">' +
      '<circle cx="6" cy="19" r="2.5" fill="currentColor"></circle>' +
      '<circle cx="18" cy="5" r="2.5" fill="currentColor"></circle>' +
      '<path d="M8.2 18.2h6.1a3.3 3.3 0 0 0 0-6.6H9.7a3.3 3.3 0 0 1 0-6.6h6.1" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"></path>' +
    '</svg>';

  function routeCardTitle(summary) {
    var label = String(summary.label || "").trim();
    var destino = String(summary.roteiro || summary.destino || "")
      .trim()
      .replace(/\s*->\s*/g, " \u2192 ");
    return [label, destino].filter(Boolean).join(" ");
  }

  function firstNames(summary) {
    var nomes = summary.servidores_nomes;
    if (!nomes || !nomes.length) {
      nomes = String(summary.servidores_label || "")
        .split(",")
        .map(function (nome) { return nome.trim(); })
        .filter(Boolean);
    }
    return nomes
      .map(function (nome) { return String(nome || "").trim().split(/\s+/)[0] || ""; })
      .filter(Boolean);
  }

  function viaturaLabel(summary) {
    var placa = String(summary.viatura || "").trim();
    var modelo = String(summary.viatura_modelo || "").trim();
    return [placa, modelo].filter(Boolean).join(" ");
  }

  function routeCardMeta(summary) {
    var periodo = String(summary.periodo || "").trim();
    var servidores = firstNames(summary).join(", ");
    var viatura = viaturaLabel(summary);
    var parts = [periodo, servidores, viatura].filter(Boolean);
    return parts.length ? parts.join(" \u00b7 ") : "Sem informa\u00e7\u00f5es dispon\u00edveis";
  }

  function readSummaries() {
    var script = document.getElementById("termos-oficios-summary");
    if (!script) return {};
    try {
      return JSON.parse(script.textContent || "{}");
    } catch (err) {
      return {};
    }
  }

  function resetSearchPicker(select) {
    if (window.CV && window.CV.locationRows && typeof window.CV.locationRows.resetSearchPicker === "function") {
      window.CV.locationRows.resetSearchPicker(select);
      return;
    }
    if (!select) return;
    if (select.dataset.cvSearchPickerReady === "true") {
      delete select.dataset.cvSearchPickerReady;
      var nextEl = select.nextElementSibling;
      if (nextEl && nextEl.classList && nextEl.classList.contains("cv-search-picker")) {
        nextEl.parentNode.removeChild(nextEl);
      }
    }
  }

  function initSearchPickers(scope) {
    if (window.CV && window.CV.locationRows && typeof window.CV.locationRows.initSearchPickers === "function") {
      window.CV.locationRows.initSearchPickers(scope || document);
      return;
    }
    if (window.CvSearchPicker && window.CvSearchPicker.init) {
      window.CvSearchPicker.init(scope || document);
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

  function clearOficioFields(form) {
    setDateFields(form, "", "");

    var stateSelect = form.querySelector("select[name='destino_estado']");
    var citySelect = form.querySelector("select[name='destino_cidade']");
    if (stateSelect) {
      stateSelect.value = "";
      resetSearchPicker(stateSelect);
      initSearchPickers(form);
    }
    if (citySelect) {
      clearCitySelect(form, citySelect);
    }

    var servidoresSelect = form.querySelector("select[name='servidores']");
    if (servidoresSelect) {
      setMultiSelectValues(servidoresSelect, [], form);
    }

    var viaturaSelect = form.querySelector("select[name='viatura']");
    if (viaturaSelect) {
      viaturaSelect.value = "";
      resetSearchPicker(viaturaSelect);
      initSearchPickers(form);
    }
  }

  function autoFillFromOficio(form, summary) {
    if (!summary) {
      clearOficioFields(form);
      return;
    }

    if (summary.data_inicio) {
      setDateFields(form, summary.data_inicio, summary.data_fim || summary.data_inicio);
    }

    var stateId = String(summary.estado_id || "");
    var cityId  = String(summary.cidade_id  || "");
    if (stateId) {
      var stateSelect = form.querySelector("select[name='destino_estado']");
      var citySelect  = form.querySelector("select[name='destino_cidade']");
      if (stateSelect && citySelect) {
        stateSelect.value = stateId;
        resetSearchPicker(stateSelect);
        initSearchPickers(form);
        loadCitiesForState(form, citySelect, stateId, cityId);
      }
    }

    if (summary.servidor_ids && summary.servidor_ids.length) {
      var servidoresSelect = form.querySelector("select[name='servidores']");
      setMultiSelectValues(servidoresSelect, summary.servidor_ids, form);
    }

    var viaturaId = String(summary.viatura_id || "");
    if (viaturaId) {
      var viaturaSelect = form.querySelector("select[name='viatura']");
      if (viaturaSelect) {
        viaturaSelect.value = viaturaId;
        resetSearchPicker(viaturaSelect);
        initSearchPickers(form);
      }
    }
  }

  function syncOficioSummary(form, summaries) {
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
        var button = document.createElement("button");
        button.type = "button";
        button.className = "cv-search-picker__selected-card related-route-item" + (active ? " is-active" : "");
        button.dataset.routeId = String(summary.id);
        button.setAttribute("aria-pressed", active ? "true" : "false");

        var avatar = document.createElement("span");
        avatar.className = "cv-search-picker__selected-avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.innerHTML = ROUTE_AVATAR_ICON;

        var main = document.createElement("div");
        main.className = "cv-search-picker__selected-main";

        var name = document.createElement("span");
        name.className = "cv-search-picker__selected-name";
        name.textContent = routeCardTitle(summary);

        var meta = document.createElement("span");
        meta.className = "cv-search-picker__selected-meta related-route-period";
        meta.textContent = routeCardMeta(summary);

        main.appendChild(name);
        main.appendChild(meta);
        button.appendChild(avatar);
        button.appendChild(main);
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
      autoFillFromOficio(form, selectedSummary());
    });
    search.addEventListener("input", function () {
      renderList(search.value);
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
    window.CV.locationRows.initManagedRows({
      form: form,
      managedFlag: "termoDestinosManaged",
    });
  }

  function syncAddDestinationButton(form) {
    if (form.dataset.termoDestinosManaged === "true") return;
    var button = form.querySelector("#termo-btn-adicionar-destino");
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

    var addButton = form.querySelector("#termo-btn-adicionar-destino");
    var rowsNeeded = indexes[indexes.length - 1] + 1;

    function rowsCount() {
      return form.querySelectorAll("[data-location-row]").length;
    }

    var guard = 0;
    while (rowsCount() < rowsNeeded && addButton && guard < 50) {
      addButton.click();
      guard += 1;
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

    syncOficioSummary(form, readSummaries());
    syncDestinationCities(form);
    syncAddDestinationButton(form);
    if (draft) applyDraftDestinos(form, draft);

    bindDraftAutosaveLinks(form);
  });
})();
