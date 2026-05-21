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
    if (!semRg || !rg || !wrap) return;

    const active = semRg.checked;
    const rgTechnicalValue = (rg.value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
    rg.disabled = active;
    rg.setAttribute("aria-disabled", active ? "true" : "false");
    wrap.classList.toggle("field--locked", active);

    if (active && (rgTechnicalValue === "NAOPOSSUIRG" || rgTechnicalValue.includes("POSSUI"))) {
      rg.value = "";
    } else if (opts && opts.clearRgOnLock && active) {
      if (rg.value && rg.value !== "NAO POSSUI RG") {
        rg.dataset.previousValue = rg.value;
      }
      rg.value = "";
      if (window.MaskEngine && typeof window.MaskEngine.apply === "function") {
        window.MaskEngine.apply(rg);
      }
    } else if (!active && rg.value === "NAO POSSUI RG") {
      rg.value = "";
    } else if (!active && rg.dataset.previousValue && !rg.value) {
      rg.value = rg.dataset.previousValue;
      if (window.MaskEngine && typeof window.MaskEngine.apply === "function") {
        window.MaskEngine.apply(rg);
      }
    }
  }

  function initServidorSemRg() {
    document.querySelectorAll("[data-servidor-sem-rg-form]").forEach((form) => {
      const semRg = form.querySelector("#id_sem_rg");
      if (!semRg) return;

      if (window.CV && window.CV.stateToggle && typeof window.CV.stateToggle.init === "function") {
        window.CV.stateToggle.init(form);
      }

      applyServidorSemRgUi(form, { clearRgOnLock: false });

      const onChange = () => applyServidorSemRgUi(form, { clearRgOnLock: true });
      semRg.addEventListener("change", onChange);
      form.addEventListener("cv:state-toggle:change", onChange);
    });
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
