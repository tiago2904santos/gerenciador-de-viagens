/* Filtros automáticos das listagens servidas pelo Django.
 *
 * A busca espera uma pausa de 1 segundo. Depois da navegação GET, o foco e o
 * cursor voltam ao campo para que a digitação possa continuar normalmente.
 * Selects de filtro enviam o formulário; selects de navegação usam a URL já
 * preparada pelo servidor. Intervalos de data só são enviados completos.
 */
(function () {
  "use strict";

  var ATRIBUTO_ARMADO = "data-server-filter-bound";
  var PREFIXO_FOCO = "cv:server-filter:focus:";
  var ESPERA = 1000;

  function chaveDeFoco(input) {
    return PREFIXO_FOCO + window.location.pathname + ":" + (input.name || "q");
  }

  function guardarFoco(input) {
    try {
      window.sessionStorage.setItem(chaveDeFoco(input), "true");
    } catch (error) {
      /* A filtragem continua funcionando quando storage estiver bloqueado. */
    }
  }

  function restaurarFoco(input) {
    var deveRestaurar = false;
    try {
      deveRestaurar = window.sessionStorage.getItem(chaveDeFoco(input)) === "true";
      window.sessionStorage.removeItem(chaveDeFoco(input));
    } catch (error) {
      return;
    }
    if (!deveRestaurar) return;

    input.focus();
    if (typeof input.setSelectionRange === "function") {
      var fim = input.value.length;
      input.setSelectionRange(fim, fim);
    }
  }

  function enviar(form) {
    if (typeof form.requestSubmit === "function") {
      form.requestSubmit();
      return;
    }
    form.submit();
  }

  function intervaloPodeSerEnviado(input) {
    var picker = input.closest("[data-cv-date-picker]");
    if (!picker || picker.dataset.mode !== "range") return true;

    var inicio = picker.querySelector("[data-cv-date-picker-start-value]");
    var fim = picker.querySelector("[data-cv-date-picker-end-value]");
    if (!inicio || !fim) return true;
    return Boolean(inicio.value && fim.value) || (!inicio.value && !fim.value);
  }

  function init(root) {
    var escopo = root && root.querySelectorAll ? root : document;
    var formularios = escopo.querySelectorAll("[data-server-filter-form]");

    Array.prototype.forEach.call(formularios, function (form) {
      if (form.getAttribute(ATRIBUTO_ARMADO) === "true") return;
      form.setAttribute(ATRIBUTO_ARMADO, "true");

      var busca = form.querySelector("[data-server-filter-search]");
      var temporizador = null;
      var preservarFoco = false;

      function agendar(devePreservarFoco) {
        preservarFoco = preservarFoco || devePreservarFoco;
        window.clearTimeout(temporizador);
        temporizador = window.setTimeout(function () {
          if (preservarFoco && busca) guardarFoco(busca);
          enviar(form);
        }, ESPERA);
      }

      form.addEventListener("input", function (event) {
        if (event.target.matches("[data-server-filter-search]")) agendar(true);
      });

      form.addEventListener("change", function (event) {
        var controle = event.target;
        if (controle.matches("[data-server-filter-url]")) {
          window.clearTimeout(temporizador);
          window.setTimeout(function () {
            if (controle.value) window.location.assign(controle.value);
          }, ESPERA);
          return;
        }
        if (controle.matches("[data-server-filter-control]")) agendar(false);
        if (
          controle.matches("[data-cv-date-picker-start-value], [data-cv-date-picker-end-value]") &&
          intervaloPodeSerEnviado(controle)
        ) {
          agendar(false);
        }
      });

      if (busca) restaurarFoco(busca);
    });
  }

  window.CV = window.CV || {};
  window.CV.serverFilter = { init: init };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }
}());
