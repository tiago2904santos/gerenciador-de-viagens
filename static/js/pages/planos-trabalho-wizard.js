(function () {
  "use strict";

  var CITIES_CACHE = {};

  /* ── Utilitários (clonados de ordens-servico-form.js) ───────── */

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

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  /* ── cv-search-picker: reset + reinit ──────────────────────── */

  function resetPicker(select) {
    if (!select || select.dataset.cvSearchPickerReady !== "true") return;
    delete select.dataset.cvSearchPickerReady;
    var next = select.nextElementSibling;
    if (next && next.classList && next.classList.contains("cv-search-picker")) {
      next.parentNode.removeChild(next);
    }
  }

  function initPickers(scope) {
    if (window.CvSearchPicker && window.CvSearchPicker.init) {
      window.CvSearchPicker.init(scope || document);
    }
  }

  function updateCitySelect(form, citySelect, cities, selectedCityId) {
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
    citySelect.dataset.ptCitiesRequest = requestToken;
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
        if (citySelect.dataset.ptCitiesRequest !== requestToken) {
          return [];
        }
        var cities = Array.isArray(data) ? data : (data.cidades || []);
        CITIES_CACHE[state] = cities;
        updateCitySelect(form, citySelect, cities, selectedCityId);
        return cities;
      })
      .catch(function () {
        if (citySelect.dataset.ptCitiesRequest === requestToken) {
          clearCitySelect(form, citySelect);
        }
        return [];
      });
  }

  function bindDestinationRow(form, row) {
    if (!row || row.dataset.ptDestinoReady === "true") return;
    row.dataset.ptDestinoReady = "true";
    var stateSelect = row.querySelector("[data-pt-destino-state]");
    var citySelect = row.querySelector("[data-pt-destino-city]");
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

    var removeButton = row.querySelector("[data-pt-remove-destino]");
    if (removeButton) {
      removeButton.addEventListener("click", function () {
        row.remove();
      });
    }
  }

  function syncDestinationCities(form) {
    Array.prototype.slice.call(form.querySelectorAll("[data-pt-destino-row]")).forEach(function (row) {
      bindDestinationRow(form, row);
    });

    var addButton = form.querySelector("[data-pt-add-destino]");
    var template = form.querySelector("template[data-pt-destino-template]");
    var list = form.querySelector(".roteiro-destinos-list");
    if (!addButton || !template || !list) return;

    addButton.addEventListener("click", function () {
      var indexes = Array.prototype.slice.call(form.querySelectorAll("[data-pt-destino-row]")).map(function (row) {
        return parseInt(row.dataset.ptDestinoIndex || "0", 10);
      }).filter(function (value) {
        return !isNaN(value);
      });
      var nextIndex = indexes.length ? Math.max.apply(Math, indexes) + 1 : 1;
      var html = template.innerHTML.replace(/__index__/g, String(nextIndex));
      var holder = document.createElement("div");
      holder.innerHTML = html.trim();
      var row = holder.firstElementChild;
      var existingRows = Array.prototype.slice.call(form.querySelectorAll("[data-pt-destino-row]"));
      var referenceRow = existingRows.length ? existingRows[existingRows.length - 1] : null;
      var referenceState = referenceRow ? referenceRow.querySelector("[data-pt-destino-state]") : null;
      var referenceStateId = referenceState
        ? String(referenceState.value || referenceState.dataset.pickerInitialValue || "").trim()
        : "";
      if (referenceStateId) {
        var newStateSelect = row.querySelector("[data-pt-destino-state]");
        if (newStateSelect) {
          newStateSelect.value = referenceStateId;
          newStateSelect.dataset.pickerInitialValue = referenceStateId;
        }
      }
      list.appendChild(row);
      bindDestinationRow(form, row);
      initPickers(form);
    });
  }

  function syncProgramaOutros(form) {
    var programaSelect = form.querySelector("[data-pt-programa-select]");
    var programaOutrosField = form.querySelector("[data-pt-programa-outros-field]");
    if (!programaSelect || !programaOutrosField) return;

    var outroValue = programaSelect.dataset.ptProgramaOutroValue || "__outro__";
    var outrosInput = programaOutrosField.querySelector("input[name='programa_outros']");

    function applyProgramaMode() {
      var isOutro = programaSelect.value === outroValue;
      programaOutrosField.hidden = !isOutro;
      if (!outrosInput) return;
      if (isOutro) {
        outrosInput.removeAttribute("disabled");
      } else {
        outrosInput.setAttribute("disabled", "disabled");
        outrosInput.value = "";
      }
    }

    programaSelect.addEventListener("change", applyProgramaMode);
    applyProgramaMode();
  }

  /* ── Textos padrão: pré-preenchimento ao vivo (editável) ───── */

  var _PT_MINORES = { de: 1, da: 1, do: 1, das: 1, dos: 1, e: 1, a: 1, o: 1, no: 1, na: 1, em: 1, "à": 1 };

  function ptTitleCase(value) {
    return String(value || "")
      .toLowerCase()
      .split(/\s+/)
      .map(function (word, index) {
        if (!word) return word;
        if (index > 0 && _PT_MINORES[word]) return word;
        return word.charAt(0).toUpperCase() + word.slice(1);
      })
      .join(" ");
  }

  function computeMunicipio(form) {
    var labels = [];
    Array.prototype.slice.call(form.querySelectorAll("[data-pt-destino-row]")).forEach(function (row) {
      if (row.hidden) return;
      var stateSelect = row.querySelector("[data-pt-destino-state]");
      var citySelect = row.querySelector("[data-pt-destino-city]");
      if (!citySelect || !citySelect.value) return;
      var cityOption = citySelect.options[citySelect.selectedIndex];
      var cityText = cityOption ? cityOption.text.trim() : "";
      if (!cityText) return;
      var uf = "";
      if (stateSelect && stateSelect.options[stateSelect.selectedIndex]) {
        var match = stateSelect.options[stateSelect.selectedIndex].text.match(/\(([A-Za-z]{2})\)/);
        if (match) uf = match[1].toUpperCase();
      }
      var label = ptTitleCase(cityText) + (uf ? "/" + uf : "");
      if (labels.indexOf(label) < 0) labels.push(label);
    });
    return labels.length ? labels.join(", ") : "________";
  }

  function computePrograma(form) {
    var select = form.querySelector("[data-pt-programa-select]");
    if (!select) return "________";
    var outroValue = select.dataset.ptProgramaOutroValue || "__outro__";
    if (select.value === outroValue) {
      var input = form.querySelector("input[name='programa_outros']");
      var raw = input ? input.value.trim() : "";
      return raw ? ptTitleCase(raw) : "________";
    }
    if (!select.value) return "________";
    var option = select.options[select.selectedIndex];
    return option ? ptTitleCase(option.text.trim()) : "________";
  }

  function initTextosPadrao(form) {
    var dataEl = document.getElementById("pt-textos-padrao-data");
    if (!dataEl) return;
    var templates = {};
    try { templates = JSON.parse(dataEl.textContent || "{}"); } catch (e) { templates = {}; }

    var programmatic = false;
    var fields = [
      { name: "contextualizacao", flag: "contextualizacao" },
      { name: "consideracao_final", flag: "consideracao_final" },
    ];

    fields.forEach(function (field) {
      field.textarea = form.querySelector("textarea[name='" + field.name + "']");
      field.flagInput = form.querySelector("[data-pt-texto-auto-flag='" + field.flag + "']");
      if (field.textarea) {
        field.textarea.addEventListener("input", function () {
          if (programmatic) return;
          if (field.flagInput) field.flagInput.value = "0";
        });
      }
    });

    function regenerate() {
      var municipio = computeMunicipio(form);
      var programa = computePrograma(form);
      fields.forEach(function (field) {
        if (!field.textarea || !field.flagInput) return;
        if (field.flagInput.value !== "1") return; // usuário já editou manualmente
        var template = templates[field.name] || "";
        if (!template) return;
        programmatic = true;
        field.textarea.value = template
          .replace(/\{municipio\}/g, municipio)
          .replace(/\{programa\}/g, programa);
        programmatic = false;
      });
    }

    form.addEventListener("change", function (event) {
      var target = event.target;
      if (!target) return;
      if (
        target.matches("[data-pt-destino-city], [data-pt-destino-state], [data-pt-programa-select]") ||
        target.name === "programa_outros"
      ) {
        regenerate();
      }
    });
    form.addEventListener("input", function (event) {
      if (event.target && event.target.name === "programa_outros") regenerate();
    });
  }

  /* ── Coordenadores: picker com texto livre no mesmo input ───── */

  function dispatchFieldEvent(field, eventName) {
    if (!field) return;
    field.dispatchEvent(new Event(eventName, { bubbles: true }));
  }

  function selectedOption(select) {
    if (!select || !select.value) return null;
    return select.options[select.selectedIndex] || null;
  }

  function setSelectValue(select, value, options) {
    if (!select) return;
    options = options || {};
    var nextValue = String(value || "");
    if (nextValue && !Array.prototype.slice.call(select.options).some(function (option) {
      return option.value === nextValue;
    })) {
      var option = document.createElement("option");
      option.value = nextValue;
      option.textContent = nextValue;
      select.appendChild(option);
    }
    select.value = nextValue;
    if (!options.silent) dispatchFieldEvent(select, "change");
  }

  function setHiddenValue(input, value, options) {
    if (!input) return;
    options = options || {};
    var nextValue = String(value || "");
    if (input.value === nextValue) return;
    input.value = nextValue;
    if (!options.silent) dispatchFieldEvent(input, "change");
  }

  function clearServidorSelection(select) {
    if (!select || !select.value) return false;
    Array.prototype.slice.call(select.options).forEach(function (option) {
      option.selected = false;
    });
    select.value = "";
    dispatchFieldEvent(select, "input");
    return true;
  }

  function initCoordenadorPanel(panel) {
    if (!panel || panel.dataset.ptCoordenadorReady === "true") return;
    panel.dataset.ptCoordenadorReady = "true";

    var servidorSelect = panel.querySelector("select[data-pt-coordenador-picker]");
    if (!servidorSelect) return;

    var manualName = servidorSelect.dataset.ptCoordenadorManualName || "";
    var cargoName = servidorSelect.dataset.ptCoordenadorCargoName || "";
    var modoName = servidorSelect.dataset.ptCoordenadorModoName || "";
    var manualInput = manualName ? panel.querySelector("[name='" + manualName + "']") : null;
    var cargoSelect = cargoName ? panel.querySelector("[name='" + cargoName + "']") : null;
    var modoInput = modoName ? panel.querySelector("[name='" + modoName + "']") : null;
    var pickerRoot = servidorSelect.nextElementSibling;
    var pickerInput = pickerRoot && pickerRoot.classList.contains("cv-search-picker")
      ? pickerRoot.querySelector(".cv-search-picker__input")
      : null;
    var clearButton = pickerRoot ? pickerRoot.querySelector(".cv-search-picker__clear") : null;
    if (!pickerInput) return;

    var syncing = false;

    function applyServidorSelection(option, options) {
      if (!option) return;
      options = options || {};
      syncing = true;
      setHiddenValue(manualInput, "", options);
      setHiddenValue(modoInput, "SERVIDOR", options);
      setSelectValue(cargoSelect, option.dataset.cargo || "", options);
      syncing = false;
    }

    function applyManualName(options) {
      options = options || {};
      var name = (pickerInput.value || "").trim();
      var hadServidor = clearServidorSelection(servidorSelect);
      setHiddenValue(manualInput, name);
      setHiddenValue(modoInput, name ? "MANUAL" : "");
      if (!name || hadServidor || options.clearCargo) {
        setSelectValue(cargoSelect, "");
      }
    }

    servidorSelect.addEventListener("change", function () {
      if (syncing) return;
      var option = selectedOption(servidorSelect);
      if (option) {
        applyServidorSelection(option);
      } else if (!(pickerInput.value || "").trim()) {
        applyManualName({ clearCargo: true });
      }
    });

    pickerInput.addEventListener("input", function () {
      if (syncing) return;
      applyManualName();
    });

    if (clearButton) {
      clearButton.addEventListener("click", function () {
        window.setTimeout(function () {
          applyManualName({ clearCargo: true });
        }, 0);
      });
    }

    var initialOption = selectedOption(servidorSelect);
    if (initialOption) {
      applyServidorSelection(initialOption, { silent: true });
    } else if (manualInput && manualInput.value) {
      pickerInput.value = manualInput.value;
      if (pickerRoot) pickerRoot.classList.add("cv-search-picker--has-query");
      setHiddenValue(modoInput, "MANUAL", { silent: true });
    }
  }

  function initCoordenadores(form) {
    initPickers(form);
    Array.prototype.slice.call(form.querySelectorAll("[data-pt-coordenador-panel]")).forEach(initCoordenadorPanel);
  }

  /* ── Date picker sync (clonado de ordens-servico-form.js) ──── */

  function syncEventDates(form) {
    var root = form.querySelector("#pt-evento-date-picker");
    var startHidden = form.querySelector("input[name='data_evento_inicio']");
    var endHidden = form.querySelector("input[name='data_evento_fim']");
    var startDisplay = form.querySelector("[data-termo-evento-start-display]");
    var endDisplay = form.querySelector("[data-termo-evento-end-display]");
    var openButtons = Array.prototype.slice.call(form.querySelectorAll("[data-termo-evento-open-picker]"));
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
      var end = dates[dates.length - 1] || start;
      startHidden.value = start;
      endHidden.value = end;
      if (startDisplay) startDisplay.value = isoToDisplay(start);
      if (endDisplay) endDisplay.value = isoToDisplay(end);
      startHidden.dispatchEvent(new Event("change", { bubbles: true }));
      endHidden.dispatchEvent(new Event("change", { bubbles: true }));
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

    var outerForm = form.closest("form") || form;
    outerForm.addEventListener("submit", renderFromDates);
    renderFromDates();
  }

  /* ── Etapa 2: linhas de efetivo (formset dinâmico) ─────────── */

  function initEfetivoFormset(scope) {
    var rowsContainer = scope.querySelector("[data-pt-efetivo-rows]");
    var template = scope.querySelector("template[data-pt-efetivo-template]");
    var addButton = scope.querySelector("[data-pt-efetivo-add]");
    var totalInput = scope.querySelector("input[name='efetivo-TOTAL_FORMS']");
    if (!rowsContainer || !template || !addButton || !totalInput) return;

    addButton.addEventListener("click", function () {
      var index = parseInt(totalInput.value || "0", 10);
      var html = template.innerHTML.replace(/__prefix__/g, String(index));
      var holder = document.createElement("div");
      holder.innerHTML = html.trim();
      var row = holder.firstElementChild;
      rowsContainer.appendChild(row);
      totalInput.value = String(index + 1);
      bindEfetivoInputs(scope, row);
      initPickers(scope);
      updateEfetivoRemoveButtons(scope);
    });

    Array.prototype.slice.call(rowsContainer.querySelectorAll("[data-pt-efetivo-row]")).forEach(function (row) {
      bindEfetivoInputs(scope, row);
    });
    updateEfetivoRemoveButtons(scope);
  }

  function bindEfetivoInputs(scope, row) {
    var removeBtn = row.querySelector("[data-pt-efetivo-remove]");
    if (removeBtn && row.dataset.ptEfetivoRemoveReady !== "true") {
      row.dataset.ptEfetivoRemoveReady = "true";
      removeBtn.addEventListener("click", function () {
        var deleteInput = row.querySelector("input[name$='-DELETE']");
        var idInput = row.querySelector("input[name$='-id']");
        if (deleteInput && idInput && idInput.value) {
          deleteInput.checked = true;
          row.hidden = true;
        } else {
          row.remove();
        }
        updateEfetivoRemoveButtons(scope);
        notifyEfetivoChanged(scope);
      });
    }

    Array.prototype.slice.call(row.querySelectorAll("input, select")).forEach(function (input) {
      input.addEventListener("change", function () { notifyEfetivoChanged(scope); });
      input.addEventListener("input", function () { notifyEfetivoChanged(scope); });
    });
  }

  function updateEfetivoRemoveButtons(scope) {
    var visibleRows = Array.prototype.slice.call(scope.querySelectorAll("[data-pt-efetivo-row]")).filter(function (row) {
      if (row.hidden) return false;
      var deleteInput = row.querySelector("input[name$='-DELETE']");
      return !(deleteInput && deleteInput.checked);
    });

    visibleRows.forEach(function (row, index) {
      var removeBtn = row.querySelector("[data-pt-efetivo-remove]");
      if (!removeBtn) return;
      removeBtn.hidden = visibleRows.length <= 1 && index === 0;
      row.classList.toggle("destino-row--single", visibleRows.length <= 1 && index === 0);
    });
  }

  function totalEfetivo(scope) {
    var total = 0;
    Array.prototype.slice.call(scope.querySelectorAll("[data-pt-efetivo-row]")).forEach(function (row) {
      var deleteInput = row.querySelector("input[name$='-DELETE']");
      if (deleteInput && deleteInput.checked) return;
      if (row.hidden) return;
      var unidade = row.querySelector("select[name$='-unidade']");
      var cargo = row.querySelector("select[name$='-cargo']");
      var qtd = row.querySelector("input[name$='-quantidade']");
      if (!unidade || !unidade.value || !cargo || !cargo.value) return;
      var n = parseInt((qtd && qtd.value) || "0", 10);
      if (!isNaN(n) && n > 0) total += n;
    });
    return total;
  }

  /* ── Etapa 2: cálculo ao vivo das diárias ──────────────────── */

  var calcTimer = null;

  function notifyEfetivoChanged(scope) {
    scheduleCalc(scope);
  }

  function scheduleCalc(scope) {
    if (calcTimer) window.clearTimeout(calcTimer);
    calcTimer = window.setTimeout(function () { runCalc(scope); }, 350);
  }

  function fieldValue(scope, name) {
    var input = scope.querySelector("[name='" + name + "']");
    return input ? input.value : "";
  }

  function setText(scope, selector, value) {
    var el = scope.querySelector(selector);
    if (el) el.textContent = value;
  }

  function runCalc(scope) {
    var url = scope.dataset.apiCalcularUrl || "";
    if (!url) return;
    var payload = {
      saida_sede_data: fieldValue(scope, "saida_sede_data"),
      saida_sede_hora: fieldValue(scope, "saida_sede_hora"),
      chegada_sede_data: fieldValue(scope, "chegada_sede_data"),
      chegada_sede_hora: fieldValue(scope, "chegada_sede_hora"),
      total_efetivo: totalEfetivo(scope),
    };
    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken"),
      },
      body: JSON.stringify(payload),
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        var errosEl = scope.querySelector("[data-pt-diarias-erros]");
        if (!data.ok) {
          setText(scope, "[data-pt-resultado-composicao]", "—");
          setText(scope, "[data-pt-resultado-efetivo]", "—");
          setText(scope, "[data-pt-resultado-unitario]", "—");
          setText(scope, "[data-pt-resultado-unitario-extenso]", "—");
          setText(scope, "[data-pt-resultado-total]", "—");
          setText(scope, "[data-pt-resultado-total-extenso]", "—");
          if (errosEl) {
            var erros = data.erros;
            if (erros && !Array.isArray(erros)) {
              erros = Object.keys(erros).map(function (k) { return erros[k].join(" "); });
            }
            errosEl.textContent = (erros || []).join(" ");
          }
          return;
        }
        if (errosEl) errosEl.textContent = "";
        setText(scope, "[data-pt-resultado-composicao]", data.composicao || "—");
        setText(scope, "[data-pt-resultado-efetivo]", String(data.quantidade_servidores) + " servidor(es)");
        setText(scope, "[data-pt-resultado-unitario]", "R$" + data.valor_unitario_display);
        setText(scope, "[data-pt-resultado-unitario-extenso]", data.valor_unitario_extenso || "—");
        setText(scope, "[data-pt-resultado-total]", "R$" + data.valor_total_display);
        setText(scope, "[data-pt-resultado-total-extenso]", data.valor_total_extenso || "—");
      })
      .catch(function () { /* silencioso — o cálculo definitivo acontece no salvar */ });
  }

  function initDiariasLiveCalc(scope) {
    Array.prototype.slice.call(scope.querySelectorAll("[data-pt-diarias-input]")).forEach(function (input) {
      input.addEventListener("change", function () { scheduleCalc(scope); });
    });
  }

  /* ── Etapa 3: seleção de atividades + preview ao vivo ──────── */

  function setChipLabel(wrapper, text) {
    if (!wrapper) return;
    var label = wrapper.querySelector(".cv-chip__label");
    if (label) label.textContent = text;
  }

  function buildCatalogMap() {
    var dataEl = document.getElementById("pt-atividades-data");
    var map = {};
    if (!dataEl) return map;
    var list = [];
    try { list = JSON.parse(dataEl.textContent || "[]"); } catch (e) { list = []; }
    list.forEach(function (item) {
      if (item && item.codigo) map[item.codigo] = item;
    });
    return map;
  }

  function renderLiveList(listEl, emptyEl, countEl, values) {
    setChipLabel(countEl, String(values.length));
    if (listEl) {
      listEl.innerHTML = "";
      values.forEach(function (text) {
        var li = document.createElement("li");
        li.className = "pt-live-entry";
        var span = document.createElement("span");
        span.className = "pt-live-entry-text";
        span.textContent = text;
        li.appendChild(span);
        listEl.appendChild(li);
      });
    }
    if (emptyEl) emptyEl.hidden = values.length > 0;
  }

  function initAtividades(scope) {
    var catalog = buildCatalogMap();
    var counter = scope.querySelector("[data-pt-activity-counter]");
    var checkboxes = Array.prototype.slice.call(scope.querySelectorAll("[data-pt-activity-checkbox]"));
    var selectAll = scope.querySelector("[data-pt-activity-select-all]");
    var clearBtn = scope.querySelector("[data-pt-activity-clear]");
    var search = scope.querySelector("[data-pt-activity-search]");
    var items = Array.prototype.slice.call(scope.querySelectorAll("[data-pt-activity-item]"));
    var emptyFilter = scope.querySelector("[data-pt-activity-empty]");

    var metasList = scope.querySelector("[data-pt-live-metas-list]");
    var metasEmpty = scope.querySelector("[data-pt-live-metas-empty]");
    var metasCount = scope.querySelector("[data-pt-live-metas-count]");
    var recursosList = scope.querySelector("[data-pt-live-recursos-list]");
    var recursosEmpty = scope.querySelector("[data-pt-live-recursos-empty]");
    var recursosCount = scope.querySelector("[data-pt-live-recursos-count]");

    function refresh() {
      var checked = checkboxes.filter(function (cb) { return cb.checked; });
      setChipLabel(counter, checked.length + " selecionadas");
      var metas = [];
      var metasSeen = {};
      var recursos = [];
      var recursosSeen = {};
      checked.forEach(function (cb) {
        var item = catalog[cb.value];
        if (!item) return;
        var meta = (item.meta || "").trim();
        if (meta && !metasSeen[meta]) { metasSeen[meta] = true; metas.push(meta); }
        var recurso = (item.recurso || "").trim();
        if (recurso && !recursosSeen[recurso]) { recursosSeen[recurso] = true; recursos.push(recurso); }
      });
      renderLiveList(metasList, metasEmpty, metasCount, metas);
      renderLiveList(recursosList, recursosEmpty, recursosCount, recursos);
    }

    checkboxes.forEach(function (cb) {
      cb.addEventListener("change", refresh);
    });

    if (selectAll) {
      selectAll.addEventListener("click", function () {
        checkboxes.forEach(function (cb) {
          var item = cb.closest("[data-pt-activity-item]");
          if (item && item.hidden) return; // respeita o filtro de busca
          cb.checked = true;
        });
        refresh();
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        checkboxes.forEach(function (cb) { cb.checked = false; });
        refresh();
      });
    }

    if (search) {
      search.addEventListener("input", function () {
        var term = (search.value || "").trim().toLowerCase();
        var anyVisible = false;
        items.forEach(function (item) {
          var name = item.dataset.nome || "";
          var match = !term || name.indexOf(term) >= 0;
          item.hidden = !match;
          if (match) anyVisible = true;
        });
        if (emptyFilter) emptyFilter.hidden = anyVisible;
      });
    }

    refresh();
  }

  /* ── Bootstrap ──────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    var identificacao = document.querySelector("[data-pt-form]");
    if (identificacao) {
      syncProgramaOutros(identificacao);
      syncDestinationCities(identificacao);
      syncEventDates(identificacao);
      initTextosPadrao(identificacao);
      initCoordenadores(identificacao);
    }

    var efetivoDiarias = document.querySelector("[data-pt-efetivo-diarias]");
    if (efetivoDiarias) {
      initEfetivoFormset(efetivoDiarias);
      initDiariasLiveCalc(efetivoDiarias);
    }

    var atividades = document.querySelector("[data-pt-atividades]");
    if (atividades) {
      initAtividades(atividades);
    }
  });
})();
