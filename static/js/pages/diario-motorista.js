// Troca de motorista / viatura do diário.
// - Cada "picker" (motorista/viatura) mostra o grupo de campos conforme a opção
//   escolhida e marca o card selecionado (.is-selected — fallback do :has()).
// - Ao escolher um ofício no select de prefill, preenche motorista + viatura a
//   partir dos dados embutidos (data-oficios), disparando eventos para as máscaras.
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

    function aplicar() {
      var modo = modoAtual();
      radios.forEach(function (radio) {
        var card = radio.closest(".dmv-option");
        if (card) {
          card.classList.toggle("is-selected", radio.checked);
        }
      });
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

  // ── Auto-preenchimento a partir de um ofício existente ──
  var oficios = [];
  try {
    oficios = JSON.parse(form.getAttribute("data-oficios") || "[]");
  } catch (e) {
    oficios = [];
  }
  var porId = {};
  oficios.forEach(function (o) {
    porId[String(o.id)] = o;
  });

  function setValor(name, value) {
    var el = form.querySelector('[name="' + name + '"]');
    if (!el) {
      return;
    }
    el.value = value == null ? "" : value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function marcarRadio(name, value) {
    var el = form.querySelector('input[name="' + name + '"][value="' + value + '"]');
    if (el) {
      el.checked = true;
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  var prefill = form.querySelector("[data-oficio-prefill]");
  if (prefill) {
    prefill.addEventListener("change", function () {
      var dados = porId[prefill.value];
      if (!dados) {
        return;
      }
      setValor("motorista_manual_nome", dados.motorista_nome || "");
      setValor("motorista_manual_cpf", dados.motorista_cpf || "");
      setValor("motorista_oficio_referencia", dados.numero_ano || "");
      setValor("motorista_protocolo_ref", dados.protocolo || "");

      var v = dados.viatura || {};
      if (v.modo === "BANCO" && v.id) {
        marcarRadio("viatura_modo", "BANCO");
        setValor("viatura", v.id);
      } else if (v.modo === "MANUAL") {
        marcarRadio("viatura_modo", "MANUAL");
        setValor("viatura_manual_modelo", v.modelo || "");
        setValor("viatura_manual_placa", v.placa || "");
        setValor("viatura_manual_tipo", v.tipo || "");
        setValor("viatura_manual_combustivel", v.combustivel || "");
      }
    });
  }
})();
