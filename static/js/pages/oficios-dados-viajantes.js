(function () {
  function onModeloMotivoChange(select) {
    const form = select.closest("form");
    if (!form) return;
    const motivo = form.querySelector("[data-motivo-textarea='true']");
    if (!motivo || (motivo.value || "").trim()) return;
    const selected = select.options[select.selectedIndex];
    if (!selected) return;
    const texto = selected.dataset.textoMotivo || "";
    if (texto.trim()) {
      motivo.value = texto;
    }
  }

  function initModeloMotivo() {
    const select = document.querySelector("[data-modelo-motivo-select='true']");
    if (!select) return;
    select.addEventListener("change", function () {
      onModeloMotivoChange(select);
    });
  }

  function shouldShowCusteioObservacao(value) {
    return (value || "").toUpperCase() === "OUTRA_INSTITUICAO";
  }

  function updateCusteioObservacaoVisibility(select, wrapper) {
    const visible = shouldShowCusteioObservacao(select.value);
    wrapper.classList.toggle("form-field--hidden", !visible);
  }

  function initCusteioObservacao() {
    const select = document.querySelector("select[name='custeio']");
    const wrapper = document.querySelector("[data-custeio-observacao-wrapper]");
    if (!select || !wrapper) return;
    select.addEventListener("change", function () {
      updateCusteioObservacaoVisibility(select, wrapper);
    });
    updateCusteioObservacaoVisibility(select, wrapper);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initModeloMotivo();
      initCusteioObservacao();
    });
  } else {
    initModeloMotivo();
    initCusteioObservacao();
  }
})();
