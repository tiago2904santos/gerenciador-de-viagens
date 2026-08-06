(function () {
  "use strict";

  // Espelha, na tela, a derivação que o modelo faz no save(): 15% e 30% do
  // valor de 24 horas, ROUND_HALF_UP em duas casas. É pré-visualização — o
  // valor gravado é sempre o que o servidor calcula, nunca o que veio do
  // formulário. Os campos são readonly e disabled justamente para não haver
  // caminho de entrada que contradiga o modelo.
  // Math.round arredonda .5 para cima em positivos, que é o ROUND_HALF_UP do
  // servidor. O que não dá para reproduzir aqui é o Decimal: em ponto
  // flutuante um produto pode cair logo abaixo do meio exato e descer um
  // centavo. Por isso esta função só alimenta a prévia — quem grava é o save()
  // do modelo, com Decimal.
  function formatar(valor) {
    return (Math.round(valor * 100) / 100).toFixed(2).replace(".", ",");
  }

  function atualizar(base, raiz) {
    var bruto = parseFloat(String(base.value).replace(",", "."));
    var derivados = (raiz || document).querySelectorAll("[data-diaria-derivado]");
    for (var i = 0; i < derivados.length; i += 1) {
      var campo = derivados[i];
      var fator = parseFloat(campo.getAttribute("data-diaria-derivado"));
      campo.value = isNaN(bruto) || bruto <= 0 ? "" : "R$ " + formatar(bruto * fator);
    }
  }

  function iniciar(raiz) {
    var escopo = raiz || document;
    var base = escopo.querySelector("[data-diaria-base]");
    if (!base || base.dataset.diariaLigado === "1") return;
    base.dataset.diariaLigado = "1";
    base.addEventListener("input", function () {
      atualizar(base, escopo);
    });
    atualizar(base, escopo);
  }

  // JS-02 — registra pelo mesmo nome que todo o resto usa. `CV.registry.register`
  // e `CV.registerEnhancer` são a mesma função (core/app.js), mas só o segundo
  // é visível para a catraca que exige `destroy`; pelo primeiro, o componente
  // passava despercebido. Não há `destroy`: o listener é do próprio campo e
  // morre com ele, sem nada em `document`/`window` para desfazer.
  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("diariaDerivados", iniciar);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      iniciar(document);
    });
  } else {
    iniciar(document);
  }
})();
