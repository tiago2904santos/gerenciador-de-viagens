(function () {
  "use strict";

  /* ── cv-search-picker: reset + reinit ──────────────────────── */

  function resetPicker(select) {
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

  function syncDestinationCities(form) {
    window.CV.locationRows.initManagedRows({ form: form });
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
    Array.prototype.slice.call(form.querySelectorAll("[data-location-row]")).forEach(function (row) {
      if (row.hidden) return;
      var stateSelect = row.querySelector("[data-location-state]");
      var citySelect = row.querySelector("[data-location-city]");
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

  function formatCargoNome(cargo, nome) {
    return [ptTitleCase(cargo), ptTitleCase(nome)].filter(Boolean).join(" ");
  }

  function termosGeneroCoordenador(genero) {
    var feminino = genero === "FEMININO";
    return {
      designado: feminino ? "designada" : "designado",
      artigo: feminino ? "a" : "o",
      coordenador_administrativo: feminino ? "Coordenadora Administrativa" : "Coordenador Administrativo",
      coordenador_operacional: feminino ? "Coordenadora Operacional do Evento" : "Coordenador Operacional do Evento",
    };
  }

  function preencherTemplateCoordenador(template, data, papel) {
    var termos = termosGeneroCoordenador(data.genero);
    var coordenadorKey = papel === "adm" ? "coordenador_administrativo" : "coordenador_operacional";
    return String(template || "")
      .replace(/\{cargo_nome\}/g, formatCargoNome(data.cargo, data.nome))
      .replace(/\{designado\}/g, termos.designado)
      .replace(/\{artigo\}/g, termos.artigo)
      .replace(/\{coordenador_administrativo\}/g, termos.coordenador_administrativo)
      .replace(/\{coordenador_operacional\}/g, termos[coordenadorKey]);
  }

  function getCoordenadorData(form, papel) {
    var panel = form.querySelector("[data-pt-coordenador-panel='" + papel + "']");
    if (!panel) return { nome: "", cargo: "", genero: "MASCULINO" };
    var servidorSelect = panel.querySelector("select[data-pt-coordenador-picker]");
    var generoSelect = panel.querySelector("[name='coordenador_" + papel + "_genero']");
    var option = selectedOption(servidorSelect);
    if (option) {
      // O texto da option é apenas o nome do servidor; data-main traz a linha
      // rica do dropdown (nome * RG * CPF * cargo) e NÃO deve virar o nome.
      return {
        nome: (option.textContent || "").trim(),
        cargo: (option.dataset.cargo || "").trim(),
        genero: (generoSelect && generoSelect.value) || "MASCULINO",
      };
    }
    var manualInput = panel.querySelector("[data-pt-coordenador-nome-manual]");
    var cargoSelect = panel.querySelector("[name='coordenador_" + papel + "_cargo_manual']");
    var pickerRoot = servidorSelect ? servidorSelect.nextElementSibling : null;
    var pickerInput = pickerRoot && pickerRoot.classList.contains("cv-search-picker")
      ? pickerRoot.querySelector(".cv-search-picker__input")
      : null;
    return {
      nome: ((manualInput && manualInput.value) || (pickerInput && pickerInput.value) || "").trim(),
      cargo: ((cargoSelect && cargoSelect.value) || "").trim(),
      genero: (generoSelect && generoSelect.value) || "MASCULINO",
    };
  }

  function computeCoordenacao(form, templates) {
    var paragrafos = [];
    var adm = getCoordenadorData(form, "adm");
    if (adm.nome) {
      paragrafos.push(preencherTemplateCoordenador(templates.coordenacao_adm, adm, "adm"));
    }
    var op = getCoordenadorData(form, "op");
    if (op.nome) {
      paragrafos.push(preencherTemplateCoordenador(templates.coordenacao_op, op, "op"));
    }
    return paragrafos.filter(Boolean).join("\n\n");
  }

  function isCoordenadorTextTarget(target) {
    if (!target) return false;
    if (target.matches && target.matches("[data-pt-coordenador-picker], [data-pt-coordenador-nome-manual], [data-pt-coordenador-modo]")) {
      return true;
    }
    return /^coordenador_(adm|op)_(cargo_manual|nome_manual|modo|genero)$/.test(target.name || "");
  }

  function initTextosPadrao(form) {
    var dataEl = document.getElementById("pt-textos-padrao-data");
    if (!dataEl) return;
    var templates = {};
    try { templates = JSON.parse(dataEl.textContent || "{}"); } catch (e) { templates = {}; }

    var programmatic = false;
    var fields = [
      { name: "contextualizacao", flag: "contextualizacao" },
      { name: "coordenacao", flag: "coordenacao" },
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
        var nextValue = field.name === "coordenacao"
          ? computeCoordenacao(form, templates)
          : template
            .replace(/\{municipio\}/g, municipio)
            .replace(/\{programa\}/g, programa);
        if (field.name !== "coordenacao" && !template) return;
        programmatic = true;
        field.textarea.value = nextValue;
        programmatic = false;
      });
    }

    form.addEventListener("change", function (event) {
      var target = event.target;
      if (!target) return;
      if (
        target.matches("[data-location-city], [data-location-state], [data-pt-programa-select]") ||
        target.name === "programa_outros" ||
        isCoordenadorTextTarget(target)
      ) {
        regenerate();
      }
      // When cargo_manual changes, also mark the companion fields dirty so the
      // autosave payload includes enough context to clear any stale servidor data.
      var cargoManualMatch = /^coordenador_(adm|op)_cargo_manual$/.exec(target.name || "");
      if (cargoManualMatch && window.AppAutosave) {
        var papel = cargoManualMatch[1];
        window.AppAutosave.markDirty(form, "coordenador_" + papel, 900);
        window.AppAutosave.markDirty(form, "coordenador_" + papel + "_nome_manual", 900);
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

  function refreshCustomSelect(select) {
    if (!select || !select.closest) return;
    var root = select.closest('[data-entity-picker-renderer="select"]');
    if (root && root._cvSelect && typeof root._cvSelect.refresh === "function") {
      root._cvSelect.refresh();
    }
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
      // Em modo silencioso (carga/edição) o setSelectValue não dispara "change",
      // então o cv-custom-select do cargo não atualiza o texto visível sozinho.
      refreshCustomSelect(cargoSelect);
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

  /* ── Etapa 2: linhas de efetivo (formset dinâmico) ─────────── */

  function initEfetivoFormset(scope) {
    var rowsContainer = scope.querySelector("[data-pt-efetivo-rows]");
    var template = scope.querySelector("template[data-pt-efetivo-template]");
    var addButton = scope.querySelector("[data-pt-efetivo-add]");
    var totalInput = scope.querySelector("input[name='efetivo-TOTAL_FORMS']");
    if (!rowsContainer || !template || !addButton || !totalInput) return;

    rowsContainer.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-pt-quantidade-delta]");
      if (!btn) return;
      var stepper = btn.closest(".pt-quantidade-stepper");
      if (!stepper) return;
      var input = stepper.querySelector("input");
      if (!input) return;
      var delta = parseInt(btn.getAttribute("data-pt-quantidade-delta") || "0", 10);
      var cur = parseInt(input.value || "1", 10) || 1;
      input.value = String(Math.max(1, cur + delta));
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    addButton.addEventListener("click", function () {
      var index = parseInt(totalInput.value || "0", 10);
      var html = template.innerHTML.replace(/__prefix__/g, String(index));
      var holder = document.createElement("div");
      holder.innerHTML = html.trim();
      var row = holder.firstElementChild;
      rowsContainer.appendChild(row);
      totalInput.value = String(index + 1);
      bindEfetivoInputs(scope, row);
      var picker = window.CV && window.CV.picker;
      if (picker && picker.initSelect) picker.initSelect(row);
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
      var ord = row.querySelector("[data-pt-efetivo-ord]");
      if (ord) ord.textContent = String(index + 1);
      var removeBtn = row.querySelector("[data-pt-efetivo-remove]");
      if (!removeBtn) return;
      removeBtn.hidden = visibleRows.length <= 1 && index === 0;
      row.classList.toggle("destination-row--single", visibleRows.length <= 1 && index === 0);
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
    window.CV.http.fetchJson(url, {
      method: "POST",
      body: payload,
    })
      .then(function (result) {
        var data = result.data || {};
        var errosEl = scope.querySelector("[data-pt-diarias-erros]");
        if (!result.ok || !data.ok) {
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

  function buildPresetsMap() {
    var dataEl = document.getElementById("pt-atividades-presets-data");
    var map = {};
    if (!dataEl) return map;
    var list = [];
    try { list = JSON.parse(dataEl.textContent || "[]"); } catch (e) { list = []; }
    list.forEach(function (item) {
      if (item && item.id != null) map[String(item.id)] = item;
    });
    return map;
  }

  function initAtividades(scope) {
    var catalog = buildCatalogMap();
    var presets = buildPresetsMap();
    var counter = scope.querySelector("[data-pt-activity-counter]");
    var checkboxes = Array.prototype.slice.call(scope.querySelectorAll("[data-pt-activity-checkbox]"));
    var selectAll = scope.querySelector("[data-pt-activity-select-all]");
    var clearBtn = scope.querySelector("[data-pt-activity-clear]");
    var search = scope.querySelector("[data-pt-activity-search]");
    var presetSelect = scope.querySelector("[data-pt-activity-preset]");
    var items = Array.prototype.slice.call(scope.querySelectorAll("[data-pt-activity-item]"));
    var emptyFilter = scope.querySelector("[data-pt-activity-empty]");

    var metasList = scope.querySelector("[data-pt-live-metas-list]");
    var metasEmpty = scope.querySelector("[data-pt-live-metas-empty]");
    var metasCount = scope.querySelector("[data-pt-live-metas-count]");
    var recursosList = scope.querySelector("[data-pt-live-recursos-list]");
    var recursosEmpty = scope.querySelector("[data-pt-live-recursos-empty]");
    var recursosCount = scope.querySelector("[data-pt-live-recursos-count]");

    function syncCardState(cb) {
      var card = cb.closest("[data-pt-activity-item]");
      if (card) card.classList.toggle("is-selected", cb.checked);
    }

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

    function applyPresetCodes(codigos) {
      var wanted = {};
      (codigos || []).forEach(function (codigo) { wanted[String(codigo)] = true; });
      checkboxes.forEach(function (cb) {
        cb.checked = Boolean(wanted[cb.value]);
        syncCardState(cb);
      });
      refresh();
      var form = scope.closest("form") || document.querySelector("form[data-autosave='true']");
      markSnapshot(form, "atividades", 600);
    }

    checkboxes.forEach(function (cb) {
      cb.addEventListener("change", function () {
        syncCardState(cb);
        refresh();
      });
    });

    if (selectAll) {
      selectAll.addEventListener("click", function () {
        checkboxes.forEach(function (cb) {
          var card = cb.closest("[data-pt-activity-item]");
          if (card && card.hidden) return;
          cb.checked = true;
          syncCardState(cb);
        });
        refresh();
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        checkboxes.forEach(function (cb) { cb.checked = false; syncCardState(cb); });
        refresh();
        if (presetSelect) {
          presetSelect.value = "";
          presetSelect.dispatchEvent(new Event("change", { bubbles: true }));
        }
      });
    }

    if (presetSelect) {
      var previousPresetId = presetSelect.value || "";
      var resettingPreset = false;
      presetSelect.addEventListener("change", async function () {
        if (resettingPreset) {
          resettingPreset = false;
          return;
        }
        var presetId = (presetSelect.value || "").trim();
        if (!presetId) {
          previousPresetId = "";
          return;
        }
        var preset = presets[presetId];
        if (!preset) return;
        var alreadyChecked = checkboxes.some(function (cb) { return cb.checked; });
        if (alreadyChecked) {
          presetSelect.disabled = true;
          var ok = await window.CV.feedback.confirm(
            "Aplicar o preset “" + (preset.nome || "") + "” vai substituir a seleção atual. Continuar?"
          );
          presetSelect.disabled = false;
          if (!ok) {
            resettingPreset = true;
            presetSelect.value = previousPresetId;
            presetSelect.dispatchEvent(new Event("change", { bubbles: true }));
            return;
          }
        }
        applyPresetCodes(preset.codigos || []);
        previousPresetId = presetId;
      });
    }

    if (search) {
      search.addEventListener("input", function () {
        var term = (search.value || "").trim().toLowerCase();
        var anyVisible = false;
        items.forEach(function (card) {
          var name = card.dataset.nome || "";
          var match = !term || name.indexOf(term) >= 0;
          card.hidden = !match;
          if (match) anyVisible = true;
        });
        if (emptyFilter) emptyFilter.hidden = anyVisible;
      });
    }

    refresh();
  }

  /* ── Autosave: provedor de snapshots por etapa ─────────────── */

  function collectEfetivoSnapshot(form) {
    var rows = Array.prototype.slice.call(form.querySelectorAll("[data-pt-efetivo-row]"));
    var out = [];
    rows.forEach(function (row, index) {
      if (row.hidden) return;
      var deleteInput = row.querySelector("input[name$='-DELETE']");
      if (deleteInput && deleteInput.checked) return;
      var idInput = row.querySelector("input[name$='-id']");
      var unidade = row.querySelector("select[name$='-unidade']");
      var cargo = row.querySelector("select[name$='-cargo']");
      var qtd = row.querySelector("input[name$='-quantidade']");
      out.push({
        idx: index,
        id: idInput && idInput.value ? idInput.value : "",
        unidade: unidade ? unidade.value : "",
        cargo: cargo ? cargo.value : "",
        quantidade: qtd ? qtd.value : "",
      });
    });
    return out;
  }

  function collectAtividadesSnapshot(form) {
    var checkboxes = Array.prototype.slice.call(form.querySelectorAll("[data-pt-activity-checkbox]"));
    var codigos = checkboxes.filter(function (cb) { return cb.checked; }).map(function (cb) { return cb.value; });
    return { codigos: codigos };
  }

  window.AppAutosaveSnapshots = window.AppAutosaveSnapshots || {};
  window.AppAutosaveSnapshots.plano_trabalho = function (form) {
    var step = form.dataset.autosaveStep || "";
    var snapshots = {};
    if (step === "efetivo_diarias") {
      snapshots.efetivo = collectEfetivoSnapshot(form);
    } else if (step === "atividades") {
      snapshots.atividades = collectAtividadesSnapshot(form);
    }
    return snapshots;
  };

  function findAutosaveForm(scope) {
    return scope.closest("form[data-autosave='true']");
  }

  function markSnapshot(form, name, delay) {
    if (!form || !window.AppAutosave || !window.AppAutosave.markSnapshotChanged) return;
    window.AppAutosave.markSnapshotChanged(form, name, delay);
  }

  function applyEfetivoIdsFromResponse(scope, snapshotResult) {
    if (!Array.isArray(snapshotResult)) return;
    var rows = Array.prototype.slice.call(scope.querySelectorAll("[data-pt-efetivo-row]"));
    snapshotResult.forEach(function (entry) {
      var idx = typeof entry.idx === "number" ? entry.idx : parseInt(entry.idx, 10);
      if (isNaN(idx) || !rows[idx]) return;
      var idInput = rows[idx].querySelector("input[name$='-id']");
      if (idInput && entry.id && !idInput.value) idInput.value = String(entry.id);
    });
  }

  function wireEfetivoAutosave(scope) {
    var form = findAutosaveForm(scope);
    if (!form) return;
    var rowsContainer = scope.querySelector("[data-pt-efetivo-rows]");
    if (!rowsContainer) return;

    function ping() { markSnapshot(form, "efetivo", 900); }

    rowsContainer.addEventListener("change", function (event) {
      var target = event.target;
      if (!target) return;
      if (target.matches && target.matches("select[name$='-unidade'], select[name$='-cargo'], input[name$='-quantidade'], input[name$='-DELETE']")) {
        ping();
      }
    });
    rowsContainer.addEventListener("input", function (event) {
      var target = event.target;
      if (!target || !target.matches) return;
      if (target.matches("input[name$='-quantidade']")) ping();
    });

    var addButton = scope.querySelector("[data-pt-efetivo-add]");
    if (addButton) addButton.addEventListener("click", function () { window.setTimeout(ping, 50); });

    form.addEventListener("autosave:success", function (event) {
      var data = event.detail || {};
      if (data && data.snapshots && data.snapshots.efetivo) {
        applyEfetivoIdsFromResponse(scope, data.snapshots.efetivo);
      }
    });
  }

  function wireAtividadesAutosave(scope) {
    var form = findAutosaveForm(scope);
    if (!form) return;
    function ping() { markSnapshot(form, "atividades", 600); }
    Array.prototype.slice.call(scope.querySelectorAll("[data-pt-activity-checkbox]")).forEach(function (cb) {
      cb.addEventListener("change", ping);
    });
    var selectAll = scope.querySelector("[data-pt-activity-select-all]");
    var clearBtn = scope.querySelector("[data-pt-activity-clear]");
    if (selectAll) selectAll.addEventListener("click", function () { window.setTimeout(ping, 50); });
    if (clearBtn) clearBtn.addEventListener("click", function () { window.setTimeout(ping, 50); });
  }

  /* ── Bootstrap ──────────────────────────────────────────────── */

  document.addEventListener("DOMContentLoaded", function () {
    var identificacao = document.querySelector("[data-pt-form]");
    if (identificacao) {
      syncProgramaOutros(identificacao);
      syncDestinationCities(identificacao);
      initTextosPadrao(identificacao);
      initCoordenadores(identificacao);
    }

    var efetivoDiarias = document.querySelector("[data-pt-efetivo-diarias]");
    if (efetivoDiarias) {
      initEfetivoFormset(efetivoDiarias);
      initDiariasLiveCalc(efetivoDiarias);
      wireEfetivoAutosave(efetivoDiarias);
    }

    var atividades = document.querySelector("[data-pt-atividades]");
    if (atividades) {
      initAtividades(atividades);
      wireAtividadesAutosave(atividades);
    }
  });
})();
