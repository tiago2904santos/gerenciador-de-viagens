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

    const root = el("div", `cv-search-picker cv-search-picker--${variant}`);
    if (mode === "single") root.classList.add("cv-search-picker--single");
    if (select.disabled)   root.classList.add("cv-search-picker--disabled");
    if (isError)           root.classList.add("cv-search-picker--error");

    /* Área de busca */
    const searchWrap = el("div",    "cv-search-picker__search");
    const inputWrap  = el("div",    "cv-search-picker__input-wrap");
    const input      = el("input",  "cv-search-picker__input");
    const clearBtn   = el("button", "cv-search-picker__clear", "×");
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

    list.id = listboxId;
    list.setAttribute("role", "listbox");
    list.setAttribute("aria-multiselectable", mode === "multi" ? "true" : "false");
    dropdown.hidden = true;

    dropdown.appendChild(list);
    dropdown.appendChild(emptyEl);
    inputWrap.appendChild(input);
    inputWrap.appendChild(clearBtn);
    searchWrap.appendChild(inputWrap);
    searchWrap.appendChild(dropdown);
    root.appendChild(searchWrap);

    /* Painel de selecionados — apenas no modo multi */
    let panel = null, grid = null, counter = null, panelEmpty = null;
    if (mode === "multi") {
      panel      = el("section", "cv-search-picker__panel");
      const panelHeader = el("div",  "cv-search-picker__panel-header");
      const titleEl     = el("h4",   "cv-search-picker__panel-title", panelTitle);
      counter    = el("span", "cv-search-picker__counter", "0");
      grid       = el("div",  "cv-search-picker__grid");
      panelEmpty = el("p",    "cv-search-picker__panel-empty", emptyPanelMsg);

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

    /* ── Render: Resultados do dropdown ─────────────────────────── */

    function renderOptionItem(item, index) {
      const btn    = el("button", "cv-search-picker__option");
      const marker = el("span",   "cv-search-picker__option-marker", "✓");
      const body   = el("div",    "cv-search-picker__option-body");
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
      const row     = el("div",  "cv-term-control");
      const label   = el("span", "cv-term-control__label", "Termo de Autorização");
      const choice  = el("div",  "cv-term-control__choice");

      const btnNo  = el("button", "cv-term-control__option cv-term-control__option--no",  "Não gerar");
      const btnYes = el("button", "cv-term-control__option cv-term-control__option--yes", "Gerar");

      btnNo.type  = "button";
      btnYes.type = "button";
      btnNo.setAttribute("aria-pressed",  !enabled ? "true" : "false");
      btnYes.setAttribute("aria-pressed",  enabled ? "true" : "false");
      btnNo.classList.toggle("cv-term-control__option--active",  !enabled);
      btnYes.classList.toggle("cv-term-control__option--active",  enabled);
      btnNo.addEventListener("click",  () => setTermValue(value, false));
      btnYes.addEventListener("click", () => setTermValue(value, true));

      choice.appendChild(btnNo);
      choice.appendChild(btnYes);
      row.appendChild(label);
      row.appendChild(choice);
      return row;
    }

    /* ── Render: Cards selecionados ─────────────────────────────── */

    function buildCard(item) {
      const card = el("div", "cv-search-picker__card");
      card.dataset.value = item.value;

      const body = el("div",  "cv-search-picker__card-body");
      const name = el("span", "cv-search-picker__card-name", item.label);
      const metaParts = [item.cargo, item.unidade].filter(Boolean);
      const meta = el(
        "span",
        "cv-search-picker__card-meta",
        metaParts.length ? metaParts.join(" • ") : "Dados complementares não informados",
      );
      body.appendChild(name);
      body.appendChild(meta);

      /* Detalhe: CPF / RG — exibido pelo CSS apenas no modo --detailed */
      const detailParts = [];
      if (item.cpf) detailParts.push("CPF: " + item.cpf);
      if (item.rg)  detailParts.push("RG: "  + item.rg);
      if (detailParts.length) {
        body.appendChild(el("span", "cv-search-picker__card-detail", detailParts.join("  •  ")));
      }

      const removeBtn = el("button", "cv-search-picker__card-remove", "×");
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", "Remover " + item.label);
      removeBtn.addEventListener("click", () => removeItem(item.value));

      card.appendChild(body);
      card.appendChild(removeBtn);

      /* Controle de Termo */
      if (showTermCtrl) {
        card.appendChild(buildTermControl(item.value));
        card.classList.toggle("cv-search-picker__card--has-termo", selectedForTerm.has(item.value));
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
