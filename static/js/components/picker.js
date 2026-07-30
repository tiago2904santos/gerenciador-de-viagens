(function () {
  "use strict";

  const SELECTOR = "select[data-entity-picker]";
  const renderers = [];

  /* ── Utilitários ─────────────────────────────────────────────── */

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function dispatchChange(select) {
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  const UNIDADE_VALUE_PREFIX = "__unidade__";

  function readOption(option) {
    const kind = option.dataset.optionKind || "servidor";
    const memberIds = (option.dataset.memberIds || "")
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    return {
      cargo:     option.dataset.cargo    || "",
      cpf:       option.dataset.cpf      || "",
      disabled:  option.disabled,
      kind,
      label:     (option.textContent || "").trim(),
      main:      option.dataset.main     || (option.textContent || "").trim(),
      memberIds,
      meta:      option.dataset.meta     || option.dataset.unidade || "",
      rascunho:  option.dataset.rascunho === "true",
      rg:        option.dataset.rg       || "",
      search:    option.dataset.search   || option.textContent    || "",
      selected:  option.selected,
      unidade:   option.dataset.unidade  || "",
      unidadeId: option.dataset.unidadeId || "",
      value:     option.value,
    };
  }

  function isUnidadeValue(value) {
    return (value || "").startsWith(UNIDADE_VALUE_PREFIX);
  }

  function unidadePkFromValue(value) {
    return (value || "").replace(UNIDADE_VALUE_PREFIX, "");
  }

  function maskDocument(value, kind) {
    const digits = (value || "").replace(/\D/g, "");
    if (kind === "cpf" && digits.length >= 11) {
      return `${digits.slice(0, 3)}.***.***-${digits.slice(-2)}`;
    }
    if (kind === "rg" && digits.length >= 5) {
      return `${digits.slice(0, 2)}.***.***-${digits.slice(-1)}`;
    }
    return value || "";
  }

  function initialsFromLabel(label) {
    const parts = (label || "").trim().split(/\s+/).filter(Boolean);
    return [parts[0], parts.length > 1 ? parts[parts.length - 1] : ""]
      .filter(Boolean)
      .map((part) => part.charAt(0))
      .join("")
      .slice(0, 2)
      .toUpperCase() || "•";
  }

  function uniqueTextParts(values) {
    const seen = new Set();
    return values
      .map((value) => (value || "").trim())
      .filter((value) => {
        const key = window.CV.util.normalize(value);
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }

  /* ── Inicialização do picker ──────────────────────────────────── */

  function initPicker(select) {
    if (!select || select.dataset.entityPickerReady === "true") return;
    select.dataset.entityPickerReady = "true";

    /* Configuração via data-* */
    const mode         = select.dataset.entityPickerMode  || "multi";   /* single | multi */
    const variant      = select.dataset.pickerVariant     || "compact"; /* compact | detailed */
    const presentation = select.dataset.pickerPresentation || "default";
    const placeholder  = select.dataset.placeholder       || "Digite para buscar";
    const emptyMsg     = select.dataset.emptyMessage      || "Nenhum resultado encontrado.";
    const emptyPanelMsg = select.dataset.emptySelected    || "Nenhum item selecionado.";
    const panelTitle   = select.dataset.panelTitle        || "SELECIONADOS";
    const termosName   = select.dataset.cvTermosName      || "";
    const openAllOnFocus = select.dataset.pickerOpenAll === "true";
    const showTermCtrl   = select.dataset.pickerTermControl   === "true" || !!termosName;
    const showDriverCtrl = select.dataset.pickerDriverControl === "true";
    const allowFreeText  = select.dataset.pickerAllowFreeText === "true";
    const freeTextMsg    = select.dataset.pickerFreeTextMessage || "Pressione Enter para confirmar este nome.";
    const forceUppercase = select.dataset.pickerUppercase === "true";
    const isError        = select.dataset.pickerError         === "true";
    const listboxId    = `${select.id || select.name || "cv-picker"}-results`;
    const initialValue = (select.dataset.pickerInitialValue || "").trim();

    if (initialValue && !select.value) {
      select.value = initialValue;
    }

    /* Estado */
    const options = Array.from(select.options).map(readOption).filter((o) => o.value !== "");
    let query       = "";
    let activeIndex = -1;
    let isOpen      = false;
    let selectedForTerm = new Set();
    let driverValue = select.dataset.pickerDriverValue || "";

    /* Select de termos (hidden, gerenciado pelo componente).
       Busca dentro do form mais próximo; fora de form, usa o document. */
    let termSelect = null;
    if (termosName) {
      const scope = select.closest("form") || document;
      termSelect = scope.querySelector(`select[name="${CSS.escape(termosName)}"]`);
    }
    if (termSelect) {
      Array.from(termSelect.selectedOptions).forEach((o) => {
        if (o.value) selectedForTerm.add(o.value);
      });
    }

    /* ── Construção do DOM ──────────────────────────────────────── */

    const root = el("div", `cv-search-picker cv-search-picker--${mode} cv-search-picker--${variant}`);
    if (presentation !== "default") root.classList.add(`cv-search-picker--${presentation}`);
    if (presentation === "people") root.classList.add("cv-search-picker--roster");
    if (select.disabled)   root.classList.add("cv-search-picker--disabled");
    if (isError)           root.classList.add("cv-search-picker--error");

    const fieldLabel = select.dataset.pickerLabel || "";
    const fieldHint  = select.dataset.pickerHint  || "";

    /* Área de busca */
    const field      = el("div",    "cv-search-picker__field");
    const labelEl    = fieldLabel ? el("div", "cv-search-picker__label", fieldLabel) : null;
    const hintEl     = fieldHint ? el("div", "cv-search-picker__hint", fieldHint) : null;
    const control    = el("div",    "cv-search-picker__control");
    const icon       = el("span",   "cv-search-picker__icon", "");
    const input      = el("input",  "cv-search-picker__input");
    const clearBtn   = el("button", "cv-search-picker__clear", "x");
    const dropdown   = el("div",    "cv-search-picker__dropdown");
    const list       = el("div",    "cv-search-picker__list");
    const emptyEl    = el("div",    "cv-search-picker__empty", emptyMsg);

    input.type         = "search";
    input.placeholder  = placeholder;
    input.autocomplete = "off";
    input.disabled     = select.disabled;
    input.setAttribute("role", "combobox");
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-controls", listboxId);
    input.setAttribute("aria-autocomplete", "list");

    clearBtn.type = "button";
    clearBtn.setAttribute("aria-label", "Limpar busca");
    icon.setAttribute("aria-hidden", "true");

    list.id = listboxId;
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-multiselectable", mode === "multi" ? "true" : "false");
    dropdown.hidden = true;

    if (labelEl) field.appendChild(labelEl);
    if (hintEl && presentation !== "people" && presentation !== "vehicle") field.appendChild(hintEl);
    dropdown.appendChild(list);
    dropdown.appendChild(emptyEl);
    control.appendChild(icon);
    control.appendChild(input);
    control.appendChild(clearBtn);
    field.appendChild(control);
    field.appendChild(dropdown);
    root.appendChild(field);

    /* Painel de selecionados — multi sempre; single só quando detailed */
    const showPanel = mode === "multi" || variant === "detailed";
    let panel = null, grid = null, counter = null, panelEmpty = null, panelTitleEl = null;
    if (showPanel) {
      panel      = el("section", "cv-search-picker__selected-panel");
      grid       = el("div",  "cv-search-picker__selected-list");
      panelEmpty = el("p",    "cv-search-picker__selected-empty", emptyPanelMsg);

      if (presentation !== "people" && presentation !== "vehicle") {
        const panelHeader = el("div", "cv-search-picker__selected-header");
        panelTitleEl = el("h4", "cv-search-picker__selected-title", panelTitle);
        panelHeader.appendChild(panelTitleEl);
        if (mode === "multi") {
          counter = el("span", "cv-search-picker__selected-count", "0");
          panelHeader.appendChild(counter);
        }
        panel.appendChild(panelHeader);
      }
      panel.appendChild(grid);
      panel.appendChild(panelEmpty);
      root.appendChild(panel);
    }
    select.insertAdjacentElement("afterend", root);

    /* Campo com botão de gerenciar (field.html): o botão nasce como irmão
       do <select> dentro do wrapper .cv-field-with-action--search-picker.
       Move para dentro do controle de busca para alinhar com "Limpar
       busca" em vez de sobrepor o rótulo/dica renderizados acima. */
    const manageBtn = select.parentElement
      ? select.parentElement.querySelector(":scope > .cv-icon-btn--field-manage")
      : null;
    if (manageBtn) control.appendChild(manageBtn);

    const floatingMenu =
      window.CvFloatingDropdown && window.CvFloatingDropdown.attach
        ? window.CvFloatingDropdown.attach(dropdown, control)
        : null;
    if (floatingMenu) root.classList.add("cv-search-picker--menu-portal");

    /* ── Helpers de estado ──────────────────────────────────────── */

    function selectedItems() {
      return options.filter((o) => o.selected && o.kind !== "unidade");
    }

    function servidorOptions() {
      return options.filter((o) => o.kind !== "unidade");
    }

    function unidadeFullySelected(item) {
      if (!item.memberIds.length) return false;
      const selected = new Set(selectedItems().map((o) => o.value));
      return item.memberIds.every((id) => selected.has(id));
    }

    function filteredItems() {
      const term = window.CV.util.normalize(query);
      if (!term && openAllOnFocus && isOpen) {
        return options.filter((o) => !o.disabled);
      }
      if (!term) return [];
      if (mode === "single") {
        return options.filter((o) => window.CV.util.normalize(o.search).includes(term));
      }
      return options.filter((o) => {
        if (o.kind === "unidade") {
          return !unidadeFullySelected(o) && window.CV.util.normalize(o.search).includes(term);
        }
        return !o.selected && window.CV.util.normalize(o.search).includes(term);
      });
    }

    function syncSelect(dispatch) {
      const sel = new Set(selectedItems().map((o) => o.value));
      Array.from(select.options).forEach((o) => {
        if (isUnidadeValue(o.value)) {
          o.selected = false;
          return;
        }
        o.selected = sel.has(o.value);
      });
      if (dispatch) dispatchChange(select);
    }

    function syncTermSelect() {
      if (!termSelect) return;
      Array.from(termSelect.options).forEach((o) => {
        o.selected = selectedForTerm.has(o.value);
      });
      dispatchChange(termSelect);
    }

    function setHasQuery(val) {
      root.classList.toggle("cv-search-picker--has-query", val);
    }

    function setOpen(next) {
      const shouldOpen = next && (!!query || openAllOnFocus) && !select.disabled;
      if (shouldOpen && !isOpen && floatingMenu) floatingMenu.open();
      if (!shouldOpen && isOpen && floatingMenu) floatingMenu.close();
      isOpen = shouldOpen;
      dropdown.hidden = !isOpen;
      input.setAttribute("aria-expanded", isOpen ? "true" : "false");
      root.classList.toggle("cv-search-picker--open", isOpen);
      if (isOpen && floatingMenu) floatingMenu.reposition();
      renderResults();
    }

    function normalizeInputValue() {
      if (!forceUppercase || !input.value) return;
      const upperValue = input.value.toLocaleUpperCase("pt-BR");
      if (upperValue === input.value) return;
      const start = input.selectionStart;
      const end = input.selectionEnd;
      input.value = upperValue;
      try {
        input.setSelectionRange(start, end);
      } catch (e) {
        /* Alguns tipos/ambientes nao permitem restaurar selecao. */
      }
    }

    function commitFreeText() {
      if (!allowFreeText) return false;
      const value = (input.value || "").trim();
      if (!value) return false;
      input.value = value;
      query = value;
      select.dispatchEvent(new CustomEvent("cv-search-picker:free-text-commit", {
        bubbles: true,
        detail: { value },
      }));
      setOpen(false);
      return true;
    }

    /* ── Seleção / Remoção ──────────────────────────────────────── */

    function selectServidorValues(ids) {
      const idSet = new Set(ids.map(String));
      servidorOptions().forEach((o) => {
        if (idSet.has(String(o.value))) {
          o.selected = true;
          if (showTermCtrl) selectedForTerm.add(o.value);
        }
      });
    }

    function selectItem(value) {
      const item = options.find((o) => o.value === value);
      if (!item || item.disabled) return;

      if (mode === "single") {
        /* Deseleciona tudo e seleciona só o item escolhido */
        options.forEach((o) => { o.selected = false; });
        item.selected = true;
        query         = "";
        if (showPanel) {
          input.value = "";
          setHasQuery(false);
        } else {
          input.value = item.label;
          setHasQuery(true); /* mantém o clear visível com o valor preenchido */
        }
      } else if (item.kind === "unidade") {
        selectServidorValues(item.memberIds);
        query       = "";
        activeIndex = -1;
        input.value = "";
        setHasQuery(false);
      } else {
        if (item.selected) return;
        item.selected = true;
        if (showTermCtrl) selectedForTerm.add(value);
        query       = "";
        activeIndex = -1;
        input.value = "";
        setHasQuery(false);
      }

      activeIndex = -1;
      syncSelect(true);
      syncTermSelect();
      render();
      setOpen(false);
      input.focus();
    }

    function removeItem(value) {
      const item = options.find((o) => o.value === value);
      if (!item || item.disabled || !item.selected) return;
      item.selected = false;
      selectedForTerm.delete(value);
      if (driverValue === value) setDriverValue("");
      syncSelect(true);
      syncTermSelect();
      render();
      if (query) setOpen(true);
      input.focus();
    }

    function setTermValue(value, enabled) {
      if (enabled) selectedForTerm.add(value);
      else selectedForTerm.delete(value);
      syncTermSelect();

      /* Atualiza apenas o card afetado, sem reconstruir a grade inteira
         (evita o flash de fechar/reabrir ao clicar no toggle). */
      if (!grid) return;
      const card = grid.querySelector('[data-value="' + CSS.escape(value) + '"]');
      if (!card) return;

      card.classList.toggle("cv-search-picker__selected-card--has-term", enabled);

      const toggle = card.querySelector(".cv-search-picker__term-control .cv-field-side-action");
      if (toggle) {
        toggle.setAttribute("aria-pressed", enabled ? "true" : "false");
        toggle.textContent = presentation === "people"
          ? (enabled ? "Termo: sim" : "Termo: não")
          : (enabled ? "Gerar termo" : "Nao gerar");
        toggle.setAttribute("aria-label", enabled ? "Não gerar termo de autorização" : "Gerar termo de autorização");
        toggle.classList.toggle("cv-field-side-action--success", enabled);
        toggle.classList.toggle("cv-field-side-action--danger", !enabled);
        toggle.classList.toggle("is-active",   enabled);
        toggle.classList.toggle("is-inactive", !enabled);
      }
    }

    function updateDriverControls() {
      if (!grid) return;
      grid.querySelectorAll(".cv-search-picker__driver-toggle").forEach((button) => {
        const active = button.dataset.value === driverValue;
        const card = button.closest(".cv-search-picker__selected-card");
        const text = button.querySelector(".cv-search-picker__driver-text");
        button.setAttribute("aria-pressed", active ? "true" : "false");
        button.classList.toggle("cv-search-picker__driver-toggle--active", active);
        if (card) {
          card.classList.toggle("cv-search-picker__selected-card--driver", active);
          const surface = card.querySelector(".cv-search-picker__driver-surface");
          if (surface) {
            surface.setAttribute("aria-pressed", active ? "true" : "false");
            surface.setAttribute(
              "aria-label",
              active
                ? `${surface.dataset.label} é o motorista`
                : `Definir ${surface.dataset.label} como motorista`,
            );
          }
        }
        if (text && presentation === "people") {
          text.textContent = active ? "Motorista" : "Definir motorista";
        }
      });
    }

    function setDriverValue(value) {
      driverValue = value;
      select.dataset.pickerDriverValue = value;
      updateDriverControls();
      select.dispatchEvent(new CustomEvent("cv:search-picker-driver-change", {
        bubbles: true,
        detail: { value: value },
      }));
    }

    /* ── Render: Resultados do dropdown ─────────────────────────── */

    function renderOptionItem(item, index) {
      const btn    = el("button", "cv-search-picker__option");
      const marker = el("span",   "cv-search-picker__option-marker", "");
      const visual = el("span",   "cv-search-picker__option-visual", "");
      const body   = el("div",    "cv-search-picker__option-content");
      const status = el("span",   "cv-search-picker__option-status", "");
      const isVehicle = presentation === "vehicle";
      const isPerson = !isVehicle && (presentation === "people" || !!item.cargo || !!item.cpf || !!item.rg);
      const primaryText = (isPerson || isVehicle) ? item.label : (item.main || item.label);
      const main   = el("span",   "cv-search-picker__option-main", primaryText);
      let metaText = item.meta;

      if (isPerson) {
        btn.classList.add("cv-search-picker__option--person");
        visual.textContent = initialsFromLabel(item.label);
        metaText = uniqueTextParts([item.cargo, item.unidade]).join(" • ") || "Servidor cadastrado";
      } else if (isVehicle) {
        btn.classList.add("cv-search-picker__option--vehicle");
        visual.textContent = "V";
        metaText = item.cargo || item.meta;
      } else if (item.kind === "unidade") {
        visual.textContent = "U";
      } else {
        visual.textContent = "•";
      }

      btn.type = "button";
      btn.dataset.value = item.value;
      btn.setAttribute("role", "option");
      btn.setAttribute("aria-selected", item.selected ? "true" : "false");
      btn.classList.toggle("cv-search-picker__option--active", index === activeIndex);
      btn.classList.toggle("cv-search-picker__option--selected", item.selected);
      if (item.kind === "unidade") {
        btn.classList.add("cv-search-picker__option--unidade");
      }

      visual.setAttribute("aria-hidden", "true");
      status.setAttribute("aria-hidden", "true");
      status.textContent = item.selected
        ? "Selecionado"
        : (mode === "multi" ? "Adicionar" : "Escolher");

      body.appendChild(main);
      if (item.rascunho) {
        main.appendChild(el("span", "cv-chip cv-chip--warning cv-chip--compact", "Rascunho"));
      }
      if (metaText) {
        body.appendChild(el("span", "cv-search-picker__option-meta", metaText));
      }

      btn.appendChild(marker);
      btn.appendChild(visual);
      btn.appendChild(body);
      btn.appendChild(status);
      btn.addEventListener("mousedown", (e) => e.preventDefault());
      btn.addEventListener("click", () => selectItem(item.value));
      return btn;
    }

    function renderResults() {
      const visible = filteredItems();
      list.innerHTML = "";
      if (activeIndex >= visible.length) activeIndex = visible.length - 1;
      visible.forEach((item, i) => list.appendChild(renderOptionItem(item, i)));
      emptyEl.textContent = allowFreeText ? freeTextMsg : emptyMsg;
      emptyEl.hidden  = allowFreeText || !query || visible.length > 0;
      dropdown.hidden = !isOpen || (!query && visible.length === 0) || (allowFreeText && query && visible.length === 0);
    }

    /* ── Render: Controle de Termo ──────────────────────────────── */

    function buildTermControl(value) {
      const enabled = selectedForTerm.has(value);
      const row    = el("div",  "cv-search-picker__term-control");
      const label  = el("span", "cv-search-picker__term-label", "Termo de Autorizacao");

      /* Reutiliza o padrão cv-field-side-action--state (dot colorido + filled bg)
         usado nos demais toggles binários do sistema (ex: Possui RG). */
      const stateClass = enabled
        ? "cv-field-side-action--success is-active"
        : "cv-field-side-action--danger is-inactive";
      const toggle = el(
        "button",
        "cv-field-side-action cv-field-side-action--toggle cv-field-side-action--state " + stateClass,
        presentation === "people"
          ? (enabled ? "Termo: sim" : "Termo: não")
          : (enabled ? "Gerar termo" : "Nao gerar"),
      );

      toggle.type = "button";
      toggle.setAttribute("aria-pressed", enabled ? "true" : "false");
      toggle.setAttribute("aria-label", enabled ? "Não gerar termo de autorização" : "Gerar termo de autorização");

      toggle.addEventListener("click", () => {
        const current = toggle.getAttribute("aria-pressed") === "true";
        setTermValue(value, !current);
      });

      row.appendChild(label);
      row.appendChild(toggle);
      return row;
    }

    function buildDriverControl(item) {
      const active = driverValue === item.value;
      const row = el("div", "cv-search-picker__driver-control");
      const button = el("button", "cv-search-picker__driver-toggle");
      const marker = el("span", "cv-search-picker__driver-marker", "");
      const text = el(
        "span",
        "cv-search-picker__driver-text",
        presentation === "people" ? (active ? "Motorista" : "Definir motorista") : "Este servidor e o motorista",
      );

      button.type = "button";
      button.dataset.value = item.value;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.setAttribute("aria-label", (active ? "Desmarcar " : "Marcar ") + item.label + " como motorista");
      button.classList.toggle("cv-search-picker__driver-toggle--active", active);
      button.addEventListener("click", () => setDriverValue(driverValue === item.value ? "" : item.value));

      button.appendChild(marker);
      button.appendChild(text);
      row.appendChild(button);
      return row;
    }

    function buildDriverSurface(item) {
      const active = driverValue === item.value;
      const button = el("button", "cv-search-picker__driver-surface");
      button.type = "button";
      button.dataset.value = item.value;
      button.dataset.label = item.label;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.setAttribute(
        "aria-label",
        active ? `${item.label} é o motorista` : `Definir ${item.label} como motorista`,
      );
      button.addEventListener("click", () => setDriverValue(driverValue === item.value ? "" : item.value));
      return button;
    }

    /* ── Render: Cards selecionados ─────────────────────────────── */

    function buildCard(item) {
      const card = el("div", "cv-search-picker__selected-card");
      card.dataset.value = item.value;

      if (presentation === "people" || item.cpf || item.rg) {
        card.classList.add("cv-search-picker__selected-card--person");
      } else if (presentation === "vehicle") {
        card.classList.add("cv-search-picker__selected-card--vehicle");
      }

      const body  = el("div", "cv-search-picker__selected-main");
      const title = el("div", "cv-search-picker__selected-title-row");

      if (presentation === "people") {
        const name = el("span", "cv-search-picker__selected-name", item.label);
        title.appendChild(name);
        if (showDriverCtrl) title.appendChild(el("span", "cv-search-picker__driver-chip", "Motorista"));
        if (item.rascunho) title.appendChild(el("span", "cv-chip cv-chip--warning cv-chip--compact", "Rascunho"));
        body.appendChild(title);

        const infoParts = [];
        if (item.cargo) infoParts.push(item.cargo);
        if (item.unidade) infoParts.push(item.unidade);
        if (infoParts.length) {
          body.appendChild(el("span", "cv-search-picker__selected-meta", infoParts.join("  •  ")));
        }
      } else if (variant === "detailed") {
        /* ── Layout detalhado ──────────────────────────────────────
           Linha 1: Nome • Unidade lotada
           Linha 2: Cargo • CPF • RG (sem máscara)
        ─────────────────────────────────────────────────────────── */
        const nameParts = [item.label, item.unidade].filter(Boolean);
        const name = el("span", "cv-search-picker__selected-name", nameParts.join("  •  "));
        title.appendChild(name);
        if (showDriverCtrl) title.appendChild(el("span", "cv-search-picker__driver-chip", "Motorista"));
        if (item.rascunho) title.appendChild(el("span", "cv-chip cv-chip--warning cv-chip--compact", "Rascunho"));
        body.appendChild(title);

        const metaParts = [item.cargo, item.cpf, item.rg].filter(Boolean);
        if (metaParts.length) {
          body.appendChild(el("span", "cv-search-picker__selected-meta", metaParts.join("  •  ")));
        }
      } else {
        /* ── Layout compacto ───────────────────────────────────────
           Linha 1: Nome
           Linha 2: Cargo • Unidade
           Linha 3 (detail): CPF mascarado • RG mascarado
        ─────────────────────────────────────────────────────────── */
        const name = el("span", "cv-search-picker__selected-name", item.label);
        title.appendChild(name);
        if (showDriverCtrl) title.appendChild(el("span", "cv-search-picker__driver-chip", "Motorista"));
        if (item.rascunho) title.appendChild(el("span", "cv-chip cv-chip--warning cv-chip--compact", "Rascunho"));
        body.appendChild(title);

        const metaParts = [item.cargo, item.unidade].filter(Boolean);
        const metaText = metaParts.length
          ? metaParts.join(" • ")
          : (item.meta || "Dados complementares nao informados");
        body.appendChild(el("span", "cv-search-picker__selected-meta", metaText));

        const detailParts = [];
        if (item.cpf) detailParts.push("CPF: " + maskDocument(item.cpf, "cpf"));
        if (item.rg)  detailParts.push("RG: "  + maskDocument(item.rg, "rg"));
        if (detailParts.length) {
          body.appendChild(el("span", "cv-search-picker__selected-detail", detailParts.join("  •  ")));
        }
      }

      const removeBtn = el("button", "cv-search-picker__remove", presentation !== "default" ? "×" : "x");
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", "Remover " + item.label);
      removeBtn.addEventListener("click", () => removeItem(item.value));

      card.classList.toggle("cv-search-picker__selected-card--driver", driverValue === item.value);

      if (presentation === "people") {
        const nameParts = item.label.trim().split(/\s+/).filter(Boolean);
        const initials = [nameParts[0], nameParts.length > 1 ? nameParts[nameParts.length - 1] : ""]
          .filter(Boolean)
          .map((part) => part.charAt(0))
          .join("")
          .slice(0, 2)
          .toUpperCase();
        const avatar = el("span", "cv-search-picker__selected-avatar", initials || "•");
        const actions = el("div", "cv-search-picker__selected-actions");
        avatar.setAttribute("aria-hidden", "true");
        actions.setAttribute("role", "group");
        actions.setAttribute("aria-label", "Ações de " + item.label);

        if (showDriverCtrl) card.appendChild(buildDriverSurface(item));
        card.appendChild(avatar);
        card.appendChild(body);
        if (showDriverCtrl) {
          card.classList.add("cv-search-picker__selected-card--with-driver");
          actions.appendChild(buildDriverControl(item));
        }
        if (showTermCtrl) {
          card.classList.add("cv-search-picker__selected-card--with-term");
          actions.appendChild(buildTermControl(item.value));
          card.classList.toggle("cv-search-picker__selected-card--has-term", selectedForTerm.has(item.value));
        }
        actions.appendChild(removeBtn);
        card.appendChild(actions);
        return card;
      }

      card.appendChild(body);
      card.appendChild(removeBtn);

      /* Controle de Termo */
      if (showTermCtrl) {
        card.classList.add("cv-search-picker__selected-card--with-term");
        card.appendChild(buildTermControl(item.value));
        card.classList.toggle("cv-search-picker__selected-card--has-term", selectedForTerm.has(item.value));
      }

      /* Botão de motorista — apenas quando explicitamente habilitado */
      if (showDriverCtrl) {
        card.classList.add("cv-search-picker__selected-card--with-driver");
        card.appendChild(buildDriverControl(item));
      }

      return card;
    }

    function renderSelectedCards() {
      if (!grid) return;
      const sel = selectedItems();
      grid.innerHTML = "";
      sel.forEach((item) => grid.appendChild(buildCard(item)));
      if (panelEmpty) panelEmpty.hidden = sel.length > 0;
      if (counter)    counter.textContent = String(sel.length);
      if (panelTitleEl && presentation === "people") {
        panelTitleEl.textContent = sel.length === 1 ? "1 pessoa na equipe" : `${sel.length} pessoas na equipe`;
      }
    }

    /* ── Render principal ───────────────────────────────────────── */

    function render() {
      renderResults();
      if (showPanel) renderSelectedCards();
    }

    /* ── Eventos ────────────────────────────────────────────────── */

    input.addEventListener("focus", () => {
      if (query || openAllOnFocus) setOpen(true);
    });

    input.addEventListener("input", () => {
      normalizeInputValue();
      query       = input.value;
      activeIndex = 0;
      setHasQuery(!!query);
      setOpen(!!query);
      renderResults();
    });

    clearBtn.addEventListener("mousedown", (e) => e.preventDefault());
    clearBtn.addEventListener("click", () => {
      /* No modo single, limpar também deseleciona o item */
      if (mode === "single") {
        options.forEach((o) => { o.selected = false; });
        syncSelect(true);
      }
      query       = "";
      input.value = "";
      activeIndex = -1;
      setHasQuery(false);
      setOpen(false);
      input.focus();
    });

    input.addEventListener("keydown", (e) => {
      const visible = filteredItems();
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const item = visible[Math.max(activeIndex, 0)];
        if (item) selectItem(item.value);
        else commitFreeText();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeIndex = Math.min(activeIndex + 1, visible.length - 1);
        setOpen(!!query);
        renderResults();
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        setOpen(!!query);
        renderResults();
      }
    });

    /* Fecha dropdown ao clicar fora */
    document.addEventListener("click", (e) => {
      if (!root.contains(e.target) && e.target !== select) setOpen(false);
    });

    /* Sincroniza quando o select nativo muda externamente */
    select.addEventListener("change", () => {
      const sel = new Set(Array.from(select.selectedOptions).map((o) => o.value));
      options.forEach((o) => { o.selected = sel.has(o.value); });
      if (mode === "single" && !showPanel) {
        const selItem = options.find((o) => o.selected);
        input.value = selItem ? selItem.label : "";
        setHasQuery(!!input.value);
      }
      render();
    });

    syncSelect(false);

    if (mode === "single" && initialValue && !select.value) {
      select.value = initialValue;
      const selected = new Set(Array.from(select.selectedOptions).map((o) => o.value));
      options.forEach((o) => { o.selected = selected.has(o.value); });
    }

    /* No modo single sem painel: inicializa o input com o valor já selecionado */
    if (mode === "single" && !showPanel) {
      const selItem = options.find((o) => o.selected);
      if (selItem) {
        input.value = selItem.label;
        setHasQuery(true);
      }
    }

    render();
  }

  /* ── Boot ───────────────────────────────────────────────────────── */

  function init(root) {
    const scope = root && root.querySelectorAll ? root : document;
    if (scope.matches && scope.matches(SELECTOR)) initPicker(scope);
    scope.querySelectorAll(SELECTOR).forEach(initPicker);
    renderers.forEach((renderer) => renderer(scope));
  }

  function boot() {
    init(document);
  }

  window.CV = window.CV || {};
  window.CV.picker = {
    boot,
    init,
    initSearch: init,
    registerRenderer(renderer) {
      if (typeof renderer === "function" && !renderers.includes(renderer)) {
        renderers.push(renderer);
      }
    },
  };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("picker", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
