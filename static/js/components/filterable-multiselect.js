(function () {
  function normalize(value) {
    return (value || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  function initFilter(input) {
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

  function boot() {
    document.querySelectorAll("input[data-filterable-multiselect-input]").forEach(initFilter);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
