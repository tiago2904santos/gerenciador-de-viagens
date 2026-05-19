(function () {
  function getLabels(root) {
    return {
      on: root.dataset.onLabel || "LIGADA",
      off: root.dataset.offLabel || "DESLIGADA",
    };
  }

  function syncCardToggle(root) {
    const input = root.querySelector('input[type="checkbox"]');
    if (!input) return;

    const labels = getLabels(root);
    const state = root.querySelector("[data-card-toggle-state]");

    root.classList.toggle("is-checked", input.checked);
    root.classList.toggle("is-disabled", input.disabled);
    input.setAttribute("aria-checked", input.checked ? "true" : "false");

    if (state) {
      state.textContent = input.checked ? labels.on : labels.off;
    }
  }

  function initCardToggles() {
    document.querySelectorAll("[data-card-toggle]").forEach((root) => {
      const input = root.querySelector('input[type="checkbox"]');
      if (!input) return;

      syncCardToggle(root);
      input.addEventListener("change", () => syncCardToggle(root));
    });
  }

  function applyServidorSemRgUi(form, opts) {
    const semRg = form.querySelector("#id_sem_rg");
    const rg = form.querySelector("#id_rg");
    const wrap = form.querySelector("[data-rg-field-wrap]");
    const button = form.querySelector("[data-rg-toggle]");
    if (!semRg || !rg || !wrap) return;

    const active = semRg.checked;
    const rgTechnicalValue = (rg.value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    rg.disabled = active;
    rg.setAttribute("aria-disabled", active ? "true" : "false");
    wrap.classList.toggle("field--locked", active);

    if (button) {
      button.classList.toggle("cv-field-side-action--success", !active);
      button.classList.toggle("cv-field-side-action--danger", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
      const label = button.querySelector("span:last-child");
      if (label) label.textContent = active ? "Não possui RG" : "Possui RG";
    }

    if (active && (rgTechnicalValue === "NAOPOSSUIRG" || rgTechnicalValue.includes("POSSUI"))) {
      rg.value = "";
    } else if (opts && opts.clearRgOnLock && active) {
      if (rg.value && rg.value !== "NAO POSSUI RG") {
        rg.dataset.previousValue = rg.value;
      }
      rg.value = "";
    } else if (!active && rg.value === "NAO POSSUI RG") {
      rg.value = "";
    } else if (!active && rg.dataset.previousValue && !rg.value) {
      rg.value = rg.dataset.previousValue;
    }
  }

  function initServidorSemRg() {
    const form = document.querySelector("[data-servidor-sem-rg-form]");
    if (!form) return;

    const semRg = form.querySelector("#id_sem_rg");
    const button = form.querySelector("[data-rg-toggle]");
    if (!semRg) return;

    applyServidorSemRgUi(form, { clearRgOnLock: false });
    semRg.addEventListener("change", () => applyServidorSemRgUi(form, { clearRgOnLock: true }));
    if (button) {
      button.addEventListener("click", () => {
        semRg.checked = !semRg.checked;
        semRg.dispatchEvent(new Event("change", { bubbles: true }));
      });
    }
  }

  function boot() {
    initCardToggles();
    initServidorSemRg();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
