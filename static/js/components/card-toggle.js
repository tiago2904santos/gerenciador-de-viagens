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

  function matching(root, selector) {
    const scope = root && root.querySelectorAll ? root : document;
    const matches = Array.from(scope.querySelectorAll(selector));
    if (scope.matches && scope.matches(selector)) matches.unshift(scope);
    return matches;
  }

  function initCardToggles(root) {
    matching(root, "[data-card-toggle]").forEach((toggleRoot) => {
      if (toggleRoot.dataset.cardToggleBound === "true") return;
      const input = toggleRoot.querySelector('input[type="checkbox"]');
      if (!input) return;
      toggleRoot.dataset.cardToggleBound = "true";

      syncCardToggle(toggleRoot);
      input.addEventListener("change", () => syncCardToggle(toggleRoot));
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

  function initServidorSemRg(root) {
    matching(root, "[data-servidor-sem-rg-form]").forEach((form) => {
      if (form.dataset.servidorSemRgBound === "true") return;
      const semRg = form.querySelector("#id_sem_rg");
      if (!semRg) return;
      form.dataset.servidorSemRgBound = "true";

      if (window.CV && window.CV.stateToggle && typeof window.CV.stateToggle.init === "function") {
        window.CV.stateToggle.init(form);
      }

      applyServidorSemRgUi(form, { clearRgOnLock: false });

      const onChange = () => applyServidorSemRgUi(form, { clearRgOnLock: true });
      semRg.addEventListener("change", onChange);
      form.addEventListener("cv:state-toggle:change", onChange);
    });
  }

  function init(root) {
    initCardToggles(root);
    initServidorSemRg(root);
  }

  window.CV = window.CV || {};
  window.CV.cardToggle = { init: init };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("cardToggle", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
})();
