(function () {
  "use strict";

  var CITIES_CACHE = {};

  function readSummaries() {
    var script = document.getElementById("termos-oficios-summary");
    if (!script) return {};
    try {
      return JSON.parse(script.textContent || "{}");
    } catch (err) {
      return {};
    }
  }

  function normalize(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function parseIsoDate(value) {
    if (!value) return "";
    var text = String(value).trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
    var match = text.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!match) return "";
    return [match[3], match[2], match[1]].join("-");
  }

  function formatDisplayDate(value) {
    var iso = parseIsoDate(value);
    if (!iso) return "";
    var parts = iso.split("-");
    return [parts[2], parts[1], parts[0]].join("/");
  }

  function setInputValue(input, value) {
    if (!input) return;
    input.value = value || "";
  }

  function resetSearchPicker(select) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.resetSearchPicker === "function") {
      window.CV.destinos.resetSearchPicker(select);
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
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.initSearchPickers === "function") {
      window.CV.destinos.initSearchPickers(scope || document);
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
    var startDisplay = form.querySelector("[data-termo-evento-start-display]");
    var endDisplay   = form.querySelector("[data-termo-evento-end-display]");
    var picker       = form.querySelector("#termo-evento-date-picker");
    var safeEnd = endIso || startIso;
    if (startHidden)  startHidden.value  = startIso || "";
    if (endHidden)    endHidden.value    = safeEnd  || "";
    if (startDisplay) startDisplay.value = isoToDisplay(startIso);
    if (endDisplay)   endDisplay.value   = isoToDisplay(safeEnd);
    if (picker) {
      var dates = [];
      if (startIso) dates.push(startIso);
      if (safeEnd && safeEnd !== startIso) dates.push(safeEnd);
      picker.dataset.selectedDates = JSON.stringify(dates);
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

  function autoFillFromOficio(form, summary) {
    if (!summary) return;

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
      var term = normalize(filterText);
      var tokens = term.split(/\s+/).filter(Boolean);
      var filtered = items.filter(function (summary) {
        var text = normalize(summary.search_text || [summary.label, summary.numero, summary.protocolo, summary.destino, summary.periodo].join(" "));
        return !tokens.length || tokens.every(function (token) {
          return text.indexOf(token) !== -1;
        });
      });

      list.innerHTML = "";
      if (!filtered.length) {
        var emptyState = document.createElement("div");
        emptyState.className = "oficio-roteiro-route-empty";
        emptyState.textContent = "Nenhum oficio encontrado para a busca.";
        list.appendChild(emptyState);
        return;
      }

      filtered.forEach(function (summary) {
        var active = String(summary.id) === String(select.value || "");
        var button = document.createElement("button");
        button.type = "button";
        button.className = "oficio-roteiro-route-item" + (active ? " is-active" : "");
        button.dataset.routeId = String(summary.id);

        var firstLine = document.createElement("span");
        firstLine.className = "route-title termo-oficio-route-line termo-oficio-route-line--primary";

        var oficio = document.createElement("strong");
        oficio.className = "termo-oficio-route__oficio";
        oficio.textContent = summary.label || ("Oficio " + String(summary.id));

        var protocolo = document.createElement("span");
        protocolo.className = "termo-oficio-route__protocolo";
        protocolo.textContent = "Protocolo " + (summary.protocolo || "-");

        firstLine.appendChild(oficio);
        firstLine.appendChild(protocolo);

        var secondLine = document.createElement("span");
        secondLine.className = "route-destinos termo-oficio-route-line";
        secondLine.textContent = [
          summary.roteiro || summary.destino || "Roteiro nao informado",
          summary.periodo ? "Periodo: " + summary.periodo : "",
        ].filter(Boolean).join(" | ");

        var thirdLine = document.createElement("span");
        thirdLine.className = "route-periodo termo-oficio-route-line termo-oficio-route-line--servers";
        thirdLine.textContent = summary.servidores_label ? summary.servidores_label : "Sem servidores vinculados";

        button.appendChild(firstLine);
        button.appendChild(secondLine);
        button.appendChild(thirdLine);
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

  function updateCitySelect(form, citySelect, cities, selectedCityId) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.setSelectOptions === "function") {
      window.CV.destinos.setSelectOptions(citySelect, cities, selectedCityId, { scope: form });
      return;
    }
    var selected = String(selectedCityId || "");
    resetSearchPicker(citySelect);
    citySelect.innerHTML = '<option value="">---------</option>';

    cities.forEach(function (city) {
      var option = document.createElement("option");
      option.value = String(city.id);
      option.textContent = city.nome;
      if (selected && String(city.id) === selected) {
        option.selected = true;
      }
      citySelect.appendChild(option);
    });

    citySelect.disabled = false;
    initSearchPickers(form);
  }

  function clearCitySelect(form, citySelect) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.clearSelect === "function") {
      window.CV.destinos.clearSelect(citySelect, { scope: form });
      return;
    }
    resetSearchPicker(citySelect);
    citySelect.innerHTML = '<option value="">---------</option>';
    citySelect.disabled = true;
    initSearchPickers(form);
  }

  function loadCitiesForState(form, citySelect, stateId, selectedCityId) {
    var state = String(stateId || "").trim();
    var urlTemplate = form.dataset.apiCidadesUrl || "";
    if (!state) {
      clearCitySelect(form, citySelect);
      return Promise.resolve([]);
    }
    if (!urlTemplate) {
      return Promise.resolve([]);
    }

    var cached = CITIES_CACHE[state];
    if (cached) {
      updateCitySelect(form, citySelect, cached, selectedCityId);
      return Promise.resolve(cached);
    }

    var requestToken = String(Date.now()) + "-" + Math.random().toString(16).slice(2);
    citySelect.dataset.termoCitiesRequest = requestToken;
    clearCitySelect(form, citySelect);

    var url = urlTemplate.replace("/0/", "/" + encodeURIComponent(state) + "/");
    return fetch(url, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Falha ao carregar cidades");
        }
        return response.json();
      })
      .then(function (data) {
        if (citySelect.dataset.termoCitiesRequest !== requestToken) {
          return [];
        }
        var cities = Array.isArray(data) ? data : (data.cidades || []);
        CITIES_CACHE[state] = cities;
        updateCitySelect(form, citySelect, cities, selectedCityId);
        return cities;
      })
      .catch(function () {
        if (citySelect.dataset.termoCitiesRequest === requestToken) {
          clearCitySelect(form, citySelect);
        }
        return [];
      });
  }

  function syncDestinationCities(form) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.initManagedRows === "function") {
      window.CV.destinos.initManagedRows({
        form: form,
        sectionSelector: "#termo-evento-destinos",
        addSelector: "[data-termo-add-destino]",
        templateSelector: "template[data-termo-destino-template]",
        rowSelector: "[data-termo-destino-row]",
        stateSelector: "[data-termo-destino-state]",
        citySelector: "[data-termo-destino-city]",
        removeSelector: "[data-termo-remove-destino]",
        indexAttr: "termoDestinoIndex",
        primaryStateName: "destino_estado",
        primaryCityName: "destino_cidade",
        extraStatePrefix: "destino_estado_",
        extraCityPrefix: "destino_cidade_",
        managedFlag: "termoDestinosManaged",
        readyAttr: "termoDestinoReady",
        loadCities: function (citySelect, stateId, selectedCityId) {
          return loadCitiesForState(form, citySelect, stateId, selectedCityId);
        }
      });
      return;
    }

    var stateSelect = form.querySelector("select[name='destino_estado']");
    var citySelect = form.querySelector("select[name='destino_cidade']");
    if (!stateSelect || !citySelect) return;
    var initialStateId = (stateSelect.dataset.pickerInitialValue || "").trim();
    var initialCityId = (citySelect.dataset.pickerInitialValue || "").trim();

    function onStateChange() {
      loadCitiesForState(
        form,
        citySelect,
        stateSelect.value || initialStateId,
        citySelect.value || initialCityId,
      );
    }

    stateSelect.addEventListener("change", onStateChange);
    loadCitiesForState(
      form,
      citySelect,
      stateSelect.value || initialStateId,
      citySelect.value || initialCityId,
    );
  }

  function syncAddDestinationButton(form) {
    if (form.dataset.termoDestinosManaged === "true") return;
    var button = form.querySelector("[data-termo-add-destino]");
    var destinationSection = form.querySelector("#termo-evento-destinos");
    if (!button || !destinationSection) return;

    button.addEventListener("click", function () {
      if (window.CV && window.CV.destinos && typeof window.CV.destinos.focusFirstEmptyPicker === "function") {
        window.CV.destinos.focusFirstEmptyPicker(destinationSection);
        return;
      }
      var pickers = Array.prototype.slice.call(destinationSection.querySelectorAll(".cv-search-picker__input"));
      var emptyPicker = pickers.find(function (input) {
        return !String(input.value || "").trim();
      });
      var firstPicker = pickers[0];
      var target = emptyPicker || firstPicker;
      if (target) {
        target.focus();
      }
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

    var addButton = form.querySelector("[data-termo-add-destino]");
    var rowsNeeded = indexes[indexes.length - 1] + 1;

    function rowsCount() {
      return form.querySelectorAll("[data-termo-destino-row]").length;
    }

    var guard = 0;
    while (rowsCount() < rowsNeeded && addButton && guard < 50) {
      addButton.click();
      guard += 1;
    }

    var rows = Array.prototype.slice.call(form.querySelectorAll("[data-termo-destino-row]"));
    indexes.forEach(function (idx) {
      var row = rows[idx];
      var entry = entries[idx];
      if (!row || !entry) return;
      var stateSelect = row.querySelector("[data-termo-destino-state]");
      var citySelect = row.querySelector("[data-termo-destino-city]");
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

  function syncEventDates(form) {
    var root = form.querySelector("#termo-evento-date-picker");
    var startHidden = form.querySelector("input[name='data_evento_inicio']");
    var endHidden = form.querySelector("input[name='data_evento_fim']");
    var startDisplay = form.querySelector("[data-termo-evento-start-display]");
    var endDisplay = form.querySelector("[data-termo-evento-end-display]");
    var openButtons = Array.prototype.slice.call(form.querySelectorAll("[data-termo-evento-open-picker]"));

    if (!root || !startHidden || !endHidden || !startDisplay || !endDisplay) return;

    function parseSelectedDates() {
      var raw = root.dataset.selectedDates || "[]";
      var values = [];
      try {
        values = JSON.parse(raw) || [];
      } catch (err) {
        values = [];
      }

      values = values
        .map(function (value) {
          return parseIsoDate(value);
        })
        .filter(function (value) {
          return !!value;
        });

      if (!values.length) {
        var start = parseIsoDate(startHidden.value);
        var end = parseIsoDate(endHidden.value);
        if (start) values.push(start);
        if (end && end !== start) values.push(end);
      }

      values.sort(function (a, b) {
        return a < b ? -1 : a > b ? 1 : 0;
      });

      return values;
    }

    function renderFromDates() {
      var dates = parseSelectedDates();
      var start = dates[0] || "";
      var end = dates[dates.length - 1] || "";
      if (start && !end) {
        end = start;
      }
      if (!start) {
        setInputValue(startHidden, "");
        setInputValue(endHidden, "");
        setInputValue(startDisplay, "");
        setInputValue(endDisplay, "");
        return;
      }
      setInputValue(startHidden, start);
      setInputValue(endHidden, end || start);
      setInputValue(startDisplay, formatDisplayDate(start));
      setInputValue(endDisplay, formatDisplayDate(end || start));
    }

    var observer = new MutationObserver(function (mutations) {
      var changed = mutations.some(function (mutation) {
        return mutation.attributeName === "data-selected-dates";
      });
      if (changed) {
        renderFromDates();
      }
    });

    observer.observe(root, { attributes: true, attributeFilter: ["data-selected-dates"] });
    root.addEventListener("cv:multi-confirm", renderFromDates);

    openButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        if (root._cvDatePicker && root._cvDatePicker.open) {
          root._cvDatePicker.open();
        }
      });
    });

    form.addEventListener("submit", renderFromDates);
    renderFromDates();
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-termo-form]");
    if (!form) return;

    var draft = takeDraft();
    if (draft) applyDraftSimpleFields(form, draft);

    syncOficioSummary(form, readSummaries());
    syncDestinationCities(form);
    syncAddDestinationButton(form);
    syncEventDates(form);

    if (draft) applyDraftDestinos(form, draft);

    bindDraftAutosaveLinks(form);
  });
})();
