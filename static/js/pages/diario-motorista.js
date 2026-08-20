// Troca de motorista / viatura do diário.
// - Cada "picker" (motorista/viatura) mostra o grupo de campos conforme a opção
//   escolhida e marca o card selecionado (.is-selected — fallback do :has()).
// - CV.documentSource preenche motorista + viatura a partir do ofício escolhido.
// Sem JS, todos os grupos ficam visíveis e a validação é feita no servidor.
(function () {
  "use strict";

  var form = document.querySelector("[data-diario-motorista-form]");
  if (!form) {
    return;
  }

  function setupPicker(radioName, groupAttr) {
    var radios = form.querySelectorAll('input[name="' + radioName + '"]');
    if (!radios.length) {
      return;
    }
    var groups = form.querySelectorAll("[" + groupAttr + "]");

    function modoAtual() {
      for (var i = 0; i < radios.length; i += 1) {
        if (radios[i].checked) {
          return radios[i].value;
        }
      }
      return radios[0] ? radios[0].value : "";
    }

    /* Só mostrar e esconder os grupos. Marcar o cartão escolhido era coisa daqui
       até 2026-08-20 (`classList.toggle("is-selected")` no `.dmv-option`); agora
       as opções são `c-v2.choice_card`, e a folha do componente pinta o
       escolhido por `:has(input:checked)` — sem JS, e igual ao resto do
       sistema. */
    function aplicar() {
      var modo = modoAtual();
      groups.forEach(function (group) {
        group.hidden = group.getAttribute(groupAttr) !== modo;
      });
    }

    radios.forEach(function (radio) {
      radio.addEventListener("change", aplicar);
    });
    aplicar();
  }

  setupPicker("motorista_modo", "data-motorista-group");
  setupPicker("viatura_modo", "data-viatura-group");

  var prefill = form.querySelector("[data-oficio-prefill]");
  if (prefill) {
    prefill.addEventListener("change", function () {
      var source = window.CV.documentSource.selected(prefill);
      if (!source.length) return;
      window.CV.documentSource.apply(form, source, [
        { type: "value", name: "motorista_manual_nome", path: "motorista_nome", events: true, clear: true },
        { type: "value", name: "motorista_manual_cpf", path: "motorista_cpf", events: true, clear: true },
        { type: "value", name: "motorista_oficio_referencia", path: "numero_ano", events: true, clear: true },
        { type: "value", name: "motorista_protocolo_ref", path: "protocolo", events: true, clear: true },
        { type: "radio", name: "viatura_modo", path: "viatura.modo", when: { path: "viatura.modo" }, events: true },
        { type: "value", name: "viatura", path: "viatura.id", when: { path: "viatura.modo", equals: "BANCO" }, events: true },
        { type: "value", name: "viatura_manual_modelo", path: "viatura.modelo", when: { path: "viatura.modo", equals: "MANUAL" }, events: true, clear: true },
        { type: "value", name: "viatura_manual_placa", path: "viatura.placa", when: { path: "viatura.modo", equals: "MANUAL" }, events: true, clear: true },
        { type: "value", name: "viatura_manual_tipo", path: "viatura.tipo", when: { path: "viatura.modo", equals: "MANUAL" }, events: true, clear: true },
        { type: "value", name: "viatura_manual_combustivel", path: "viatura.combustivel", when: { path: "viatura.modo", equals: "MANUAL" }, events: true, clear: true },
      ]);
    });
  }
})();
