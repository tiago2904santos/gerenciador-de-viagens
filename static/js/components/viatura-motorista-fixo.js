(function () {
  "use strict";

  function applyViaturaMotoristaFixoUi(form, opts) {
    const temMotoristaFixo = form.querySelector("#id_tem_motorista_fixo");
    const panel = form.querySelector("[data-viatura-motoristas-panel]");
    const button = form.querySelector("[data-motorista-fixo-toggle]");
    const motoristasSelect = form.querySelector("#id_motoristas");
    if (!temMotoristaFixo || !panel) return;

    const hasFixed = temMotoristaFixo.checked;
    panel.classList.toggle("viatura-motoristas-panel--open", hasFixed);
    panel.setAttribute("aria-hidden", hasFixed ? "false" : "true");

    if (button) {
      button.classList.toggle("cv-field-side-action--success", hasFixed);
      button.classList.toggle("cv-field-side-action--danger", !hasFixed);
      button.classList.toggle("is-active", hasFixed);
      button.classList.toggle("is-inactive", !hasFixed);
      button.setAttribute("aria-pressed", hasFixed ? "true" : "false");
      const label = button.querySelector("span:last-child");
      const activeLabel = button.dataset.mfLabelActive || "Com Motorista";
      const inactiveLabel = button.dataset.mfLabelInactive || "Sem Motorista";
      if (label) label.textContent = hasFixed ? activeLabel : inactiveLabel;
    }

    if (!hasFixed && motoristasSelect && opts && opts.clearOnHide) {
      Array.from(motoristasSelect.options).forEach((option) => {
        option.selected = false;
      });
      motoristasSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function initViaturaMotoristaFixoForms() {
    document.querySelectorAll("[data-viatura-motorista-form]").forEach((form) => {
      const temMotoristaFixo = form.querySelector("#id_tem_motorista_fixo");
      if (!temMotoristaFixo) return;

      applyViaturaMotoristaFixoUi(form, { clearOnHide: false });
      temMotoristaFixo.addEventListener("change", () =>
        applyViaturaMotoristaFixoUi(form, { clearOnHide: true }),
      );
    });
  }

  function initViaturaMotoristaFixoButton() {
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-motorista-fixo-toggle]");
      if (!button) return;

      const form = button.closest("[data-viatura-motorista-form]");
      const temMotoristaFixo = form ? form.querySelector("#id_tem_motorista_fixo") : null;
      if (!form || !temMotoristaFixo) return;

      event.preventDefault();
      temMotoristaFixo.checked = !temMotoristaFixo.checked;
      temMotoristaFixo.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function boot() {
    initViaturaMotoristaFixoForms();
    initViaturaMotoristaFixoButton();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
