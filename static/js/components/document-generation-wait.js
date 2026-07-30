(function () {
  "use strict";

  var root = document.querySelector("[data-document-generation-wait]");
  if (!root || !window.CV || !window.CV.http) return;
  var statusUrl = root.getAttribute("data-status-url");
  var message = root.querySelector("[data-document-generation-message]");

  function poll() {
    window.CV.http.fetchJson(statusUrl).then(function (result) {
      var data = result.data || {};
      if (result.ok && data.status === "complete" && data.result_url) {
        window.location.replace(data.result_url);
        return;
      }
      if (!result.ok || data.status === "error") {
        if (message) message.textContent = data.error || "Não foi possível gerar o documento.";
        return;
      }
      window.setTimeout(poll, data.retry_after_ms || 1000);
    }).catch(function () {
      if (message) message.textContent = "Falha ao consultar a geração. Tente novamente.";
    });
  }

  poll();
}());
