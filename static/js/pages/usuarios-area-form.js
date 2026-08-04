(function () {
  "use strict";

  /*
   * Gerenciador da área — o diálogo de vínculo atende dois gestos.
   *
   * "Vincular usuário" (header do bloco) abre o modal limpo; o lápis de cada
   * linha abre o MESMO modal com a conta e o perfil daquela linha já
   * preenchidos. São o mesmo registro do lado do servidor: a unique de
   * (usuario, area) garante um vínculo por par, então reenviar o par com outro
   * papel é edição — a view resolve isso passando o `instance`.
   *
   * Não passa por `overlay.js` porque os `simpleDialogs` de lá só sabem apontar
   * o `action` e copiar valores para inputs; aqui é preciso trocar a copy,
   * limpar o formulário entre um gesto e outro e ressincronizar os pickers.
   */

  var MODAL_ID = "vincular-usuario-modal";
  var TITULO_POR_MODO = {
    create: "Vincular usuário",
    edit: "Editar acesso",
  };

  function sincronizar(campo) {
    // O entity picker desenha uma UI própria sobre o `<select>` nativo e só se
    // redesenha quando o nativo emite `change`.
    campo.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function definirValor(form, name, valor) {
    var campo = form.querySelector('[name="' + name + '"]');
    if (!campo) return;
    campo.value = valor == null ? "" : String(valor);
    sincronizar(campo);
  }

  function aplicarModo(dialog, modo, rotulo) {
    dialog.setAttribute("data-vinculo-mode", modo);

    var titulo = dialog.querySelector("#vincular-na-area-title");
    if (titulo) titulo.textContent = TITULO_POR_MODO[modo] || TITULO_POR_MODO.create;

    Array.prototype.forEach.call(
      dialog.querySelectorAll("[data-vinculo-intro]"),
      function (trecho) {
        trecho.hidden = trecho.getAttribute("data-vinculo-intro") !== modo;
      }
    );

    var etiqueta = dialog.querySelector("[data-vinculo-edit-label]");
    if (etiqueta) etiqueta.textContent = rotulo || "este usuário";
  }

  function abrir(gatilho, modo) {
    var dialog = document.getElementById(MODAL_ID);
    if (!dialog || !window.CV || !window.CV.overlay) return;

    var form = dialog.querySelector("[data-vincular-usuario-form]");
    if (!form) return;

    var action =
      gatilho.getAttribute("data-edit-url") ||
      gatilho.getAttribute("data-vincular-url");
    if (action) form.setAttribute("action", action);

    // Zera o que a abertura anterior deixou para trás: sem isto, criar depois
    // de editar herdaria a conta da linha editada.
    form.reset();
    Array.prototype.forEach.call(form.querySelectorAll("select"), sincronizar);

    var valores = {};
    try {
      valores = JSON.parse(gatilho.getAttribute("data-edit-fields") || "{}");
    } catch (erro) {
      valores = {};
    }
    Object.keys(valores).forEach(function (name) {
      definirValor(form, name, valores[name]);
    });

    aplicarModo(dialog, modo, gatilho.getAttribute("data-edit-label"));
    window.CV.overlay.openDialog(dialog, { opener: gatilho });
  }

  function init() {
    if (document.body.dataset.vinculoModalBound === "true") return;
    if (!document.getElementById(MODAL_ID)) return;
    document.body.dataset.vinculoModalBound = "true";

    document.addEventListener("click", function (event) {
      var edicao = event.target.closest(
        '[data-row-edit-modal="' + MODAL_ID + '"]'
      );
      if (edicao) {
        event.preventDefault();
        abrir(edicao, "edit");
        return;
      }

      var criacao = event.target.closest("[data-vinculo-create]");
      if (criacao) {
        event.preventDefault();
        abrir(criacao, "create");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
