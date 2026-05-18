(function () {
  const SELECTOR = "select[data-app-motorista-picker]";

  function normalize(value) {
    return (value || "")
      .toString()
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function dispatchNativeEvents(select) {
    select.dispatchEvent(new Event("input", { bubbles: true }));
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function optionData(option) {
    return {
      cargo: option.dataset.cargo || "",
      cpf: option.dataset.cpf || "",
      disabled: option.disabled,
      label: (option.textContent || "").trim(),
      main: option.dataset.main || (option.textContent || "").trim(),
      meta: option.dataset.meta || option.dataset.unidade || "",
      rg: option.dataset.rg || "",
      search: option.dataset.search || option.textContent || "",
      unidade: option.dataset.unidade || "",
      value: option.value,
    };
  }

  function initPicker(select) {
    if (!select || select.dataset.appMotoristaPickerReady === "true") return;
    select.dataset.appMotoristaPickerReady = "true";
    select.classList.add("app-motorista-picker__native");

    const options = Array.from(select.options).map(optionData).filter((item) => item.value !== "");
    const placeholder = select.dataset.placeholder || "Digite para buscar";
    const emptyMessage = select.dataset.emptyMessage || "Nenhum resultado encontrado.";
    const emptySelected = select.dataset.emptySelected || "Nenhum servidor selecionado.";
    const panelTitle = select.dataset.panelTitle || "MOTORISTA SELECIONADO";
    const statusWaiting = select.dataset.statusWaiting || "Aguardando seleção";
    const listboxId = `${select.id || select.name || "app-motorista-picker"}-results`;
    let query = "";
    let activeIndex = -1;
    let isOpen = false;

    const root = createElement("div", "app-motorista-picker oficio-motorista-picker oficio-equipe-picker");
    const searchGroup = createElement("div", "oficio-equipe-picker__search-group");
    const search = createElement("input", "oficio-equipe-picker__input");
    const results = createElement("div", "oficio-equipe-picker__results");
    const listbox = createElement("div", "oficio-equipe-picker__results-list");
    const empty = createElement("div", "oficio-equipe-picker__empty", emptyMessage);
    const selectedPanel = createElement(
      "section",
      "oficio-motorista-picker__selected-panel oficio-equipe-picker__selected-panel app-form-grid-panel",
    );
    const selectedHeader = createElement("div", "oficio-equipe-picker__selected-header");
    const selectedTitle = createElement("h4", "oficio-equipe-picker__selected-title", panelTitle);
    const statusBadge = createElement("span", "oficio-motorista-picker__status", statusWaiting);
    const selectedList = createElement("div", "oficio-equipe-picker__selected-list");
    const selectedEmpty = createElement("p", "oficio-equipe-picker__selected-empty", emptySelected);

    search.type = "search";
    search.placeholder = placeholder;
    search.autocomplete = "off";
    search.disabled = select.disabled;
    search.setAttribute("role", "combobox");
    search.setAttribute("aria-expanded", "false");
    search.setAttribute("aria-controls", listboxId);
    search.setAttribute("aria-autocomplete", "list");
    results.hidden = true;
    listbox.id = listboxId;
    listbox.setAttribute("role", "listbox");

    searchGroup.appendChild(search);
    results.appendChild(listbox);
    results.appendChild(empty);
    selectedHeader.appendChild(selectedTitle);
    selectedHeader.appendChild(statusBadge);
    selectedPanel.appendChild(selectedHeader);
    selectedPanel.appendChild(selectedList);
    selectedPanel.appendChild(selectedEmpty);
    root.appendChild(searchGroup);
    root.appendChild(results);
    root.appendChild(selectedPanel);
    select.insertAdjacentElement("afterend", root);

    function selectedItem() {
      const item = options.find((candidate) => candidate.value === select.value);
      return item || null;
    }

    function filteredItems() {
      const term = normalize(query);
      if (!term) return [];
      return options.filter((item) => normalize(item.search).includes(term));
    }

    function syncSelect(shouldDispatch) {
      if (shouldDispatch) dispatchNativeEvents(select);
    }

    function setOpen(nextOpen) {
      isOpen = nextOpen && !!query && !select.disabled;
      results.hidden = !isOpen;
      search.setAttribute("aria-expanded", isOpen ? "true" : "false");
      root.classList.toggle("oficio-equipe-picker--open", isOpen);
      renderResults();
    }

    function selectItem(value) {
      const item = options.find((candidate) => candidate.value === value);
      if (!item || item.disabled) return;
      select.value = value;
      query = "";
      activeIndex = -1;
      search.value = "";
      syncSelect(true);
      render();
      setOpen(false);
      search.focus();
    }

    function clearSelection() {
      select.value = "";
      syncSelect(true);
      render();
      search.focus();
    }

    function renderResultItem(item, index) {
      const button = createElement("button", "oficio-equipe-picker__result");
      const main = createElement("span", "oficio-equipe-picker__result-main", item.main || item.label);
      const meta = createElement("span", "oficio-equipe-picker__result-meta", item.meta || "Sem unidade informada");
      button.type = "button";
      button.dataset.value = item.value;
      button.setAttribute("role", "option");
      button.classList.toggle("oficio-equipe-picker__result--active", index === activeIndex);
      button.appendChild(main);
      button.appendChild(meta);
      button.addEventListener("mousedown", (event) => event.preventDefault());
      button.addEventListener("click", () => selectItem(item.value));
      return button;
    }

    function renderResults() {
      const visible = filteredItems();
      listbox.innerHTML = "";
      if (activeIndex >= visible.length) activeIndex = visible.length - 1;
      visible.forEach((item, index) => {
        listbox.appendChild(renderResultItem(item, index));
      });
      empty.hidden = !query || visible.length > 0;
      results.hidden = !isOpen || (!query && visible.length === 0);
    }

    function renderSelected() {
      const item = selectedItem();
      selectedList.innerHTML = "";
      if (!item) {
        selectedEmpty.hidden = false;
        statusBadge.textContent = statusWaiting;
        statusBadge.classList.remove("oficio-motorista-picker__status--ok");
        return;
      }
      selectedEmpty.hidden = true;
      statusBadge.textContent = "Motorista definido";
      statusBadge.classList.add("oficio-motorista-picker__status--ok");

      const card = createElement("div", "oficio-equipe-picker__selected-card");
      const copy = createElement("div", "oficio-equipe-picker__selected-copy");
      const name = createElement("span", "oficio-equipe-picker__selected-name", item.label);
      const rgcpf = [item.rg ? `RG ${item.rg}` : "", item.cpf ? `CPF ${item.cpf}` : ""].filter(Boolean).join(" • ");
      const metaParts = [item.cargo, item.unidade].filter(Boolean);
      const metaLine = [rgcpf, metaParts.join(" • ")].filter(Boolean).join(" — ");
      const meta = createElement(
        "span",
        "oficio-equipe-picker__selected-meta",
        metaLine || "Dados complementares não informados",
      );
      const remove = createElement("button", "oficio-equipe-picker__remove", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", `Remover ${item.label}`);
      remove.addEventListener("click", () => clearSelection());
      copy.appendChild(name);
      copy.appendChild(meta);
      card.appendChild(copy);
      card.appendChild(remove);
      selectedList.appendChild(card);
    }

    function render() {
      renderResults();
      renderSelected();
    }

    search.addEventListener("focus", () => {
      if (query) setOpen(true);
    });
    search.addEventListener("input", () => {
      query = search.value;
      activeIndex = 0;
      setOpen(!!query);
      renderResults();
    });
    search.addEventListener("keydown", (event) => {
      const visible = filteredItems();
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        const item = visible[Math.max(activeIndex, 0)];
        if (item) selectItem(item.value);
        return;
      }
      if (event.key === "ArrowDown") {
        event.preventDefault();
        activeIndex = Math.min(activeIndex + 1, visible.length - 1);
        setOpen(!!query);
        renderResults();
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        activeIndex = Math.max(activeIndex - 1, 0);
        setOpen(!!query);
        renderResults();
      }
    });

    document.addEventListener("click", (event) => {
      if (!root.contains(event.target) && event.target !== select) setOpen(false);
    });

    select.addEventListener("change", () => {
      render();
    });

    render();
  }

  function boot() {
    document.querySelectorAll(SELECTOR).forEach(initPicker);
  }

  window.AppMotoristaPicker = { boot };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
