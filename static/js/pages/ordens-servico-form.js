(function () {
  "use strict";

  var OS_ROLE_ASSIGNMENTS = {};
  var OS_ROLE_LABELS = {
    CONDUCAO: "Condução",
    TECNICO: "Técnico",
    APOIO: "Apoio",
    COORDENACAO: "Coordenação",
    PREPARACAO: "Preparação"
  };
  var OS_ROLE_SETS = {
    CAMINHAO: ["CONDUCAO", "TECNICO", "APOIO"],
    MICROONIBUS: ["CONDUCAO", "TECNICO", "APOIO"],
    CERIMONIAL_ANTECIPADO: ["COORDENACAO", "APOIO", "PREPARACAO"]
  };
  var OS_ROLE_PANEL_COPY = {
    CAMINHAO: {
      title: "Função no caminhão",
      aria: "Função dos servidores no caminhão"
    },
    MICROONIBUS: {
      title: "Função no micro-ônibus",
      aria: "Função dos servidores no micro-ônibus"
    },
    CERIMONIAL_ANTECIPADO: {
      title: "Função no cerimonial",
      aria: "Função dos servidores no cerimonial"
    }
  };

  var ROUTE_AVATAR_ICON =
    '<svg class="cv-icon related-route-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none">' +
      '<circle cx="6" cy="19" r="2.5" fill="currentColor"></circle>' +
      '<circle cx="18" cy="5" r="2.5" fill="currentColor"></circle>' +
      '<path d="M8.2 18.2h6.1a3.3 3.3 0 0 0 0-6.6H9.7a3.3 3.3 0 0 1 0-6.6h6.1" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"></path>' +
    '</svg>';

  /* ── Utilitários ────────────────────────────────────────────── */

  function readSummaries() {
    return window.CV.documentSource.read("os-oficios-summary");
  }

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

  function salvageServidorRolePanel(form) {
    var panel = form.querySelector("[data-os-servidor-role-panel]");
    if (!panel || !panel.closest(".cv-search-picker")) return;
    var host = form.querySelector("#os-card-servidores .cv-form-block__body") || form;
    host.appendChild(panel);
  }

  function resetPicker(select) {
    if (select && select.name === "servidores") {
      var form = select.closest("[data-os-form]");
      if (form) salvageServidorRolePanel(form);
    }
    if (window.CV && window.CV.locationRows && typeof window.CV.locationRows.resetSearchPicker === "function") {
      window.CV.locationRows.resetSearchPicker(select);
      return;
    }
    if (!select || select.dataset.entityPickerReady !== "true") return;
    delete select.dataset.entityPickerReady;
    var next = select.nextElementSibling;
    if (next && next.classList && next.classList.contains("cv-search-picker")) {
      next.parentNode.removeChild(next);
    }
  }

  function initPickers(scope) {
    if (window.CV && window.CV.locationRows && typeof window.CV.locationRows.initSearchPickers === "function") {
      window.CV.locationRows.initSearchPickers(scope || document);
      return;
    }
    if (window.CV && window.CV.picker && window.CV.picker.initSearch) {
      window.CV.picker.initSearch(scope || document);
    }
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
      managedFlag: "osDestinosManaged",
      afterCitiesLoaded: function () { updateSubmitButtonLabel(form); },
      onChange: function () { updateSubmitButtonLabel(form); },
    });
  }

  function focusDestinationPicker(form) {
    var destinationSection = form.querySelector("#os-evento-destinos");
    if (!destinationSection) return;
    window.CV.locationRows.focusFirstEmptyPicker(destinationSection);
  }

  function syncAddDestinationButton(form) {
    if (form.dataset.osDestinosManaged === "true") return;
    if (!form.querySelector("[data-location-add]") || form.dataset.osAddDestinoBound === "true") return;
    form.dataset.osAddDestinoBound = "true";

    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-location-add]");
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
    if (select.name === "servidores") {
      syncServidorRoleUi(form);
    }
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

  function supportsServidorRoles(form) {
    return Object.prototype.hasOwnProperty.call(OS_ROLE_SETS, selectedOsModel(form));
  }

  function roleModesForModel(form) {
    return OS_ROLE_SETS[selectedOsModel(form)] || [];
  }

  function defaultServidorRole(form) {
    return roleModesForModel(form)[0] || "CONDUCAO";
  }

  function pruneInvalidServidorRoles(form) {
    var allowed = new Set(roleModesForModel(form));
    Object.keys(OS_ROLE_ASSIGNMENTS).forEach(function (id) {
      if (!allowed.has(OS_ROLE_ASSIGNMENTS[id])) {
        delete OS_ROLE_ASSIGNMENTS[id];
      }
    });
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
    var modes = roleModesForModel(form);
    var active = form.querySelector("[data-os-role-mode][aria-pressed='true']");
    if (active && modes.indexOf(active.dataset.osRoleMode) !== -1) {
      return active.dataset.osRoleMode;
    }
    return defaultServidorRole(form);
  }

  function syncServidorRoleButtons(form) {
    var toggle = form.querySelector(".os-servidor-role-panel__toggle");
    if (!toggle) return;
    var modes = roleModesForModel(form);
    var activeRole = activeServidorRole(form);

    if (!modes.length) {
      toggle.replaceChildren();
      return;
    }

    var currentModes = Array.from(toggle.querySelectorAll("[data-os-role-mode]")).map(function (button) {
      return button.dataset.osRoleMode;
    });
    var needsRebuild = currentModes.length !== modes.length
      || modes.some(function (mode, index) { return currentModes[index] !== mode; });

    if (needsRebuild) {
      toggle.replaceChildren();
      modes.forEach(function (mode, index) {
        var button = document.createElement("button");
        button.type = "button";
        button.className = "cv-segment-toggle__btn";
        button.dataset.osRoleMode = mode;
        button.setAttribute("aria-pressed", mode === activeRole ? "true" : "false");
        button.textContent = OS_ROLE_LABELS[mode] || mode;
        toggle.appendChild(button);
      });
    }

    form.querySelectorAll("[data-os-role-mode]").forEach(function (button) {
      var active = button.dataset.osRoleMode === activeRole;
      var wasActive = button.getAttribute("aria-pressed") === "true";
      button.setAttribute("aria-pressed", active ? "true" : "false");

      /* Dispara a animação de entrada apenas na troca (não no carregamento) */
      if (active && !wasActive) {
        button.classList.remove("cv-segment-toggle__btn--pop");
        void button.offsetWidth;
        button.classList.add("cv-segment-toggle__btn--pop");
      }
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
    if (!supportsServidorRoles(form)) return;

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

  function renderServidorRoleCard(card, role, active, highlighted) {
    card.classList.toggle("os-servidor-role-card", active);
    card.classList.toggle("os-servidor-role-card--assigned", !!role && active);
    card.classList.toggle(
      "cv-search-picker__selected-card--driver",
      highlighted,
    );
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
    badge.classList.toggle("cv-search-picker__driver-chip", highlighted);
    badge.textContent = label;
  }

  function servidoresPicker(form) {
    var select = form.querySelector("select[name='servidores']");
    if (!select) return null;
    var next = select.nextElementSibling;
    return next && next.classList && next.classList.contains("cv-search-picker") ? next : null;
  }

  function mountServidorRolePanel(form, rolesEnabled) {
    var panel = form.querySelector("[data-os-servidor-role-panel]");
    var picker = servidoresPicker(form);
    if (!panel || !picker) return;
    var model = selectedOsModel(form);
    var copy = OS_ROLE_PANEL_COPY[model] || OS_ROLE_PANEL_COPY.CAMINHAO;
    var title = panel.querySelector(".os-servidor-role-panel__title");
    var toggle = panel.querySelector(".os-servidor-role-panel__toggle");
    if (title) {
      title.textContent = copy.title;
    }
    if (toggle) {
      toggle.setAttribute("aria-label", copy.aria);
    }
    var field = picker.querySelector(".cv-search-picker__field")
      || panel.querySelector(".cv-search-picker__field");
    var selected = picker.querySelector(".cv-search-picker__selected-panel");
    var fieldHost = panel.querySelector("[data-os-servidor-picker-field-host]");
    if (!field || !selected || !fieldHost) return;

    var activeEl = document.activeElement;
    var keepPickerFocus = !!(activeEl && (
      activeEl.classList.contains("cv-search-picker__input")
      || activeEl.closest(".cv-search-picker__control")
    ));

    if (rolesEnabled) {
      var alreadyMounted = panel.parentElement === picker
        && panel.nextElementSibling === selected
        && field.parentElement === fieldHost
        && !panel.hidden;
      if (alreadyMounted) return;

      if (field.parentElement !== fieldHost) {
        fieldHost.replaceChildren(field);
      }
      if (panel.parentElement !== picker || panel.nextElementSibling !== selected) {
        picker.insertBefore(panel, selected);
      }
      panel.hidden = false;
    } else {
      if (field.parentElement !== picker || field.nextElementSibling !== selected) {
        picker.insertBefore(field, selected);
      }
      if (panel.parentElement === picker) {
        var panelHost = form.querySelector("#os-card-servidores .cv-form-block__body") || form;
        panelHost.appendChild(panel);
      }
      panel.hidden = true;
    }

    if (keepPickerFocus) {
      var input = picker.querySelector(".cv-search-picker__input")
        || panel.querySelector(".cv-search-picker__input");
      if (input) {
        window.setTimeout(function () {
          input.focus({ preventScroll: true });
        }, 0);
      }
    }
  }

  function syncServidorRoleUi(form) {
    var picker = servidoresPicker(form);
    var rolesEnabled = supportsServidorRoles(form);
    mountServidorRolePanel(form, rolesEnabled);
    pruneServidorRoles(form);
    pruneInvalidServidorRoles(form);
    syncServidorRoleButtons(form);
    syncServidorRoleInputs(form);

    if (!picker) return;
    var activeRole = activeServidorRole(form);
    picker.querySelectorAll(".cv-search-picker__selected-card[data-value]").forEach(function (card) {
      var servidorId = String(card.dataset.value || "");
      var role = OS_ROLE_ASSIGNMENTS[servidorId];
      renderServidorRoleCard(card, role, rolesEnabled, rolesEnabled && role === activeRole);
    });
  }

  function initServidorRolePicker(form) {
    OS_ROLE_ASSIGNMENTS = readRoleAssignments();
    mountServidorRolePanel(form, supportsServidorRoles(form));
    form.addEventListener("click", function (event) {
      if (!supportsServidorRoles(form)) return;
      if (event.target.closest("[data-os-role-mode]")) return;
      if (event.target.closest(".cv-search-picker__remove")) return;

      var card = event.target.closest(".cv-search-picker__selected-card[data-value]");
      if (!card || !form.contains(card)) return;
      var picker = servidoresPicker(form);
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
      var wasActive = button.getAttribute("aria-pressed") === "true";
      form.querySelectorAll("[data-os-role-mode]").forEach(function (candidate) {
        candidate.setAttribute("aria-pressed", candidate === button ? "true" : "false");
      });
      if (!wasActive) {
        button.classList.remove("cv-segment-toggle__btn--pop");
        void button.offsetWidth;
        button.classList.add("cv-segment-toggle__btn--pop");
      }
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

  function selectedOficioIds(select) {
    if (!select) return [];
    return Array.from(select.options)
      .filter(function (o) { return o.selected && o.value; })
      .map(function (o) { return String(o.value); });
  }

  function setOficioSelected(select, id, selected) {
    if (!select) return;
    var target = String(id);
    Array.from(select.options).forEach(function (opt) {
      if (String(opt.value) === target) {
        opt.selected = !!selected;
      }
    });
  }

  function onOficiosChange(form, summaries) {
    var oficiosSelect = form.querySelector("select[name='oficios']");
    if (!oficiosSelect) return;

    var documents = window.CV.documentSource.selected(oficiosSelect, summaries);
    if (!documents.length) return;

    window.CV.documentSource.apply(form, documents, [
      {
        type: "date-range",
        startName: "data_evento_inicio",
        endName: "data_evento_fim",
        startPath: "data_inicio",
        endPath: "data_fim",
        startStrategy: "min",
        endStrategy: "max",
        picker: "#os-evento-date-picker",
      },
      {
        type: "multi",
        name: "servidores",
        path: "servidor_ids",
        strategy: "union",
        after: function () { syncServidorRoleUi(form); },
      },
      { type: "value", name: "motivo", path: "motivo", preserve: true, events: true },
      {
        type: "location",
        stateName: "destino_estado",
        cityName: "destino_cidade",
        statePath: "estado_id",
        cityPath: "cidade_id",
      },
    ]).then(function () {
      updateSubmitButtonLabel(form);
    });
  }

  function syncOficioPicker(form, summaries) {
    var select = form.querySelector("select[name='oficios']");
    var search = form.querySelector("#id_os_oficio_busca");
    var list = form.querySelector("#os-oficio-lista");
    if (!select || !search || !list) return;

    var items = Object.keys(summaries).map(function (key) {
      return summaries[key];
    });
    items.sort(function (a, b) {
      return (a.order || 0) - (b.order || 0);
    });

    function renderList(filterText) {
      var emptyEl = form.querySelector("#os-oficio-lista-empty");
      var term = window.CV.util.normalize(filterText);
      var tokens = term.split(/\s+/).filter(Boolean);
      var selected = new Set(selectedOficioIds(select));
      var filtered = items.filter(function (summary) {
        var text = window.CV.util.normalize(
          summary.search_text ||
          [summary.label, summary.numero, summary.protocolo, summary.destino, summary.periodo].join(" ")
        );
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
        var active = selected.has(String(summary.id));
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
          setOficioSelected(select, summary.id, !active);
          select.dispatchEvent(new Event("change", { bubbles: true }));
        });
        list.appendChild(button);
      });
    }

    form._osRenderOficioList = renderList;

    if (form.dataset.osOficioPickerBound === "true") {
      renderList(search.value);
      return;
    }
    form.dataset.osOficioPickerBound = "true";

    select.addEventListener("change", function () {
      renderList(search.value);
      onOficiosChange(form, summaries);
    });
    search.addEventListener("input", function () {
      renderList(search.value);
    });

    renderList(search.value);
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

    if (model === "CAMINHAO" || model === "MICROONIBUS" || model === "CERIMONIAL_ANTECIPADO") {
      temEquipe = temServidores;
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

    var debouncedUpdate = window.CV.util.debounce(function () {
      updateSubmitButtonLabel(form);
    }, 150);
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

    var addButton = form.querySelector("[data-location-add]");

    function rowsCount() {
      return form.querySelectorAll("[data-location-row]").length;
    }

    var rowsNeeded = indexes[indexes.length - 1] + 1;
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
      if (typeof form._osRenderOficioList === "function") {
        var search = form.querySelector("#id_os_oficio_busca");
        form._osRenderOficioList(search ? search.value : "");
      }
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
    syncOficioPicker(form, summaries);
    initServidorRolePicker(form);
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
