/* Fit-to-width: encolhe o texto até caber em UMA linha, e só o necessário.
 *
 * O CSS não sabe medir texto. Dá para escalar pela largura do contêiner
 * (`cqw`), e foi o que o cartão de lista usou por uma sessão inteira — mas o
 * `cqw` ignora o COMPRIMENTO do conteúdo: "3,5" e "R$ 2.658,53" recebem o mesmo
 * corpo, e a cada mudança de largura do bloco (238px → 224 → 193, no mesmo dia)
 * o cálculo estático quebrava de novo: valor em duas linhas, rota cortada com
 * "…", diária invisível.
 *
 * Aqui o corpo do CSS é o MÁXIMO. Quem não couber desce, um passo por vez, até
 * caber ou até o piso — nunca sobe além do que a folha pediu. Assim o cartão
 * continua sendo desenhado no CSS, e o JS só resolve o que o CSS não alcança.
 *
 * `ResizeObserver` porque a largura muda sem recarregar a página: filtro que
 * troca a lista, sidebar que recolhe, janela que muda de tamanho.
 */
(function () {
  "use strict";

  var SELETOR = "[data-fit-text]";
  var PISO_PADRAO = 11;   // px — abaixo disto o texto deixa de ser legível
  var PASSO = 0.5;        // px — meio pixel é o menor degrau que a Inter mostra
  var observador = null;

  function maximoDe(el) {
    /* O máximo é o corpo que a folha pediu, guardado no primeiro ajuste: depois
       de encolher, `getComputedStyle` devolveria o valor já reduzido, e o texto
       nunca voltaria a crescer quando o bloco alargasse. */
    var guardado = el.getAttribute("data-fit-text-max");
    if (guardado) return parseFloat(guardado);
    var atual = parseFloat(window.getComputedStyle(el).fontSize);
    el.setAttribute("data-fit-text-max", String(atual));
    return atual;
  }

  function pisoDe(el) {
    var declarado = parseFloat(el.getAttribute("data-fit-text-min"));
    return isNaN(declarado) ? PISO_PADRAO : declarado;
  }

  function transborda(el) {
    /* Meio pixel de tolerância: `scrollWidth` é inteiro e arredonda para cima,
       então um texto que cabe exatamente aparece como 1px maior e o laço
       encolheria sem necessidade. */
    return el.scrollWidth > el.clientWidth + 1;
  }

  function ajustar(el) {
    var maximo = maximoDe(el);
    var piso = pisoDe(el);
    el.style.fontSize = "";
    if (!transborda(el)) return;      // cabe no tamanho da folha: nada a fazer
    var corpo = maximo;
    while (corpo > piso) {
      corpo = Math.max(piso, corpo - PASSO);
      el.style.fontSize = corpo + "px";
      if (!transborda(el)) return;
    }
    /* Chegou ao piso e ainda não cabe: aí o `text-overflow` do CSS assume. É o
       caso extremo (um nome absurdamente longo), não o esperado. */
  }

  function observar(el) {
    if (!observador) return;
    if (el.getAttribute("data-fit-text-observed") === "") return;
    el.setAttribute("data-fit-text-observed", "");
    observador.observe(el);
  }

  function init(raiz) {
    var alvos = (raiz || document).querySelectorAll(SELETOR);
    Array.prototype.forEach.call(alvos, function (el) {
      ajustar(el);
      observar(el);
    });
  }

  if (typeof window.ResizeObserver === "function") {
    observador = new window.ResizeObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        ajustar(entrada.target);
      });
    });
  }

  window.CV = window.CV || {};
  window.CV.fitText = { init: init, ajustar: ajustar };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      init(document);
    });
  } else {
    init(document);
  }

  /* Fonte da web: a primeira medição sai com a fonte de fallback, que tem outra
     métrica. Sem este reajuste o texto fica um degrau menor do que precisava. */
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      init(document);
    });
  }
}());
