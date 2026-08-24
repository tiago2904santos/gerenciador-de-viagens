/* Envio do RT e do Diário de Bordo pelo WhatsApp, com os PDFs anexados de
   verdade (`NOVO-20260824-173723-37e9862b4c2a`).

   Um link de WhatsApp (`wa.me`/`api.whatsapp.com`) carrega SÓ TEXTO — não existe
   parâmetro de anexo. Quem anexa arquivo é a folha de compartilhamento do
   sistema, pela Web Share API: `navigator.share({files})` entrega os PDFs ao
   aplicativo que o operador escolher, WhatsApp normal ou Business, sem que esta
   página precise saber qual é.

   A API exige contexto seguro e só existe com arquivos no celular e em parte dos
   navegadores de desktop. Onde ela não existe não há como anexar pelo navegador:
   a queda salva os PDFs e abre a conversa com o texto pronto, e o aviso diz que
   o anexo ficou por conta do operador — em silêncio, ele mandaria a mensagem
   achando que o documento foi junto.

   Delegação no document, como o `prestacoes-diaria-wa.js`: o menu é servido sob
   demanda e trocado pelo live-search. */
(function () {
  "use strict";

  function docsTrigger(el) {
    var menu = el.closest(".action-menu");
    if (!menu) return null;
    return window.CV.overlay.triggerForMenu(menu);
  }

  function primeiroNome(nomeCompleto) {
    return String(nomeCompleto || "").trim().split(/\s+/)[0] || "";
  }

  function mensagem(trigger, temDiario) {
    var saudacao = primeiroNome(trigger.dataset.waServidor);
    var oficio = trigger.dataset.waOficio || "";
    var evento = trigger.dataset.waEvento || "";
    var documentos = temDiario
      ? "o Relatório Técnico e o Diário de Bordo"
      : "o Relatório Técnico";

    return "Olá" + (saudacao ? ", " + saudacao : "") + "! Envio em anexo " + documentos +
      " referentes ao Ofício nº *" + oficio + "*" +
      (evento ? " (" + evento + ")" : "") + ", já preenchidos.\n\n" +
      "Por favor, confira os dados, assine e me devolva o arquivo assinado.";
  }

  function abrirWhatsApp(trigger, texto) {
    var fone = (trigger.dataset.waPhone || "").replace(/\D/g, "");
    var enc = encodeURIComponent(texto);
    // api.whatsapp.com direto, pela mesma razão do aviso de liberação: o salto
    // do wa.me tem relatos de corromper emoji no parâmetro "text".
    var waMe = "https://api.whatsapp.com/send?phone=" + fone + "&text=" + enc;
    if (/Android/i.test(navigator.userAgent || "")) {
      var q = (fone ? "phone=" + fone + "&" : "") + "text=" + enc;
      window.location.href =
        "intent://send?" + q +
        "#Intent;scheme=whatsapp;package=com.whatsapp;S.browser_fallback_url=" +
        encodeURIComponent(waMe) + ";end";
      return;
    }
    window.open(waMe, "_blank", "noopener");
  }

  async function enviarDocumentos(item) {
    var trigger = docsTrigger(item);
    if (!trigger) return;

    var rtUrl = trigger.dataset.docsRtUrl || "";
    // Vazio para quem não é motorista: só ele assina o diário.
    var dbUrl = trigger.dataset.docsDbUrl || "";
    if (!rtUrl) return;

    var progresso = window.CV.documentProgress;
    var emAndamento = true;
    progresso.begin(item, {
      title: "Preparando os documentos…",
      detail: "Gerando os PDFs para enviar pelo WhatsApp.",
    });

    try {
      var baixados = [];
      var urls = dbUrl ? [rtUrl, dbUrl] : [rtUrl];
      for (var i = 0; i < urls.length; i++) {
        baixados.push(await window.CV.documentFiles.fetchFile(urls[i]));
      }
      var arquivos = baixados.map(function (doc) {
        return new File([doc.blob], doc.filename, {
          type: doc.blob.type || "application/pdf",
        });
      });

      progresso.finish(item);
      emAndamento = false;

      if (navigator.canShare && navigator.canShare({ files: arquivos })) {
        try {
          await navigator.share({ files: arquivos, text: mensagem(trigger, Boolean(dbUrl)) });
        } catch (erroShare) {
          // Fechar a folha de compartilhamento é uma decisão do operador, não
          // uma falha: `AbortError` sem tratamento acenderia o erro vermelho da
          // geração de documento por um clique em "cancelar".
          if (!erroShare || erroShare.name !== "AbortError") throw erroShare;
        }
        return;
      }

      baixados.forEach(function (doc) {
        window.CV.documentFiles.save(doc.blob, doc.filename);
      });
      abrirWhatsApp(trigger, mensagem(trigger, Boolean(dbUrl)));
      window.CV.feedback.alert(
        "Este navegador não anexa arquivos ao WhatsApp. Os PDFs foram baixados: " +
        "anexe-os à conversa que acabou de abrir."
      );
    } catch (erro) {
      if (emAndamento) {
        progresso.error(item, erro && erro.message);
      } else {
        window.CV.feedback.alert(
          (erro && erro.message) || "Não foi possível enviar os documentos."
        );
      }
    }
  }

  document.addEventListener("click", function (e) {
    var item = e.target.closest("[data-docs-wa-send]");
    if (!item) return;
    e.preventDefault();
    enviarDocumentos(item);
  });
})();
