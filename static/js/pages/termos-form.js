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
    if (window.CvSearchPicker && window.CvSearchPicker.init) {
      window.CvSearchPicker.init(scope || document);
    }
  }

  function syncOficioSummary(form, summaries) {
    var select = form.querySelector("select[name='oficio']");
    var root = form.querySelector("[data-termo-oficio-summary]");
    var search = form.querySelector("#id_oficio_busca");
    var list = form.querySelector("#termo-oficio-lista");
    if (!select || !root || !search || !list) return;

    var empty = root.querySelector(".termo-oficio-summary__empty");
    var grid = root.querySelector(".termo-oficio-summary__grid");
    var destino = root.querySelector("[data-termo-oficio-destino]");
    var periodo = root.querySelector("[data-termo-oficio-periodo]");
    var servidores = root.querySelector("[data-termo-oficio-servidores]");
    var viatura = root.querySelector("[data-termo-oficio-viatura]");
    var summaryText = form.querySelector("#termo-selector-resumo");

    var items = Object.keys(summaries).map(function (key) {
      return summaries[key];
    });

    function selectedSummary() {
      return summaries[String(select.value || "")] || null;
    }

    function renderSummary() {
      var summary = selectedSummary();
      var hasSummary = !!summary;
      if (empty) empty.hidden = hasSummary;
      if (grid) grid.hidden = !hasSummary;
      if (!hasSummary) {
        if (summaryText) {
          summaryText.textContent = "Nenhum oficio vinculado.";
        }
        if (destino) destino.textContent = "-";
        if (periodo) periodo.textContent = "-";
        if (servidores) servidores.textContent = "-";
        if (viatura) viatura.textContent = "-";
        return;
      }
      if (summaryText) {
        summaryText.textContent = [summary.label, summary.destino, summary.protocolo].filter(Boolean).join(" - ");
      }
      if (destino) destino.textContent = summary.destino || "-";
      if (periodo) periodo.textContent = summary.periodo || "-";
      if (servidores) servidores.textContent = String(summary.servidores || 0);
      if (viatura) viatura.textContent = summary.viatura || "-";
    }

    function renderList(filterText) {
      var term = normalize(filterText);
      var filtered = items.filter(function (summary) {
        var text = normalize(summary.search_text || [summary.label, summary.numero, summary.protocolo, summary.destino, summary.periodo].join(" "));
        return !term || text.indexOf(term) !== -1;
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
        var title = document.createElement("span");
        title.className = "route-title";
        title.textContent = summary.label || ("Oficio " + String(summary.id));
        var destinos = document.createElement("span");
        destinos.className = "route-destinos";
        destinos.textContent = summary.destino || "Destino nao informado";
        var periodo = document.createElement("span");
        periodo.className = "route-periodo";
        periodo.textContent = "Protocolo: " + (summary.protocolo || "-") + (summary.periodo ? " | Periodo: " + summary.periodo : "");
        button.appendChild(title);
        button.appendChild(destinos);
        button.appendChild(periodo);
        button.addEventListener("click", function () {
          select.value = String(summary.id);
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
    });
    search.addEventListener("input", function () {
      renderList(search.value);
    });

    renderList(search.value);
    renderSummary();
  }

  function updateCitySelect(form, citySelect, cities, selectedCityId) {
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

    syncOficioSummary(form, readSummaries());
    syncDestinationCities(form);
    syncEventDates(form);
  });
})();
