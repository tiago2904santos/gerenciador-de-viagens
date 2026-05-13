(function () {
  "use strict";

  /** Evita que cliques nos links do cabeçalho alternem o estado do <details>. */
  document.querySelectorAll(".document-inline-actions--header").forEach(function (el) {
    el.addEventListener("click", function (e) {
      e.stopPropagation();
    });
  });

  function hydrateIframe(root) {
    var frame = root.querySelector(".document-inline-viewer__frame[data-src]");
    if (!frame) return;
    var src = frame.getAttribute("data-src");
    if (!src || frame.getAttribute("src")) return;
    frame.setAttribute("src", src);
  }

  document.querySelectorAll("[data-lazy-inline]").forEach(function (card) {
    card.addEventListener("toggle", function () {
      if (card.open) {
        hydrateIframe(card);
      }
    });
  });

  function bindVerifyPdfButton(btn, urlAttr) {
    btn.addEventListener("click", function () {
      var url = btn.getAttribute(urlAttr);
      if (!url) return;
      btn.disabled = true;
      fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (r) {
          return r.json().then(function (body) {
            return { okHttp: r.ok, status: r.status, body: body };
          });
        })
        .then(function (res) {
          var b = res.body || {};
          var detail = b.summary || b.detail || b.reason || "";
          if (b.ok) {
            window.alert("Assinatura válida.\n" + (detail || "Integridade confirmada."));
          } else {
            window.alert(
              "Verificação não passou (HTTP " +
                res.status +
                ").\n" +
                (detail || "Motivo não detalhado."),
            );
          }
        })
        .catch(function () {
          window.alert("Não foi possível concluir a verificação. Tente novamente.");
        })
        .finally(function () {
          btn.disabled = false;
        });
    });
  }

  document.querySelectorAll("[data-verify-artefato-url]").forEach(function (btn) {
    bindVerifyPdfButton(btn, "data-verify-artefato-url");
  });
  document.querySelectorAll("[data-verify-oficio-pdf-url]").forEach(function (btn) {
    bindVerifyPdfButton(btn, "data-verify-oficio-pdf-url");
  });
})();
