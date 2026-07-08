(function () {
  "use strict";

  // Quando um botão de download tem `data-extra-download-url`, o clique
  // baixa o arquivo principal (via href do próprio <a>) e enfileira um
  // segundo download logo em seguida. Usado no card de evento para que o
  // botão de PDF do ofício também baixe a justificativa quando ela existe.
  document.addEventListener("click", function (event) {
    var trigger = event.target.closest ? event.target.closest("[data-extra-download-url]") : null;
    if (!trigger) return;

    var extraUrl = trigger.getAttribute("data-extra-download-url");
    if (!extraUrl) return;

    // Não chamamos preventDefault: o download principal segue pelo href.
    window.setTimeout(function () {
      var link = document.createElement("a");
      link.href = extraUrl;
      link.rel = "noopener";
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }, 400);
  });
})();
