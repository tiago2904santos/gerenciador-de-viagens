(function () {
  function onModeloMotivoChange(select) {
    const form = select.closest("form");
    if (!form) return;
    const motivo = form.querySelector("[data-motivo-textarea='true']");
    if (!motivo) return;

    const selected = select.options[select.selectedIndex];
    // Se o usuário voltou para a opção vazia, não apaga o motivo já digitado
    if (!selected || !selected.value) return;

    const texto = (selected.dataset.textoMotivo || "").trim();
    motivo.value = texto;

    // Dispara eventos para compatibilidade com outros listeners (ex.: contadores de caracteres)
    motivo.dispatchEvent(new Event("input",  { bubbles: true }));
    motivo.dispatchEvent(new Event("change", { bubbles: true }));

    // Ajusta altura ao conteúdo inserido
    motivo.style.height = "auto";
    motivo.style.height = motivo.scrollHeight + "px";

    motivo.focus();
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
    wrapper.hidden = !visible;
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
