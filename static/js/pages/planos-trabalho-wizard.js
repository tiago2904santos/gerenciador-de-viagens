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

  /* ── Coordenadores: toggle SERVIDOR ↔ MANUAL (clone do motorista) ── */

  function initCoordenadorToggle(form, papel) {
    var hidden = form.querySelector("input[name='coordenador_" + papel + "_modo']");
    var buttons = Array.prototype.slice.call(
      form.querySelectorAll("[data-pt-coordenador-btn='" + papel + "']"),
    );
    var servidorPanel = form.querySelector("[data-pt-coordenador-servidor='" + papel + "']");
    var manualPanel = form.querySelector("[data-pt-coordenador-manual='" + papel + "']");
    if (!hidden || !buttons.length) return;

    function applyMode(mode) {
      hidden.value = mode;
      hidden.dispatchEvent(new Event("change", { bubbles: true }));
      buttons.forEach(function (btn) {
        btn.setAttribute("aria-pressed", btn.dataset.value === mode ? "true" : "false");
      });
      if (servidorPanel) servidorPanel.hidden = mode === "MANUAL";
      if (manualPanel) manualPanel.hidden = mode !== "MANUAL";
    }

    buttons.forEach(function (btn) {
      btn.addEventListener("click", function () {
        applyMode(btn.dataset.value);
      });
    });
    applyMode(hidden.value || "SERVIDOR");
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
      var removeBtn = row.querySelector("[data-pt-efetivo-remove]");
      if (removeBtn) {
        removeBtn.hidden = false;
        removeBtn.addEventListener("click", function () {
          row.remove();
          notifyEfetivoChanged(scope);
        });
      }
      bindEfetivoInputs(scope, row);
    });

    Array.prototype.slice.call(rowsContainer.querySelectorAll("[data-pt-efetivo-row]")).forEach(function (row) {
      bindEfetivoInputs(scope, row);
    });
  }

  function bindEfetivoInputs(scope, row) {
    Array.prototype.slice.call(row.querySelectorAll("input, select")).forEach(function (input) {
      input.addEventListener("change", function () { notifyEfetivoChanged(scope); });
      input.addEventListener("input", function () { notifyEfetivoChanged(scope); });
    });
  }

  function totalEfetivo(scope) {
    var total = 0;
    Array.prototype.slice.call(scope.querySelectorAll("[data-pt-efetivo-row]")).forEach(function (row) {
      var deleteInput = row.querySelector("input[name$='-DELETE']");
      if (deleteInput && deleteInput.checked) return;
      var cargo = row.querySelector("select[name$='-cargo']");
      var qtd = row.querySelector("input[name$='-quantidade']");
      if (!cargo || !cargo.value) return;
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

  /* ── Bootstrap ──────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    var identificacao = document.querySelector("[data-pt-form]");
    if (identificacao) {
      syncProgramaOutros(identificacao);
      syncDestinationCities(identificacao);
      syncEventDates(identificacao);
      initCoordenadorToggle(identificacao, "adm");
      initCoordenadorToggle(identificacao, "op");
    }

    var efetivoDiarias = document.querySelector("[data-pt-efetivo-diarias]");
    if (efetivoDiarias) {
      initEfetivoFormset(efetivoDiarias);
      initDiariasLiveCalc(efetivoDiarias);
    }
  });
})();
