(function () {
  "use strict";
  var panelSaved = document.getElementById("roteiro-selector-wrapper");
  var panelNew = document.getElementById("panel-roteiro-novo");
  var radioEvent = document.getElementById("id_roteiro_modo_evento");
  var radioOwn = document.getElementById("id_roteiro_modo_proprio");
  var buttonSaved = document.getElementById("toggle-btn-salvo");
  var buttonNew = document.getElementById("toggle-btn-novo");
  if (!panelSaved || !panelNew) return;

  /* `aria-pressed` é o único estado: `v2/toggle.css` pinta o segmento escolhido
     por ele. A animação de entrada era `segment-toggle__btn--pop`, do alternador
     ANTIGO — saiu em 2026-08-20, junto com a folha que a desenhava. */
  function setPressed(button, active) {
    if (!button) return;
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }

  function syncButtons(saved) {
    setPressed(buttonSaved, saved);
    setPressed(buttonNew, !saved);
    panelNew.hidden = saved;
  }

  if (buttonSaved) {
    buttonSaved.addEventListener("click", function () {
      if (radioEvent && !radioEvent.disabled) {
        radioEvent.checked = true;
        radioEvent.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  }
  if (buttonNew) {
    buttonNew.addEventListener("click", function () {
      if (radioOwn) {
        radioOwn.checked = true;
        radioOwn.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  }
  new MutationObserver(function () {
    syncButtons(!panelSaved.hidden);
  }).observe(panelSaved, { attributes: true, attributeFilter: ["hidden"] });
})();
