/* Provador de fontes do UI Lab — troca a fonte do SISTEMA INTEIRO ao vivo.
 *
 * Amostras lado a lado não decidem tipografia: cada candidata parece boa num
 * parágrafo de exemplo. O que decide é ver a tela real — sidebar, cartões,
 * rótulos miúdos, o número grande do valor — na fonte candidata, e comparar com
 * a de hoje no mesmo enquadramento.
 *
 * Por isso o botão não muda a amostra: ele reescreve `--font-sans` no `<html>`,
 * que é de onde toda a interface tira a fonte (`base/tokens.css`). Nada é
 * gravado — recarregar volta ao padrão. É provador, não configuração.
 *
 * A pilha NÃO vem em atributo do botão: o gancho do `c-v2.button` é impresso com
 * escape, e uma pilha como `Bahnschrift, "DIN Next", sans-serif` chegava com as
 * aspas viradas em `&quot;` — o valor aplicado saía quebrado e o navegador caía
 * no fallback (medido). O motor lê a fonte da AMOSTRA ao lado, já resolvida pelo
 * próprio navegador em `getComputedStyle`, o que dispensa qualquer escape.
 */
(function () {
  "use strict";

  var TOKEN = "--font-sans";
  var TOKEN_PESO = "--weight-strong";

  function aplicar(pilha, rotulo) {
    document.documentElement.style.setProperty(TOKEN, pilha);
    var aviso = document.querySelector("[data-font-try-current]");
    if (aviso) aviso.textContent = rotulo;
    /* O fit-to-width mediu com a fonte anterior: outra família tem outra
       métrica, e sem remedir o texto fica um degrau menor (ou vaza). */
    if (window.CV && window.CV.fitText) {
      document.querySelectorAll("[data-fit-text]").forEach(function (el) {
        el.removeAttribute("data-fit-text-max");
        el.style.fontSize = "";
      });
      window.CV.fitText.init(document);
    }
  }

  function remedir() {
    if (!window.CV || !window.CV.fitText) return;
    document.querySelectorAll("[data-fit-text]").forEach(function (el) {
      el.removeAttribute("data-fit-text-max");
      el.style.fontSize = "";
    });
    window.CV.fitText.init(document);
  }

  document.addEventListener("click", function (evento) {
    /* PESO: a família resolve o desenho, o peso resolve a presença. Bahnschrift a
       700 parece leve porque o traço dela é mais fino que o da Inter no mesmo
       número — comparar famílias sem poder mexer no peso mente sobre as duas. */
    var peso = evento.target.closest("[data-font-weight-step]");
    if (peso) {
      evento.preventDefault();
      /* O número sai do RÓTULO ("Peso 900"), e não de um atributo com valor: o
         gancho do `c-v2.button` é impresso com escape, e `data-font-weight="900"`
         chegava como `&quot;900&quot;` — o seletor nunca casava e o botão não
         fazia nada. É a terceira vez que este escape morde nesta sessão. */
      var valor = (peso.textContent.match(/\d{3}/) || [])[0];
      if (!valor) return;
      document.documentElement.style.setProperty(TOKEN_PESO, valor);
      /* `--fact-weight` acompanha: o valor e o rótulo do fato têm peso próprio
         (800), e sem isto o controle mexia no título e no selo mas não na peça
         mais visível do cartão — medido, o valor ficava em 800 com o token em 900. */
      document.documentElement.style.setProperty("--fact-weight", valor);
      var alvoPeso = document.querySelector("[data-font-weight-current]");
      if (alvoPeso) alvoPeso.textContent = valor;
      remedir();
      return;
    }

    var botao = evento.target.closest("[data-font-try]");
    if (botao) {
      evento.preventDefault();
      var painel = botao.closest(".panel");
      var amostra = painel && painel.querySelector("[data-font-sample]");
      if (!amostra) return;
      var titulo = painel.querySelector(".panel__title");
      aplicar(
        window.getComputedStyle(amostra).fontFamily,
        titulo ? titulo.textContent.trim() : ""
      );
      return;
    }
    if (evento.target.closest("[data-font-try-reset]")) {
      evento.preventDefault();
      document.documentElement.style.removeProperty(TOKEN);
      document.documentElement.style.removeProperty(TOKEN_PESO);
      document.documentElement.style.removeProperty("--fact-weight");
      var aviso = document.querySelector("[data-font-try-current]");
      if (aviso) aviso.textContent = "Inter Variable (padrão do sistema)";
      var avisoPeso = document.querySelector("[data-font-weight-current]");
      if (avisoPeso) avisoPeso.textContent = "700";
      if (window.CV && window.CV.fitText) {
        document.querySelectorAll("[data-fit-text]").forEach(function (el) {
          el.removeAttribute("data-fit-text-max");
          el.style.fontSize = "";
        });
        window.CV.fitText.init(document);
      }
    }
  });
}());
