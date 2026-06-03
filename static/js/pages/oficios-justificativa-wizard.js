(function () {
  function onModeloJustificativaChange(select) {
    const form = select.closest("form");
    if (!form) return;
    const texto = form.querySelector("[data-justificativa-textarea='true']");
    if (!texto) return;
    const selected = select.options[select.selectedIndex];
    if (!selected || !selected.value) return;

    texto.value = (selected.dataset.textoJustificativa || "").trim();
    texto.dispatchEvent(new Event("input", { bubbles: true }));
    texto.dispatchEvent(new Event("change", { bubbles: true }));
    texto.focus();
  }

  function initModeloJustificativa() {
    const select = document.querySelector("[data-modelo-justificativa-select='true']");
    if (!select) return;
    const syncJustificativa = function () {
      onModeloJustificativaChange(select);
    };
    select.addEventListener("change", syncJustificativa);
    select.addEventListener("input", syncJustificativa);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initModeloJustificativa);
  } else {
    initModeloJustificativa();
  }
})();
