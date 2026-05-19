(function () {
  "use strict";

  const SELECTOR = "select[data-cv-search-picker]";

  /* ── Utilitários ─────────────────────────────────────────────── */

  function normalize(value) {
    return (value || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "");
  }

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

  function readOption(option) {
    return {
      cargo:    option.dataset.cargo    || "",
      cpf:      option.dataset.cpf      || "",
      disabled: option.disabled,
      label:    (option.textContent || "").trim(),
      main:     option.dataset.main     || (option.textContent || "").trim(),
      meta:     option.dataset.meta     || option.dataset.unidade || "",
      rg:       option.dataset.rg       || "",
      search:   option.dataset.search   || option.textContent    || "",
      selected: option.selected,
      unidade:  option.dataset.unidade  || "",
      value:    option.value,
    };
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

  /* ── Inicialização do picker ──────────────────────────────────── */

  function initPicker(select) {
    if (!select || select.dataset.cvSearchPickerReady === "true") return;
    select.dataset.cvSearchPickerReady = "true";

    /* Configuração via data-* */
    const mode         = select.dataset.pickerMode        || "multi";   /* single | multi */
    const variant      = select.dataset.pickerVariant     || "compact"; /* compact | detailed */
    const placeholder  = select.dataset.placeholder       || "Digite para buscar";
    const emptyMsg     = select.dataset.emptyMessage      || "Nenhum resultado encontrado.";
    const emptyPanelMsg = select.dataset.emptySelected    || "Nenhum item selecionado.";
    const panelTitle   = select.dataset.panelTitle        || "SELECIONADOS";
    const termosName   = select.dataset.cvTermosName      || "";
    const showTermCtrl = select.dataset.pickerTermControl === "true" || !!termosName;
    const isError      = select.dataset.pickerError       === "true";
    const listboxId    = `${select.id || select.name || "cv-picker"}-results`;

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
    if (select.disabled)   root.classList.add("cv-search-picker--disabled");
    if (isError)           root.classList.add("cv-search-picker--error");

    const fieldLabel = select.dataset.pickerLabel || "";
    const fieldHint  = select.dataset.pickerHint  || "";

    /* Área de busca */
    const field      = el("div",    "cv-search-picker__field");
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

    if (fieldLabel) field.appendChild(el("div", "cv-search-picker__label", fieldLabel));
    if (fieldHint) field.appendChild(el("div", "cv-search-picker__hint", fieldHint));
    dropdown.appendChild(list);
    dropdown.appendChild(emptyEl);
    control.appendChild(icon);
    control.appendChild(input);
    control.appendChild(clearBtn);
    field.appendChild(control);
    field.appendChild(dropdown);
    root.appendChild(field);

    /* Painel de selecionados — apenas no modo multi */
    let panel = null, grid = null, counter = null, panelEmpty = null;
    if (mode === "multi") {
      panel      = el("section", "cv-search-picker__selected-panel");
      const panelHeader = el("div",  "cv-search-picker__selected-header");
      const titleEl     = el("h4",   "cv-search-picker__selected-title", panelTitle);
      counter    = el("span", "cv-search-picker__selected-count", "0");
      grid       = el("div",  "cv-search-picker__selected-list");
      panelEmpty = el("p",    "cv-search-picker__selected-empty", emptyPanelMsg);

      panelHeader.appendChild(titleEl);
      panelHeader.appendChild(counter);
      panel.appendChild(panelHeader);
      panel.appendChild(grid);
      panel.appendChild(panelEmpty);
      root.appendChild(panel);
    }

    select.insertAdjacentElement("afterend", root);

    /* ── Helpers de estado ──────────────────────────────────────── */

    function selectedItems() {
      return options.filter((o) => o.selected);
    }

    function filteredItems() {
      const term = normalize(query);
      if (!term) return [];
      if (mode === "single") {
        return options.filter((o) => normalize(o.search).includes(term));
      }
      return options.filter((o) => !o.selected && normalize(o.search).includes(term));
    }

    function syncSelect(dispatch) {
      const sel = new Set(selectedItems().map((o) => o.value));
      Array.from(select.options).forEach((o) => { o.selected = sel.has(o.value); });
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
      isOpen = next && !!query && !select.disabled;
      dropdown.hidden = !isOpen;
      input.setAttribute("aria-expanded", isOpen ? "true" : "false");
      root.classList.toggle("cv-search-picker--open", isOpen);
      renderResults();
    }

    /* ── Seleção / Remoção ──────────────────────────────────────── */

    function selectItem(value) {
      const item = options.find((o) => o.value === value);
      if (!item || item.disabled) return;

      if (mode === "single") {
        /* Deseleciona tudo e seleciona só o item escolhido */
        options.forEach((o) => { o.selected = false; });
        item.selected = true;
        input.value   = item.label;
        query         = "";
        setHasQuery(true); /* mantém o clear visível com o valor preenchido */
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
      if (driverValue === value) driverValue = "";
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
      renderSelectedCards();
    }

    function updateDriverControls() {
      if (!grid) return;
      grid.querySelectorAll(".cv-search-picker__driver-toggle").forEach((button) => {
        const active = button.dataset.value === driverValue;
        const card = button.closest(".cv-search-picker__selected-card");
        button.setAttribute("aria-pressed", active ? "true" : "false");
        button.classList.toggle("cv-search-picker__driver-toggle--active", active);
        if (card) card.classList.toggle("cv-search-picker__selected-card--driver", active);
      });
    }

    function setDriverValue(value) {
      driverValue = driverValue === value ? "" : value;
      updateDriverControls();
    }

    /* ── Render: Resultados do dropdown ─────────────────────────── */

    function renderOptionItem(item, index) {
      const btn    = el("button", "cv-search-picker__option");
      const marker = el("span",   "cv-search-picker__option-marker", "");
      const body   = el("div",    "cv-search-picker__option-content");
      const main   = el("span",   "cv-search-picker__option-main", item.main || item.label);

      btn.type = "button";
      btn.dataset.value = item.value;
      btn.setAttribute("role", "option");
      btn.setAttribute("aria-selected", item.selected ? "true" : "false");
      btn.classList.toggle("cv-search-picker__option--active",   index === activeIndex);
      btn.classList.toggle("cv-search-picker__option--selected", item.selected);

      body.appendChild(main);
      if (item.meta) {
        body.appendChild(el("span", "cv-search-picker__option-meta", item.meta));
      }

      btn.appendChild(marker);
      btn.appendChild(body);
      btn.addEventListener("mousedown", (e) => e.preventDefault());
      btn.addEventListener("click", () => selectItem(item.value));
      return btn;
    }

    function renderResults() {
      const visible = filteredItems();
      list.innerHTML = "";
      if (activeIndex >= visible.length) activeIndex = visible.length - 1;
      visible.forEach((item, i) => list.appendChild(renderOptionItem(item, i)));
      emptyEl.hidden  = !query || visible.length > 0;
      dropdown.hidden = !isOpen || (!query && visible.length === 0);
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
        enabled ? "Gerar termo" : "Nao gerar",
      );

      toggle.type = "button";
      toggle.setAttribute("aria-pressed", enabled ? "true" : "false");

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
      const text = el("span", "cv-search-picker__driver-text", "Este servidor e o motorista");

      button.type = "button";
      button.dataset.value = item.value;
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.setAttribute("aria-label", (active ? "Desmarcar " : "Marcar ") + item.label + " como motorista");
      button.classList.toggle("cv-search-picker__driver-toggle--active", active);
      button.addEventListener("click", () => setDriverValue(item.value));

      button.appendChild(marker);
      button.appendChild(text);
      row.appendChild(button);
      return row;
    }

    /* ── Render: Cards selecionados ─────────────────────────────── */

    function buildCard(item) {
      const card = el("div", "cv-search-picker__selected-card");
      card.dataset.value = item.value;

      const body = el("div",  "cv-search-picker__selected-main");
      const title = el("div", "cv-search-picker__selected-title-row");
      const name = el("span", "cv-search-picker__selected-name", item.label);
      const driverChip = el("span", "cv-search-picker__driver-chip", "Motorista");
      const metaParts = [item.cargo, item.unidade].filter(Boolean);
      const meta = el(
        "span",
        "cv-search-picker__selected-meta",
        metaParts.length ? metaParts.join(" • ") : "Dados complementares não informados",
      );
      title.appendChild(name);
      title.appendChild(driverChip);
      body.appendChild(title);
      body.appendChild(meta);

      /* Detalhe: CPF / RG — exibido pelo CSS apenas no modo --detailed */
      const detailParts = [];
      if (item.cpf) detailParts.push("CPF: " + maskDocument(item.cpf, "cpf"));
      if (item.rg)  detailParts.push("RG: "  + maskDocument(item.rg, "rg"));
      if (detailParts.length) {
        body.appendChild(el("span", "cv-search-picker__selected-detail", detailParts.join("  •  ")));
      }

      const removeBtn = el("button", "cv-search-picker__remove", "x");
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", "Remover " + item.label);
      removeBtn.addEventListener("click", () => removeItem(item.value));

      card.appendChild(body);
      card.appendChild(removeBtn);
      card.classList.toggle("cv-search-picker__selected-card--driver", driverValue === item.value);

      /* Controle de Termo */
      if (showTermCtrl) {
        card.classList.add("cv-search-picker__selected-card--with-term");
        card.appendChild(buildTermControl(item.value));
        card.classList.toggle("cv-search-picker__selected-card--has-term", selectedForTerm.has(item.value));
      }

      card.appendChild(buildDriverControl(item));

      return card;
    }

    function renderSelectedCards() {
      if (!grid) return;
      const sel = selectedItems();
      grid.innerHTML = "";
      sel.forEach((item) => grid.appendChild(buildCard(item)));
      if (panelEmpty) panelEmpty.hidden = sel.length > 0;
      if (counter)    counter.textContent = String(sel.length);
    }

    /* ── Render principal ───────────────────────────────────────── */

    function render() {
      renderResults();
      if (mode === "multi") renderSelectedCards();
    }

    /* ── Eventos ────────────────────────────────────────────────── */

    input.addEventListener("focus", () => {
      if (query) setOpen(true);
    });

    input.addEventListener("input", () => {
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
      if (mode === "single") {
        const selItem = options.find((o) => o.selected);
        input.value = selItem ? selItem.label : "";
        setHasQuery(!!input.value);
      }
      render();
    });

    syncSelect(false);

    /* No modo single: inicializa o input com o valor já selecionado */
    if (mode === "single") {
      const selItem = options.find((o) => o.selected);
      if (selItem) {
        input.value = selItem.label;
        setHasQuery(true);
      }
    }

    render();
  }

  /* ── Boot ───────────────────────────────────────────────────────── */

  function boot() {
    document.querySelectorAll(SELECTOR).forEach(initPicker);
  }

  window.CvSearchPicker = { boot };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
