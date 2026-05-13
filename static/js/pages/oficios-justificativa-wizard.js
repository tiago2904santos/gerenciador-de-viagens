(function () {
  function onModeloJustificativaChange(select) {
    const form = select.closest("form");
    if (!form) return;
    const texto = form.querySelector("[data-justificativa-textarea='true']");
    if (!texto || (texto.value || "").trim()) return;
    const selected = select.options[select.selectedIndex];
    if (!selected) return;
    const value = selected.dataset.textoJustificativa || "";
    if (value.trim()) {
      texto.value = value;
    }
  }

  function initModeloJustificativa() {
    const select = document.querySelector("[data-modelo-justificativa-select='true']");
    if (!select) return;
    select.addEventListener("change", function () {
      onModeloJustificativaChange(select);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initModeloJustificativa);
  } else {
    initModeloJustificativa();
  }
})();
