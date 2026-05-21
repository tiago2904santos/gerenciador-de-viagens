(function () {
  function normalize(value) {
    return (value || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function initFilter(input) {
    if (!input || input.dataset.filterableMultiselectBound === "true") return;
    input.dataset.filterableMultiselectBound = "true";

    const targetId = input.dataset.filterableMultiselectInput;
    if (!targetId) return;
    const select = document.getElementById(targetId);
    if (!select) return;

    function apply() {
      const term = normalize(input.value);
      Array.from(select.options).forEach((option) => {
        const matches = !term || normalize(option.textContent).includes(term);
        option.hidden = !matches;
      });
    }

    input.addEventListener("input", apply);
    apply();
  }

  function init(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("input[data-filterable-multiselect-input]").forEach(initFilter);
  }

  function boot() {
    init(document);
  }

  window.CvFilterableMultiselect = { boot, init };
  window.CV = window.CV || {};
  window.CV.filterableMultiselect = window.CvFilterableMultiselect;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
