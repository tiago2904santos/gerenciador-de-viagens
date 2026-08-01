(function () {
  "use strict";

  /* Mesmo renderer de cards do termos-form.js (Ofício vinculado). */
  var ROUTE_AVATAR_ICON =
    '<svg class="cv-icon related-route-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none">' +
      '<circle cx="6" cy="19" r="2.5" fill="currentColor"></circle>' +
      '<circle cx="18" cy="5" r="2.5" fill="currentColor"></circle>' +
      '<path d="M8.2 18.2h6.1a3.3 3.3 0 0 0 0-6.6H9.7a3.3 3.3 0 0 1 0-6.6h6.1" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" fill="none"></path>' +
    '</svg>';

  function routeCardTitle(summary) {
    var label = String(summary.label || "").trim();
    var destino = String(summary.roteiro || summary.destino || "")
      .trim()
      .replace(/\s*->\s*/g, " \u2192 ");
    return [label, destino].filter(Boolean).join(" ");
  }

  function firstNames(summary) {
    var nomes = summary.servidores_nomes;
    if (!nomes || !nomes.length) {
      nomes = String(summary.servidores_label || "")
        .split(",")
        .map(function (nome) { return nome.trim(); })
        .filter(Boolean);
    }
    return nomes
      .map(function (nome) { return String(nome || "").trim().split(/\s+/)[0] || ""; })
      .filter(Boolean);
  }

  function viaturaLabel(summary) {
    var placa = String(summary.viatura || "").trim();
    var modelo = String(summary.viatura_modelo || "").trim();
    return [placa, modelo].filter(Boolean).join(" ");
  }

  function routeCardMeta(summary) {
    var periodo = String(summary.periodo || "").trim();
    var servidores = firstNames(summary).join(", ");
    var viatura = viaturaLabel(summary);
    var parts = [periodo, servidores, viatura].filter(Boolean);
    return parts.length ? parts.join(" \u00b7 ") : "Sem informa\u00e7\u00f5es dispon\u00edveis";
  }

  function readSummaries() {
    return window.CV.documentSource.read("justificativas-oficios-summary");
  }

  function selectedIds(select) {
    return Array.from(select.options)
      .filter(function (opt) { return opt.selected && opt.value; })
      .map(function (opt) { return String(opt.value); });
  }

  function setSelectedIds(select, ids) {
    var idSet = new Set(ids.map(String));
    Array.from(select.options).forEach(function (opt) {
      opt.selected = idSet.has(String(opt.value));
    });
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function syncOficioPicker(root) {
    var form = root.closest("form") || root;
    var select = form.querySelector("select[name='oficios']");
    var search = form.querySelector("#id_oficio_busca");
    var list = form.querySelector("#termo-oficio-lista");
    if (!select || !search || !list) return;
    if (list.dataset.justificativaOficioReady === "true") return;
    list.dataset.justificativaOficioReady = "true";

    var summaries = readSummaries();
    var items = Object.keys(summaries).map(function (key) {
      return summaries[key];
    });
    items.sort(function (a, b) {
      return (a.order || 0) - (b.order || 0);
    });

    function renderList(filterText) {
      var emptyEl = form.querySelector("#termo-oficio-lista-empty");
      var term = window.CV.util.normalize(filterText || "");
      var tokens = term.split(/\s+/).filter(Boolean);
      var selected = new Set(selectedIds(select));
      var filtered = items.filter(function (summary) {
        var text = window.CV.util.normalize(
          summary.search_text ||
            [summary.label, summary.numero, summary.protocolo, summary.destino, summary.periodo].join(" ")
        );
        return !tokens.length || tokens.every(function (token) {
          return text.indexOf(token) !== -1;
        });
      });

      list.innerHTML = "";
      if (!filtered.length) {
        if (emptyEl) emptyEl.hidden = false;
        return;
      }
      if (emptyEl) emptyEl.hidden = true;

      filtered.forEach(function (summary) {
        var active = selected.has(String(summary.id));
        var button = document.createElement("button");
        button.type = "button";
        button.className =
          "cv-search-picker__selected-card related-route-item" + (active ? " is-active" : "");
        button.dataset.routeId = String(summary.id);
        button.setAttribute("aria-pressed", active ? "true" : "false");

        var avatar = document.createElement("span");
        avatar.className = "cv-search-picker__selected-avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.innerHTML = ROUTE_AVATAR_ICON;

        var main = document.createElement("div");
        main.className = "cv-search-picker__selected-main";

        var name = document.createElement("span");
        name.className = "cv-search-picker__selected-name";
        name.textContent = routeCardTitle(summary);

        var meta = document.createElement("span");
        meta.className = "cv-search-picker__selected-meta related-route-period";
        meta.textContent = routeCardMeta(summary);

        main.appendChild(name);
        main.appendChild(meta);
        button.appendChild(avatar);
        button.appendChild(main);
        button.addEventListener("click", function () {
          var ids = selectedIds(select);
          var id = String(summary.id);
          var idx = ids.indexOf(id);
          if (idx >= 0) {
            ids.splice(idx, 1);
          } else {
            ids.push(id);
          }
          setSelectedIds(select, ids);
          renderList(search.value);
        });
        list.appendChild(button);
      });
    }

    search.addEventListener("input", function () {
      renderList(search.value);
    });
    select.addEventListener("change", function () {
      renderList(search.value);
    });

    renderList(search.value);
  }

  function initModeloJustificativa(scope) {
    var root = scope || document;
    var select = root.querySelector("[data-modelo-justificativa-select='true']");
    if (!select || select.dataset.justificativaModeloReady === "true") return;
    select.dataset.justificativaModeloReady = "true";
    select.addEventListener("change", function () {
      var form = select.closest("form");
      if (!form) return;
      var texto = form.querySelector("[data-justificativa-textarea='true']");
      if (!texto) return;
      var selected = select.options[select.selectedIndex];
      if (!selected || !selected.value) return;
      texto.value = (selected.dataset.textoJustificativa || "").trim();
      texto.dispatchEvent(new Event("input", { bubbles: true }));
      texto.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function init() {
    document.querySelectorAll("[data-justificativa-quick-add] .termo-oficio-picker").forEach(syncOficioPicker);
    initModeloJustificativa(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
