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

  function initQuickAddActionToggle() {
    const form = document.querySelector("[data-justificativa-quick-add]");
    const toggle = document.querySelector("[data-justificativa-action-toggle]");
    if (!form || !toggle) return;

    const texto = form.querySelector("[data-justificativa-textarea='true']");
    const label = toggle.querySelector("[data-justificativa-action-label]");
    if (!texto || !label) return;

    const idleLabel = toggle.dataset.idleLabel || "Cadastrar justificativa";
    const readyLabel = toggle.dataset.readyLabel || "Criar justificativa";

    function isReady() {
      return texto.value.trim().length > 0;
    }

    function syncToggle() {
      const ready = isReady();
      const nextLabel = ready ? readyLabel : idleLabel;
      const labelChanged = label.textContent !== nextLabel;

      toggle.classList.toggle("justificativa-quick-add__toggle--ready", ready);
      toggle.setAttribute("aria-label", nextLabel);

      if (!labelChanged) return;

      toggle.classList.add("justificativa-quick-add__toggle--changing");
      window.setTimeout(function () {
        label.textContent = nextLabel;
        window.requestAnimationFrame(function () {
          toggle.classList.remove("justificativa-quick-add__toggle--changing");
        });
      }, 120);
    }

    texto.addEventListener("input", syncToggle);
    texto.addEventListener("change", syncToggle);
    toggle.addEventListener(
      "click",
      function (event) {
        if (!isReady()) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          form.submit();
        }
      },
      true,
    );
    syncToggle();
  }

  function initJustificativaPage() {
    initModeloJustificativa();
    initQuickAddActionToggle();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initJustificativaPage);
  } else {
    initJustificativaPage();
  }
})();
