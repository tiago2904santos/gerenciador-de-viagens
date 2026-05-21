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

  function getOutraInstituicaoValue(wrapper) {
    return (wrapper && wrapper.getAttribute("data-oficio-custeio-outra-value")) || "OUTRA_INSTITUICAO";
  }

  function shouldShowCusteioObservacao(value, outraValue) {
    return (value || "").toUpperCase() === (outraValue || "OUTRA_INSTITUICAO").toUpperCase();
  }

  function updateCusteioObservacaoVisibility(select, wrapper, outraValue) {
    const visible = shouldShowCusteioObservacao(select.value, outraValue);
    wrapper.classList.toggle("form-field--hidden", !visible);
  }

  function initCusteioObservacao() {
    const select =
      document.querySelector("[data-oficio-custeio-field]") ||
      document.querySelector("select[name='custeio']");
    const wrapper =
      document.querySelector("[data-oficio-instituicao-field]") ||
      document.querySelector("[data-custeio-observacao-wrapper]");
    if (!select || !wrapper) return;
    const outraValue = getOutraInstituicaoValue(wrapper);
    select.addEventListener("change", function () {
      updateCusteioObservacaoVisibility(select, wrapper, outraValue);
    });
    updateCusteioObservacaoVisibility(select, wrapper, outraValue);
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
