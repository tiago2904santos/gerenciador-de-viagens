(function () {
  "use strict";

  var CITIES_CACHE = {};

  /* ── Utilitários ────────────────────────────────────────────── */

  function readSummaries() {
    var script = document.getElementById("os-oficios-summary");
    if (!script) return {};
    try { return JSON.parse(script.textContent || "{}"); } catch (e) { return {}; }
  }

  function isoToDisplay(iso) {
    if (!iso) return "";
    var p = (iso || "").split("-");
    if (p.length !== 3) return "";
    return [p[2], p[1], p[0]].join("/");
  }

  function parseIso(val) {
    if (!val) return "";
    val = String(val).trim();
    return /^\d{4}-\d{2}-\d{2}$/.test(val) ? val : "";
  }

  /* ── cv-search-picker: reset + reinit ──────────────────────── */

  function resetPicker(select) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.resetSearchPicker === "function") {
      window.CV.destinos.resetSearchPicker(select);
      return;
    }
    if (!select || select.dataset.cvSearchPickerReady !== "true") return;
    delete select.dataset.cvSearchPickerReady;
    var next = select.nextElementSibling;
    if (next && next.classList && next.classList.contains("cv-search-picker")) {
      next.parentNode.removeChild(next);
    }
  }

  function initPickers(scope) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.initSearchPickers === "function") {
      window.CV.destinos.initSearchPickers(scope || document);
      return;
    }
    if (window.CvSearchPicker && window.CvSearchPicker.init) {
      window.CvSearchPicker.init(scope || document);
    }
  }

  function updateCitySelect(form, citySelect, cities, selectedCityId) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.setSelectOptions === "function") {
      window.CV.destinos.setSelectOptions(citySelect, cities, selectedCityId, { scope: form });
      return;
    }
    var selected = String(selectedCityId || "");
    resetPicker(citySelect);
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
    initPickers(form);
  }

  function clearCitySelect(form, citySelect) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.clearSelect === "function") {
      window.CV.destinos.clearSelect(citySelect, { scope: form });
      return;
    }
    resetPicker(citySelect);
    citySelect.innerHTML = '<option value="">---------</option>';
    citySelect.disabled = true;
    initPickers(form);
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

    if (CITIES_CACHE[state]) {
      updateCitySelect(form, citySelect, CITIES_CACHE[state], selectedCityId);
      return Promise.resolve(CITIES_CACHE[state]);
    }

    var requestToken = String(Date.now()) + "-" + Math.random().toString(16).slice(2);
    citySelect.dataset.osCitiesRequest = requestToken;
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
        if (citySelect.dataset.osCitiesRequest !== requestToken) {
          return [];
        }
        var cities = Array.isArray(data) ? data : (data.cidades || []);
        CITIES_CACHE[state] = cities;
        updateCitySelect(form, citySelect, cities, selectedCityId);
        return cities;
      })
      .catch(function () {
        if (citySelect.dataset.osCitiesRequest === requestToken) {
          clearCitySelect(form, citySelect);
        }
        return [];
      });
  }

  function syncDestinationCities(form) {
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.initManagedRows === "function") {
      window.CV.destinos.initManagedRows({
        form: form,
        sectionSelector: "#os-evento-destinos",
        addSelector: "[data-os-add-destino]",
        templateSelector: "template[data-os-destino-template]",
        rowSelector: "[data-os-destino-row]",
        stateSelector: "[data-os-destino-state]",
        citySelector: "[data-os-destino-city]",
        removeSelector: "[data-os-remove-destino]",
        indexAttr: "osDestinoIndex",
        primaryStateName: "destino_estado",
        primaryCityName: "destino_cidade",
        extraStatePrefix: "destino_estado_",
        extraCityPrefix: "destino_cidade_",
        managedFlag: "osDestinosManaged",
        readyAttr: "osDestinoReady",
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

  function focusDestinationPicker(form) {
    var destinationSection = form.querySelector("#os-evento-destinos");
    if (!destinationSection) return;
    if (window.CV && window.CV.destinos && typeof window.CV.destinos.focusFirstEmptyPicker === "function") {
      window.CV.destinos.focusFirstEmptyPicker(destinationSection);
      return;
    }

    var pickers = Array.prototype.slice.call(destinationSection.querySelectorAll(".cv-search-picker__input"))
      .filter(function (input) {
        return !input.disabled;
      });
    var emptyPicker = pickers.find(function (input) {
      return !String(input.value || "").trim();
    });
    var target = emptyPicker || pickers[0];
    if (target) {
      window.setTimeout(function () {
        target.focus();
      }, 0);
    }
  }

  function syncAddDestinationButton(form) {
    if (form.dataset.osDestinosManaged === "true") return;
    if (!form.querySelector("[data-os-add-destino]") || form.dataset.osAddDestinoBound === "true") return;
    form.dataset.osAddDestinoBound = "true";

    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-os-add-destino]");
      if (!button || !form.contains(button)) return;

      event.preventDefault();
      event.stopPropagation();
      focusDestinationPicker(form);
    });
  }

  window.OSFocusDestino = function (button) {
    var form = button && button.closest ? button.closest("[data-os-form]") : document.querySelector("[data-os-form]");
    if (form) {
      focusDestinationPicker(form);
    }
  };

  function setMultiSelectValues(select, ids, form) {
    if (!select) return;
    var idSet = new Set(ids.map(String));
    Array.from(select.options).forEach(function (opt) {
      opt.selected = idSet.has(String(opt.value));
    });
    resetPicker(select);
    initPickers(form);
  }

  /* ── Date picker sync ──────────────────────────────────────── */

  function setDateFields(form, startIso, endIso) {
    var startHidden = form.querySelector("input[name='data_evento_inicio']");
    var endHidden   = form.querySelector("input[name='data_evento_fim']");
    var startDisplay = form.querySelector("[data-termo-evento-start-display]");
    var endDisplay   = form.querySelector("[data-termo-evento-end-display]");
    var picker       = form.querySelector("#os-evento-date-picker");

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

  function syncEventDates(form) {
    var root         = form.querySelector("#os-evento-date-picker");
    var startHidden  = form.querySelector("input[name='data_evento_inicio']");
    var endHidden    = form.querySelector("input[name='data_evento_fim']");
    var startDisplay = form.querySelector("[data-termo-evento-start-display]");
    var endDisplay   = form.querySelector("[data-termo-evento-end-display]");
    var openButtons  = Array.prototype.slice.call(form.querySelectorAll("[data-termo-evento-open-picker]"));
    if (!root || !startHidden || !endHidden) return;

    function parseSelectedDates() {
      var raw = root.dataset.selectedDates || "[]";
      var vals = [];
      try { vals = JSON.parse(raw) || []; } catch (e) {}
      vals = vals.map(parseIso).filter(Boolean);
      if (!vals.length) {
        var s = parseIso(startHidden.value);
        var e = parseIso(endHidden.value);
        if (s) vals.push(s);
        if (e && e !== s) vals.push(e);
      }
      vals.sort();
      return vals;
    }

    function renderFromDates() {
      var dates = parseSelectedDates();
      var start = dates[0] || "";
      var end   = dates[dates.length - 1] || start;
      startHidden.value = start;
      endHidden.value   = end;
      if (startDisplay) startDisplay.value = isoToDisplay(start);
      if (endDisplay)   endDisplay.value   = isoToDisplay(end);
    }

    var observer = new MutationObserver(function (mutations) {
      if (mutations.some(function (m) { return m.attributeName === "data-selected-dates"; })) {
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

  /* ── Modelo de motivo → textarea ───────────────────────────── */

  function initModeloMotivo(form) {
    var select = form.querySelector("[data-modelo-motivo-select='true']");
    var motivo = form.querySelector("[data-motivo-textarea='true']");
    if (!select || !motivo) return;

    select.addEventListener("change", function () {
      var opt = this.options[this.selectedIndex];
      if (!opt || !opt.value) return;
      var texto = (opt.dataset.textoMotivo || "").trim();
      if (!texto) return;
      motivo.value = texto;
      motivo.dispatchEvent(new Event("input",  { bubbles: true }));
      motivo.dispatchEvent(new Event("change", { bubbles: true }));
      motivo.focus();
    });
  }

  /* ── Auto-fill a partir dos ofícios selecionados ───────────── */

  function onOficiosChange(form, summaries) {
    var oficiosSelect = form.querySelector("select[name='oficios']");
    if (!oficiosSelect) return;

    var selectedIds = Array.from(oficiosSelect.options)
      .filter(function (o) { return o.selected; })
      .map(function (o) { return o.value; });

    if (!selectedIds.length) { return; }

    var allServidorIds = new Set();
    var startDates     = [];
    var endDates       = [];
    var firstMotivo    = "";

    selectedIds.forEach(function (id) {
      var s = summaries[id];
      if (!s) return;
      (s.servidor_ids || []).forEach(function (sid) { allServidorIds.add(String(sid)); });
      if (s.data_inicio) startDates.push(s.data_inicio);
      if (s.data_fim)    endDates.push(s.data_fim);
      if (!firstMotivo && s.motivo) firstMotivo = s.motivo;
    });

    /* Datas: menor início, maior fim */
    startDates.sort();
    endDates.sort();
    var startIso = startDates[0]                    || "";
    var endIso   = endDates[endDates.length - 1]   || "";
    if (startIso) setDateFields(form, startIso, endIso);

    /* Servidores */
    var servidoresSelect = form.querySelector("select[name='servidores']");
    if (servidoresSelect && allServidorIds.size) {
      setMultiSelectValues(servidoresSelect, Array.from(allServidorIds), form);
    }

    /* Motivo — só preenche se estiver vazio */
    var motivoField = form.querySelector("[data-motivo-textarea='true']");
    if (motivoField && !motivoField.value.trim() && firstMotivo) {
      motivoField.value = firstMotivo;
      motivoField.dispatchEvent(new Event("input",  { bubbles: true }));
      motivoField.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /* Destino — usa o primeiro ofício que tiver estado */
    var destinoStateId = "";
    var destinoCityId = "";
    for (var i = 0; i < selectedIds.length; i++) {
      var sd = summaries[selectedIds[i]];
      if (sd && sd.estado_id) {
        destinoStateId = String(sd.estado_id);
        destinoCityId = String(sd.cidade_id || "");
        break;
      }
    }
    if (destinoStateId) {
      var stateSelect = form.querySelector("select[name='destino_estado']");
      var citySelect  = form.querySelector("select[name='destino_cidade']");
      if (stateSelect && citySelect) {
        stateSelect.value = destinoStateId;
        stateSelect.dispatchEvent(new Event("change", { bubbles: true }));
        loadCitiesForState(form, citySelect, destinoStateId, destinoCityId);
      }
    }
  }

  function initOficioAutoFill(form, summaries) {
    var select = form.querySelector("select[name='oficios']");
    if (!select) return;
    select.addEventListener("change", function () { onOficiosChange(form, summaries); });
    select.addEventListener("input",  function () { onOficiosChange(form, summaries); });
  }

  /* ── Bootstrap ──────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-os-form]");
    if (!form) return;

    var summaries = readSummaries();
    initModeloMotivo(form);
    initOficioAutoFill(form, summaries);
    syncDestinationCities(form);
    syncAddDestinationButton(form);
    syncEventDates(form);
  });
})();
