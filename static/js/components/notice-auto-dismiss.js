/* Avisos de página que somem sozinhos.
 *
 * As mensagens do Django ("Roteiro cadastrado com sucesso.") são confirmação de
 * algo que JÁ aconteceu: informam e deixam de ter função. Ficando na tela, elas
 * empurram o conteúdo para baixo pelo resto da visita e, na volta da navegação,
 * a pessoa relê um aviso de dois cliques atrás.
 *
 * Cinco segundos, depois somem: tempo de ler uma linha com folga, e o conteúdo
 * sobe para o lugar. A saída é animada — opacidade e altura — porque um sumiço
 * instantâneo desloca a página sem explicar por quê.
 *
 * O que NÃO some: aviso de erro. Falha exige ação, e fechar sozinho esconderia
 * a única explicação do que deu errado — quem lê devagar perderia a mensagem.
 *
 * Quem prefere menos movimento (`prefers-reduced-motion`) recebe a remoção sem
 * transição: o aviso ainda some, sem a animação.
 */
(function () {
  "use strict";

  var SELETOR = ".notice-stack .notice, .alerts .alert, .alert-stack .alert";
  var PERMANENTES = /(notice|alert)--?(danger|error|warning)\b/;
  var ESPERA = 5000; // ms na tela antes de começar a sair
  var SAIDA = 280;   // ms de animação, casado com `--ease` da folha
  var MARCA = "data-auto-dismiss-armado";

  function ehPermanente(aviso) {
    var tom = aviso.getAttribute("data-tone") || "";
    return PERMANENTES.test(aviso.className) || /^(danger|error|warning)$/.test(tom);
  }

  function menosMovimento() {
    return (
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function remover(aviso) {
    var pilha = aviso.parentElement;
    aviso.remove();
    /* A pilha vazia continuaria ocupando o vão (`gap`) e a margem de baixo: o
       conteúdo subiria menos do que o aviso media. */
    if (pilha && !pilha.querySelector(".notice, .alert")) pilha.remove();
  }

  function sair(aviso) {
    if (menosMovimento()) {
      remover(aviso);
      return;
    }

    /* A altura precisa ser um NÚMERO para animar: de `auto` para 0 o navegador
       não interpola. Medimos, fixamos, e só então zeramos — no quadro seguinte,
       senão as duas mudanças entram no mesmo cálculo de estilo e a transição
       não acontece. */
    var altura = aviso.getBoundingClientRect().height;
    aviso.style.height = altura + "px";
    aviso.style.overflow = "hidden";

    window.requestAnimationFrame(function () {
      aviso.classList.add("notice--saindo");
      aviso.style.height = "0px";
      aviso.style.marginBottom = "0px";
      aviso.style.paddingTop = "0px";
      aviso.style.paddingBottom = "0px";
      window.setTimeout(function () {
        remover(aviso);
      }, SAIDA);
    });
  }

  function init(root) {
    var escopo = root && root.querySelectorAll ? root : document;
    var avisos = escopo.querySelectorAll(SELETOR);

    Array.prototype.forEach.call(avisos, function (aviso) {
      if (aviso.getAttribute(MARCA) === "true") return;
      if (ehPermanente(aviso)) return;
      aviso.setAttribute(MARCA, "true");
      window.setTimeout(function () {
        if (aviso.isConnected) sair(aviso);
      }, ESPERA);
    });
  }

  window.CV = window.CV || {};
  window.CV.noticeAutoDismiss = { init: init };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }
}());
