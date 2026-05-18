(function () {
  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function selectedValues(select) {
    return new Set(Array.from(select.selectedOptions).map((option) => option.value));
  }

  function syncTarget(target, selected) {
    Array.from(target.options).forEach((option) => {
      option.selected = selected.has(option.value);
    });
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function buildOption(label, modifier, active, onClick) {
    const button = createElement(
      "button",
      `oficio-viajante-card__termo-option oficio-viajante-card__termo-option--${modifier}`,
      label,
    );
    button.type = "button";
    button.setAttribute("aria-pressed", active ? "true" : "false");
    button.classList.toggle("oficio-viajante-card__termo-option--active", active);
    button.addEventListener("click", onClick);
    return button;
  }

  function init(root) {
    const source = document.querySelector("select[name='servidores']");
    const target = root.querySelector("select[name='servidores_termo_autorizacao']");
    if (!source || !target) return;

    target.classList.add("app-termos-selector__native");
    target.setAttribute("aria-hidden", "true");
    target.tabIndex = -1;

    const knownSelected = new Set(Array.from(source.selectedOptions).map((option) => option.value));
    let selectedForTerm = selectedValues(target);
    let renderQueued = false;

    function sourceValues() {
      return new Set(Array.from(source.selectedOptions).filter((option) => option.value).map((option) => option.value));
    }

    function setTermValue(value, enabled) {
      if (enabled) selectedForTerm.add(value);
      else selectedForTerm.delete(value);
      render();
    }

    function renderControl(card, value) {
      card.querySelector(".oficio-viajante-card__termo")?.remove();

      const enabled = selectedForTerm.has(value);
      const row = createElement("div", "oficio-viajante-card__termo");
      const label = createElement("span", "oficio-viajante-card__termo-label", "Termo de Autorização");
      const choices = createElement("div", "oficio-viajante-card__termo-choice");

      choices.appendChild(buildOption("Não gerar", "no", !enabled, () => setTermValue(value, false)));
      choices.appendChild(buildOption("Gerar", "yes", enabled, () => setTermValue(value, true)));

      row.appendChild(label);
      row.appendChild(choices);
      card.appendChild(row);
      card.classList.toggle("oficio-viajante-card--termo", enabled);
    }

    function render() {
      renderQueued = false;
      const currentSourceValues = sourceValues();

      Array.from(source.selectedOptions).forEach((option) => {
        if (option.value && !knownSelected.has(option.value)) {
          selectedForTerm.add(option.value);
          knownSelected.add(option.value);
        }
      });

      selectedForTerm = new Set(Array.from(selectedForTerm).filter((value) => currentSourceValues.has(value)));
      syncTarget(target, selectedForTerm);

      document.querySelectorAll(".oficio-equipe-picker__selected-card[data-value]").forEach((card) => {
        const value = card.dataset.value || "";
        if (currentSourceValues.has(value)) renderControl(card, value);
      });
    }

    function scheduleRender() {
      if (renderQueued) return;
      renderQueued = true;
      window.requestAnimationFrame(render);
    }

    source.addEventListener("change", scheduleRender);
    render();
  }

  function boot() {
    document.querySelectorAll("[data-oficio-termos-selector]").forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
