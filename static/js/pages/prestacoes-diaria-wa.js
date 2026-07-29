/* Aviso de liberação de diárias por WhatsApp — extraído do script inline do
   prestacao_list_card.html. Delegação no document (sobrevive ao swap do
   live-search); o guard evita bind duplicado. */
(function () {
  "use strict";

  if (window.__prestDiariaWaBound) return;
  window.__prestDiariaWaBound = true;

  // Os itens do menu (Enviar WhatsApp/Business/Copiar) ficam dentro de
  // .cv-action-menu, que o action-menu.js move para <body> ao abrir — por
  // isso não dá pra usar closest() a partir do item para achar a linha do
  // servidor; volta-se ao botão-gatilho original (que continua no lugar)
  // pelo id do menu.
  function diariaWaTrigger(el) {
    var menu = el.closest(".cv-action-menu");
    if (!menu) return null;
    return document.querySelector('[data-action-menu-target="' + menu.id + '"]');
  }

  function diariaDateText(value) {
    var parts = String(value || "").split("-");
    return parts.length === 3 ? (parts[2] + "/" + parts[1] + "/" + parts[0]) : "";
  }

  function diariaTodayIso() {
    var today = new Date();
    var month = String(today.getMonth() + 1).padStart(2, "0");
    var day = String(today.getDate()).padStart(2, "0");
    return today.getFullYear() + "-" + month + "-" + day;
  }

  // Valida solicitação/período e monta a mensagem; retorna null (já focando o
  // campo pendente) se faltar algo — usado tanto pelo envio quanto pela cópia.
  function diariaWaContext(el) {
    var trigger = diariaWaTrigger(el);
    if (!trigger) return null;
    var row = trigger.closest(".oficio-lc__traveller");
    var numInput = row ? row.querySelector('input[name$="-numero_solicitacao"]') : null;
    var liberacaoInput = row ? row.querySelector('input[name$="-data_liberacao_diarias"]') : null;
    var prazoInput = row ? row.querySelector('input[name$="-prazo_limite_saque"]') : null;
    var rangeTrigger = row ? row.querySelector(".oficio-lc__saque-range-picker [data-cv-date-picker-trigger]") : null;

    if (numInput && !numInput.value.trim()) {
      numInput.focus();
      numInput.setCustomValidity("Preencha o número da solicitação antes de enviar o aviso.");
      numInput.reportValidity();
      numInput.setCustomValidity("");
      return null;
    }
    if (!liberacaoInput || !liberacaoInput.value) {
      if (rangeTrigger) rangeTrigger.focus();
      window.CV.feedback.alert("Informe a data de liberação antes de enviar o aviso.");
      return null;
    }
    if (prazoInput && !prazoInput.value) {
      if (rangeTrigger) rangeTrigger.focus();
      window.CV.feedback.alert("Informe o prazo limite para saque antes de enviar o aviso.");
      return null;
    }
    if (liberacaoInput.value > diariaTodayIso()) {
      if (rangeTrigger) rangeTrigger.focus();
      window.CV.feedback.alert(
        "O aviso só poderá ser enviado a partir de " +
        diariaDateText(liberacaoInput.value) +
        ", data de liberação das diárias."
      );
      return null;
    }

    var liberacaoTexto = diariaDateText(liberacaoInput.value);
    var prazoTexto = diariaDateText(prazoInput.value);

    // Emojis/marcadores via código de caractere — evita depender da
    // codificação com que o arquivo acaba sendo salvo/lido.
    var EMOJI_LIBERACAO = String.fromCharCode(0xD83D, 0xDCE2); // megafone
    var EMOJI_PRAZO = String.fromCharCode(0x23F3); // ampulheta
    var EMOJI_AVISO = String.fromCharCode(0x26A0, 0xFE0F); // alerta
    var BULLET = String.fromCharCode(0x2022); // marcador de lista (evita colidir com o *negrito* do WhatsApp)

    var oficioNum = trigger.dataset.waOficio || "";
    var unidade = (trigger.dataset.waUnidade || "").trim();
    var evento = trigger.dataset.waEvento || "";
    var servidorNome = trigger.dataset.waServidor || "";
    var diariaValor = trigger.dataset.waDiaria || "";
    var oficioRef = "Ofício nº *" + oficioNum + "*" + (unidade ? " (" + unidade + ")" : "");

    var msg = EMOJI_LIBERACAO + " *LIBERAÇÃO DE DIÁRIAS*\n" +
      "Comunicamos que, referente ao " + oficioRef +
      ", as diárias relativas ao evento de *" + evento + "* estão liberadas para Transferência ou Saque.\n\n" +
      BULLET + " Nome: *" + servidorNome + "*\n" +
      BULLET + " Valor: *" + diariaValor + "*\n" +
      BULLET + " Data de liberação: *" + liberacaoTexto + "*\n" +
      EMOJI_PRAZO + " Prazo limite para saque: *" + prazoTexto + "* (PRAZO IMPRORROGÁVEL)\n" +
      EMOJI_AVISO + " Aviso importante: O saque das diárias não fica disponível no mesmo dia do desbloqueio do cartão. Programe-se com antecedência!";

    return { msg: msg, phone: (trigger.dataset.waPhone || "").replace(/\D/g, "") };
  }

  document.addEventListener("click", function (e) {
    var sendBtn = e.target.closest("[data-diaria-wa-send]");
    var copyBtn = e.target.closest("[data-diaria-wa-copy]");
    var el = sendBtn || copyBtn;
    if (!el) return;
    e.preventDefault();

    var ctx = diariaWaContext(el);
    if (!ctx) return;

    if (copyBtn) {
      var label = copyBtn.querySelector("strong");
      var restore = label ? label.textContent : "";
      var marcarCopiado = function () {
        if (!label) return;
        label.textContent = "Copiado!";
        setTimeout(function () { label.textContent = restore; }, 1500);
      };
      if (navigator.clipboard) {
        navigator.clipboard.writeText(ctx.msg).then(marcarCopiado, function () {
          window.CV.feedback.alert("Não foi possível copiar automaticamente. Copie a mensagem manualmente.");
        });
      } else {
        window.CV.feedback.alert("Não foi possível copiar automaticamente. Copie a mensagem manualmente.");
      }
      return;
    }

    if (!ctx.phone) {
      window.CV.feedback.alert("Este servidor não tem um celular válido cadastrado (DDD + 9 dígitos) para enviar o aviso por WhatsApp.");
      return;
    }
    var enc = encodeURIComponent(ctx.msg);
    // api.whatsapp.com direto (em vez de wa.me) — o redirecionamento do
    // wa.me tem relatos de corromper emojis no parâmetro "text" em alguns
    // clientes; indo direto ao endpoint final evita esse salto a mais.
    var waMe = "https://api.whatsapp.com/send?phone=" + ctx.phone + "&text=" + enc;
    var app = sendBtn.dataset.waApp === "business" ? "business" : "normal";
    if (/Android/i.test(navigator.userAgent || "")) {
      var pkg = app === "business" ? "com.whatsapp.w4b" : "com.whatsapp";
      var q = (ctx.phone ? "phone=" + ctx.phone + "&" : "") + "text=" + enc;
      window.location.href =
        "intent://send?" + q +
        "#Intent;scheme=whatsapp;package=" + pkg + ";S.browser_fallback_url=" + encodeURIComponent(waMe) + ";end";
      return;
    }
    window.open(waMe, "_blank", "noopener");
  });
})();
