(function () {
  "use strict";

  var CITIES_CACHE = {};
  var OS_ROLE_ASSIGNMENTS = {};
  var OS_ROLE_LABELS = {
    CONDUCAO: "Condução",
    TECNICO: "Técnico",
    APOIO: "Apoio"
  };

  /* ── Utilitários ────────────────────────────────────────────── */

  function readSummaries() {
    var script = document.getElementById("os-oficios-summary");
    if (!script) return {};
    try { return JSON.parse(script.textContent || "{}"); } catch (e) { return {}; }
  }

  function readRoleAssignments() {
    var script = document.getElementById("os-servidor-funcoes");
    if (!script) return {};
    try {
      var parsed = JSON.parse(script.textContent || "{}");
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (e) {
      return {};
    }
  }

  function isoToDisplay(iso) {
    if (!iso) return "";
    var p = (iso || "").split("-");
    if (p.length !== 3) return "";
    return [p[2], p[1], p[0]].join("/");
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
          return loadCitiesForState(form, citySelect, stateId, selectedCityId).then(function (cities) {
            updateSubmitButtonLabel(form);
            return cities;
          });
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
      ).then(function () { updateSubmitButtonLabel(form); });
    }

    stateSelect.addEventListener("change", onStateChange);
    loadCitiesForState(
      form,
      citySelect,
      stateSelect.value || initialStateId,
      citySelect.value || initialCityId,
    ).then(function () { updateSubmitButtonLabel(form); });
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
    var startDisplay = form.querySelector("#os-evento-date-picker [data-cv-date-picker-start-display]");
    var endDisplay   = form.querySelector("#os-evento-date-picker [data-cv-date-picker-end-display]");
    var picker       = form.querySelector("#os-evento-date-picker");

    var safeEnd = endIso || startIso;
    if (startHidden)  startHidden.value  = startIso || "";
    if (endHidden)    endHidden.value    = safeEnd  || "";
    if (startDisplay) startDisplay.value = isoToDisplay(startIso);
    if (endDisplay)   endDisplay.value   = isoToDisplay(safeEnd);
    if (picker && picker._cvDatePicker && typeof picker._cvDatePicker.setRange === "function") {
      picker._cvDatePicker.setRange(startIso || "", safeEnd || "");
    }
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

  /* ── Modelo de OS → campos condicionais ───────────────────── */

  function selectedOsModel(form) {
    var checked = form.querySelector("input[name='tipo_necessidade']:checked");
    return checked ? checked.value : "";
  }

  function syncOsModelFields(form) {
    var model = selectedOsModel(form);
    form.querySelectorAll("[data-os-model-fields]").forEach(function (group) {
      var models = String(group.dataset.osModelFields || "").split(/\s+/).filter(Boolean);
      group.hidden = models.indexOf(model) === -1;
    });
    form.querySelectorAll(".os-model-card").forEach(function (card) {
      var input = card.querySelector("input[name='tipo_necessidade']");
      card.classList.toggle("is-selected", !!input && input.checked);
    });
    syncServidorRoleUi(form);
    updateSubmitButtonLabel(form);
  }

  function initOsModelPicker(form) {
    if (!form.querySelector("[data-os-model-picker]")) return;
    form.addEventListener("change", function (event) {
      if (event.target && event.target.name === "tipo_necessidade") {
        syncOsModelFields(form);
      }
    });
    syncOsModelFields(form);
  }

  /* ── Caminhão: função direto nos cards de servidores ────────── */

  function selectedServidorIds(form) {
    var select = form.querySelector("select[name='servidores']");
    if (!select) return [];
    return Array.from(select.options)
      .filter(function (option) { return option.selected; })
      .map(function (option) { return String(option.value); })
      .filter(Boolean);
  }

  function activeServidorRole(form) {
    var active = form.querySelector("[data-os-role-mode][aria-pressed='true']");
    return active ? active.dataset.osRoleMode : "CONDUCAO";
  }

  function syncServidorRoleButtons(form) {
    form.querySelectorAll("[data-os-role-mode]").forEach(function (button) {
      var active = button.dataset.osRoleMode === activeServidorRole(form);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function pruneServidorRoles(form) {
    var selected = new Set(selectedServidorIds(form));
    Object.keys(OS_ROLE_ASSIGNMENTS).forEach(function (id) {
      if (!selected.has(String(id))) {
        delete OS_ROLE_ASSIGNMENTS[id];
      }
    });
  }

  function syncServidorRoleInputs(form) {
    form.querySelectorAll("[data-os-servidor-role-input]").forEach(function (input) {
      input.remove();
    });
    if (selectedOsModel(form) !== "CAMINHAO") return;

    selectedServidorIds(form).forEach(function (id) {
      var role = OS_ROLE_ASSIGNMENTS[id];
      if (!role) return;
      var input = document.createElement("input");
      input.type = "hidden";
      input.name = "funcao_servidor_" + id;
      input.value = role;
      input.dataset.osServidorRoleInput = "true";
      form.appendChild(input);
    });
  }

  function renderServidorRoleCard(card, role, active) {
    card.classList.toggle("os-servidor-role-card", active);
    card.classList.toggle("os-servidor-role-card--assigned", !!role && active);
    card.dataset.osServidorRole = role || "";

    var badge = card.querySelector("[data-os-role-badge]");
    if (!active) {
      if (badge) badge.remove();
      return;
    }
    if (!badge) {
      badge = document.createElement("span");
      badge.className = "os-servidor-role-badge";
      badge.dataset.osRoleBadge = "true";
      var titleRow = card.querySelector(".cv-search-picker__selected-title-row");
      if (titleRow) {
        titleRow.appendChild(badge);
      } else {
        card.appendChild(badge);
      }
    }
    var label = role ? OS_ROLE_LABELS[role] : "Sem função - texto padrão";
    badge.textContent = label;
  }

  function syncServidorRoleUi(form) {
    var select = form.querySelector("select[name='servidores']");
    if (!select) return;
    var picker = select.nextElementSibling && select.nextElementSibling.classList.contains("cv-search-picker")
      ? select.nextElementSibling
      : null;
    var isTruck = selectedOsModel(form) === "CAMINHAO";
    pruneServidorRoles(form);
    syncServidorRoleButtons(form);
    syncServidorRoleInputs(form);

    if (!picker) return;
    picker.querySelectorAll(".cv-search-picker__selected-card[data-value]").forEach(function (card) {
      var servidorId = String(card.dataset.value || "");
      renderServidorRoleCard(card, OS_ROLE_ASSIGNMENTS[servidorId], isTruck);
    });
  }

  function initServidorRolePicker(form) {
    OS_ROLE_ASSIGNMENTS = readRoleAssignments();
    form.addEventListener("click", function (event) {
      if (selectedOsModel(form) !== "CAMINHAO") return;
      if (event.target.closest("[data-os-role-mode]")) return;
      if (event.target.closest(".cv-search-picker__remove")) return;

      var card = event.target.closest(".cv-search-picker__selected-card[data-value]");
      if (!card || !form.contains(card)) return;
      var servidoresSelect = form.querySelector("select[name='servidores']");
      var picker = servidoresSelect && servidoresSelect.nextElementSibling && servidoresSelect.nextElementSibling.classList.contains("cv-search-picker")
        ? servidoresSelect.nextElementSibling
        : null;
      if (!picker || !picker.contains(card)) return;

      var servidorId = String(card.dataset.value || "");
      if (!servidorId) return;
      var role = activeServidorRole(form);
      if (OS_ROLE_ASSIGNMENTS[servidorId] === role) {
        delete OS_ROLE_ASSIGNMENTS[servidorId];
      } else {
        OS_ROLE_ASSIGNMENTS[servidorId] = role;
      }
      syncServidorRoleUi(form);
      form.dispatchEvent(new Event("change", { bubbles: true }));
    }, true);

    form.addEventListener("click", function (event) {
      var button = event.target.closest("[data-os-role-mode]");
      if (!button || !form.contains(button)) return;
      form.querySelectorAll("[data-os-role-mode]").forEach(function (candidate) {
        candidate.setAttribute("aria-pressed", candidate === button ? "true" : "false");
      });
      syncServidorRoleUi(form);
    });
    form.addEventListener("change", function (event) {
      if (event.target && event.target.name === "servidores") {
        window.setTimeout(function () { syncServidorRoleUi(form); }, 0);
      }
    });
    window.setTimeout(function () { syncServidorRoleUi(form); }, 0);
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
      syncServidorRoleUi(form);
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
        loadCitiesForState(form, citySelect, destinoStateId, destinoCityId).then(function () {
          updateSubmitButtonLabel(form);
        });
      }
    }

    updateSubmitButtonLabel(form);
  }

  function initOficioAutoFill(form, summaries) {
    var select = form.querySelector("select[name='oficios']");
    if (!select) return;
    select.addEventListener("change", function () { onOficiosChange(form, summaries); });
    select.addEventListener("input",  function () { onOficiosChange(form, summaries); });
  }

  /* ── Rótulo do botão principal: "Finalizar Ordem de Serviço" ou "Salvar como rascunho" ── */

  function osIsCompleta(form) {
    var startHidden = form.querySelector("input[name='data_evento_inicio']");
    var endHidden = form.querySelector("input[name='data_evento_fim']");
    var destinoCidade = form.querySelector("select[name='destino_cidade']");
    var servidoresSelect = form.querySelector("select[name='servidores']");
    var motivoField = form.querySelector("[data-motivo-textarea='true']");
    var model = selectedOsModel(form);

    var temDatas = !!(startHidden && startHidden.value) && !!(endHidden && endHidden.value);
    var temDestino = !!(destinoCidade && destinoCidade.value);
    var temServidores = !!servidoresSelect && Array.from(servidoresSelect.options).some(function (o) { return o.selected; });
    var temTipoNecessidade = !!model;
    var temMotivo = !!(motivoField && motivoField.value.trim());
    var temEquipe = temServidores;

    if (model === "CAMINHAO" || model === "MICROONIBUS") {
      if (model === "CAMINHAO") {
        temEquipe = temServidores;
      } else {
        temEquipe = ["motorista_equipe", "tecnico_equipe", "apoio_montagem", "apoio_escolta"].every(function (name) {
        var field = form.querySelector("select[name='" + name + "']");
        return !!(field && field.value);
      });
      }
    } else if (model === "CERIMONIAL_ANTECIPADO") {
      temEquipe = ["coordenador_cerimonial", "apoio_cerimonial", "apoio_preparacao"].every(function (name) {
        var field = form.querySelector("select[name='" + name + "']");
        return !!(field && field.value);
      });
    }

    return temDatas && temDestino && temEquipe && temTipoNecessidade && temMotivo;
  }

  function updateSubmitButtonLabel(form) {
    var button = form.querySelector(".os-submit-btn span:not(.cv-btn__icon)");
    if (!button) return;
    button.textContent = osIsCompleta(form) ? "Finalizar Ordem de Serviço" : "Salvar como rascunho";
  }

  function initSubmitButtonLabel(form) {
    updateSubmitButtonLabel(form);

    var debounceTimer = null;
    function debouncedUpdate() {
      window.clearTimeout(debounceTimer);
      debounceTimer = window.setTimeout(function () { updateSubmitButtonLabel(form); }, 150);
    }
    form.addEventListener("input", debouncedUpdate);
    form.addEventListener("change", debouncedUpdate);
  }

  /* ── Draft: preserva o formulário ao navegar para "Gerenciar modelos" / "Cadastrar servidor" ── */

  function draftStorageKey() {
    return "osFormDraft:" + window.location.pathname + window.location.search;
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

  function bindDraftAutosaveLinks(form) {
    form.addEventListener("click", function (event) {
      var link = event.target.closest('[data-autosave-link="1"]');
      if (!link || !form.contains(link)) return;
      saveDraft(form);
    });
  }

  function applyDraftDestinos(form, draft) {
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

    var indexes = Object.keys(entries)
      .map(Number)
      .filter(function (idx) {
        var entry = entries[idx];
        return entry && (entry.estado || entry.cidade);
      })
      .sort(function (a, b) { return a - b; });
    if (!indexes.length) return;

    var addButton = form.querySelector("[data-os-add-destino]");

    function rowsCount() {
      return form.querySelectorAll("[data-os-destino-row]").length;
    }

    var rowsNeeded = indexes[indexes.length - 1] + 1;
    var guard = 0;
    while (rowsCount() < rowsNeeded && addButton && guard < 50) {
      addButton.click();
      guard += 1;
    }

    var rows = Array.prototype.slice.call(form.querySelectorAll("[data-os-destino-row]"));
    indexes.forEach(function (idx) {
      var row = rows[idx];
      var entry = entries[idx];
      if (!row || !entry) return;
      var stateSelect = row.querySelector("[data-os-destino-state]");
      var citySelect = row.querySelector("[data-os-destino-city]");
      if (!stateSelect) return;
      stateSelect.value = entry.estado || "";
      resetPicker(stateSelect);
      initPickers(form);
      if (entry.estado && citySelect) {
        loadCitiesForState(form, citySelect, entry.estado, entry.cidade || "").then(function () {
          initPickers(form);
          updateSubmitButtonLabel(form);
        });
      }
    });
  }

  function applyDraft(form, draft) {
    if (draft.oficios && draft.oficios.length) {
      var oficiosSelect = form.querySelector("select[name='oficios']");
      setMultiSelectValues(oficiosSelect, draft.oficios, form);
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

    applyDraftDestinos(form, draft);

    if (draft.modelo_motivo && draft.modelo_motivo.length) {
      var modeloSelect = form.querySelector("[data-modelo-motivo-select='true']");
      if (modeloSelect) modeloSelect.value = draft.modelo_motivo[0];
    }

    if (draft.tipo_necessidade && draft.tipo_necessidade.length) {
      var tipoInput = form.querySelector("input[name='tipo_necessidade'][value='" + draft.tipo_necessidade[0] + "']");
      if (tipoInput) tipoInput.checked = true;
    }

    ["motorista_equipe", "tecnico_equipe", "apoio_montagem", "apoio_escolta", "coordenador_cerimonial", "apoio_cerimonial", "apoio_preparacao"].forEach(function (name) {
      if (!draft[name] || !draft[name].length) return;
      var field = form.querySelector("select[name='" + name + "']");
      if (field) {
        field.value = draft[name][0];
        resetPicker(field);
        initPickers(form);
      }
    });

    Object.keys(draft).forEach(function (name) {
      if (!name.startsWith("funcao_servidor_") || !draft[name] || !draft[name].length) return;
      var servidorId = name.replace("funcao_servidor_", "");
      var role = String(draft[name][0] || "").toUpperCase();
      if (OS_ROLE_LABELS[role]) {
        OS_ROLE_ASSIGNMENTS[servidorId] = role;
      }
    });

    if (draft.motivo && draft.motivo.length) {
      var motivoField = form.querySelector("[data-motivo-textarea='true']");
      if (motivoField) {
        motivoField.value = draft.motivo[0];
        motivoField.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }

    syncOsModelFields(form);
    syncServidorRoleUi(form);
    updateSubmitButtonLabel(form);
  }

  /* ── Bootstrap ──────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-os-form]");
    if (!form) return;

    var summaries = readSummaries();
    initModeloMotivo(form);
    initOsModelPicker(form);
    initServidorRolePicker(form);
    initOficioAutoFill(form, summaries);
    syncDestinationCities(form);
    syncAddDestinationButton(form);
    bindDraftAutosaveLinks(form);
    initSubmitButtonLabel(form);

    var draft = takeDraft();
    if (draft) {
      applyDraft(form, draft);
    }
  });
})();
