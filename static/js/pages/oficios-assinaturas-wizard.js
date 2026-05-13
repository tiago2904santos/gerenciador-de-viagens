(function () {
  function showAssinaturasTab(tab) {
    var panels = document.querySelectorAll("[data-assinaturas-panel]");
    for (var i = 0; i < panels.length; i++) {
      var p = panels[i];
      p.hidden = p.getAttribute("data-assinaturas-panel") !== tab;
    }
    var btns = document.querySelectorAll("[data-assinaturas-tab]");
    for (var j = 0; j < btns.length; j++) {
      var b = btns[j];
      var k = b.getAttribute("data-assinaturas-tab") || "";
      var active = k === tab;
      b.classList.toggle("oficios-assinaturas-tabs__btn--active", active);
      b.setAttribute("aria-selected", active ? "true" : "false");
    }
    try {
      var u = new URL(window.location.href);
      u.searchParams.set("tab", tab);
      window.history.replaceState({}, "", u);
    } catch (_e) {
      /* ignore */
    }
  }

  function applyTermoOption(opt) {
    var iframe = document.getElementById("termo-iframe");
    var errEl = document.getElementById("termo-erro-msg");
    var hashO = document.getElementById("termo-hash-o");
    var hashA = document.getElementById("termo-hash-a");
    var abrir = document.getElementById("termo-abrir-aba");
    var hid = document.getElementById("termo-servidor-id-input");
    var badge = document.getElementById("termo-badge");
    var submitBtn = document.getElementById("termo-submit-btn");
    var meta = document.getElementById("termo-meta-hashes");
    if (!opt || !iframe || !hid) return;

    var erro = opt.getAttribute("data-erro") || "";
    var disp = opt.getAttribute("data-disponivel") === "1";
    var prevUrl = opt.getAttribute("data-preview-url") || "";
    var visUrl = opt.getAttribute("data-visualizar-url") || "#";
    var assinado = opt.getAttribute("data-assinado") === "1";
    var ho = opt.getAttribute("data-hash-o") || "";
    var ha = opt.getAttribute("data-hash-a") || "";

    hid.value = opt.value;

    if (errEl) {
      errEl.textContent = erro;
      errEl.hidden = !erro;
    }
    if (hashO) hashO.textContent = ho || "—";
    if (hashA) hashA.textContent = ha || "—";
    if (abrir) {
      abrir.setAttribute("href", visUrl);
      abrir.setAttribute("aria-disabled", disp && visUrl !== "#" ? "false" : "true");
    }
    if (badge) {
      badge.textContent = assinado ? "Assinado" : "Não assinado";
      badge.classList.remove("oficio-documentos-sig-badge--signed", "oficio-documentos-sig-badge--unsigned");
      badge.classList.add(assinado ? "oficio-documentos-sig-badge--signed" : "oficio-documentos-sig-badge--unsigned");
    }
    if (meta) meta.hidden = !!erro || !disp;
    if (submitBtn) submitBtn.disabled = !disp || !!erro;
    iframe.setAttribute("src", disp && prevUrl ? prevUrl : "");
  }

  function init() {
    var tabBtns = document.querySelectorAll("[data-assinaturas-tab]");
    for (var i = 0; i < tabBtns.length; i++) {
      tabBtns[i].addEventListener("click", function () {
        var t = this.getAttribute("data-assinaturas-tab") || "oficio";
        showAssinaturasTab(t);
      });
    }

    var sel = document.getElementById("termo-servidor-select");
    if (sel) {
      sel.addEventListener("change", function () {
        var idx = sel.selectedIndex;
        if (idx >= 0) applyTermoOption(sel.options[idx]);
      });
      if (sel.selectedIndex >= 0) applyTermoOption(sel.options[sel.selectedIndex]);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
