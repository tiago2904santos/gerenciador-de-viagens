// Troca de motorista do diário: mostra o grupo de campos conforme o modo escolhido.
// Sem JS, todos os grupos ficam visíveis e a validação é feita no servidor.
(function () {
  "use strict";

  var form = document.querySelector("[data-diario-motorista-form]");
  if (!form) {
    return;
  }

  var radios = form.querySelectorAll('input[name="motorista_modo"]');
  var groups = form.querySelectorAll("[data-motorista-group]");
  if (!radios.length || !groups.length) {
    return;
  }

  function modoSelecionado() {
    for (var i = 0; i < radios.length; i += 1) {
      if (radios[i].checked) {
        return radios[i].value;
      }
    }
    return "OFICIO";
  }

  function aplicar() {
    var modo = modoSelecionado();
    groups.forEach(function (group) {
      group.hidden = group.getAttribute("data-motorista-group") !== modo;
    });
  }

  radios.forEach(function (radio) {
    radio.addEventListener("change", aplicar);
  });

  aplicar();
})();
