(function () {
  "use strict";

  /** Evita que cliques nos links do cabeçalho alternem o estado do <details>.
   *
   * Exceto gatilhos que dependem de delegação no `document`
   * (action-menu.js, attach-signed-modal.js, delete-confirm-modal.js):
   * esses precisam que o clique continue borbulhando até lá.
   * action-menu.js já chama preventDefault no trigger, então o <details>
   * não alterna.
   */
  document.querySelectorAll(".document-inline-actions--header").forEach(function (el) {
    el.addEventListener("click", function (e) {
      if (
        e.target.closest(
          "[data-action-menu-trigger], [data-attach-signed-trigger], [data-delete-modal-trigger]",
        )
      ) {
        return;
      }
      e.stopPropagation();
    });
  });

  function collectTermUrls(root, attr) {
    return Array.prototype.slice
      .call(root.querySelectorAll("[" + attr + "]"))
      .map(function (el) {
        return el.getAttribute(attr);
      })
      .filter(Boolean);
  }

  function clickUrls(urls, options) {
    var opts = options || {};
    urls.forEach(function (url, index) {
      window.setTimeout(function () {
        var link = document.createElement("a");
        link.href = url;
        if (opts.newTab) {
          link.target = "_blank";
          link.rel = "noopener noreferrer";
        }
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        link.remove();
      }, index * 120);
    });
  }

  document.querySelectorAll("[data-open-all-termos]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var card = btn.closest(".document-inline-card--termos");
      if (!card) return;
      clickUrls(collectTermUrls(card, "data-termo-inline-url"), { newTab: true });
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
    // Cards que já abrem expandidos (ex.: visualizador único por página) precisam
    // ser hidratados no carregamento, pois o evento "toggle" não dispara sozinho.
    if (card.open) {
      hydrateIframe(card);
    }
  });

  function bindVerifyPdfButton(btn, urlAttr) {
    btn.addEventListener("click", function () {
      var url = btn.getAttribute(urlAttr);
      if (!url) return;
      btn.disabled = true;
      window.CV.http.fetchJson(url, { headers: { Accept: "application/json" } })
        .then(function (result) {
          return { okHttp: result.ok, status: result.status, body: result.data || {} };
        })
        .then(function (res) {
          var b = res.body || {};
          var detail = b.summary || b.detail || b.reason || "";
          if (b.ok) {
            return window.CV.feedback.alert("Assinatura válida.\n" + (detail || "Integridade confirmada."));
          } else {
            return window.CV.feedback.alert(
              "Verificação não passou (HTTP " +
                res.status +
                ").\n" +
                (detail || "Motivo não detalhado."),
            );
          }
        })
        .catch(function () {
          return window.CV.feedback.alert("Não foi possível concluir a verificação. Tente novamente.");
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

  /** Encaixa R$ + valor na largura do tile (só reduz se o CSS cqi ainda extrapolar). */
  function fitRouteValor(el) {
    if (!el) return;
    el.style.fontSize = "";
    var maxPx = parseFloat(window.getComputedStyle(el).fontSize);
    if (!isFinite(maxPx) || maxPx <= 0) return;
    var minPx = Math.min(14, maxPx);
    if (el.scrollWidth <= el.clientWidth + 0.5) return;
    var lo = minPx;
    var hi = maxPx;
    for (var i = 0; i < 12; i++) {
      var mid = (lo + hi) / 2;
      el.style.fontSize = mid + "px";
      if (el.scrollWidth <= el.clientWidth + 0.5) lo = mid;
      else hi = mid;
    }
    el.style.fontSize = lo + "px";
  }

  function fitAllRouteValores() {
    document
      .querySelectorAll(".oficio-documentos-route-section .oficio-documentos-route-diarias-valor")
      .forEach(fitRouteValor);
  }

  fitAllRouteValores();
  if (typeof ResizeObserver !== "undefined") {
    document.querySelectorAll(".oficio-documentos-route-valor-card").forEach(function (card) {
      var ro = new ResizeObserver(function () {
        fitRouteValor(card.querySelector(".oficio-documentos-route-diarias-valor"));
      });
      ro.observe(card);
    });
  }
})();
