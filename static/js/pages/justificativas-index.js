(function () {
  "use strict";

  /* Mesmo renderer de cards do termos-form.js (Ofício vinculado). */
  var ROUTE_AVATAR_ICON =
    '<svg class="icon related-route-icon" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" focusable="false" fill="none">' +
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
          "search-picker__selected-card related-route-item" + (active ? " is-active" : "");
        button.dataset.routeId = String(summary.id);
        button.setAttribute("aria-pressed", active ? "true" : "false");

        var avatar = document.createElement("span");
        avatar.className = "search-picker__selected-avatar";
        avatar.setAttribute("aria-hidden", "true");
        avatar.innerHTML = ROUTE_AVATAR_ICON;

        var main = document.createElement("div");
        main.className = "search-picker__selected-main";

        var name = document.createElement("span");
        name.className = "search-picker__selected-name";
        name.textContent = routeCardTitle(summary);

        var meta = document.createElement("span");
        meta.className = "search-picker__selected-meta related-route-period";
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

    /* NOVO-07: os candidatos deixaram de vir todos no HTML. `items` comeca com
       o que ja esta selecionado e recebe do servidor conforme se digita. */
    window.CV.documentSearch.attach({
      select: select,
      input: search,
      onResults: function (novos) {
        novos.forEach(function (resumo) {
          var chave = String(resumo.id);
          if (summaries[chave]) return;
          summaries[chave] = resumo;
          items.push(resumo);
        });
        renderList(search.value);
      },
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

  /* Toggle: idle → dourado "Salvar rascunho" quando ofícios + texto estão ok.
     Também intercepta o clique: o handler genérico do shell só olha o 1º
     input (busca), e fecha o painel sem enviar o form. */
  function initQuickAddSaveToggle() {
    var form = document.querySelector("[data-justificativa-quick-add]");
    var panel = form ? form.closest("form.inline-create__panel") : null;
    var toggle = document.querySelector(
      ".justificativas-page .inline-create__toggle[data-inline-create-toggle]"
    );
    if (!form || !panel || !toggle) return;
    if (toggle.dataset.justificativaSaveToggleReady === "true") return;
    toggle.dataset.justificativaSaveToggleReady = "true";

    var labelEl = toggle.querySelector(".inline-create__toggle-label");
    var idleLabel =
      toggle.getAttribute("data-inline-create-idle-label") ||
      (labelEl ? labelEl.textContent.trim() : "Cadastrar justificativa");
    var saveLabel =
      toggle.getAttribute("data-inline-create-save-label") || "Salvar justificativa";
    var oficios = panel.querySelector("select[name='oficios']");
    var texto = panel.querySelector("[data-justificativa-textarea='true']");

    function isReady() {
      var hasOficio =
        oficios &&
        Array.from(oficios.options).some(function (opt) {
          return opt.selected && opt.value;
        });
      var hasTexto = texto && String(texto.value || "").trim().length > 0;
      return Boolean(hasOficio && hasTexto);
    }

    function syncToggle() {
      var ready = isReady();
      var nextLabel = ready ? saveLabel : idleLabel;
      var labelChanged = labelEl && labelEl.textContent !== nextLabel;

      toggle.classList.toggle("is-filled", ready);
      toggle.classList.toggle("justificativa-quick-add__toggle--ready", ready);
      toggle.setAttribute("aria-label", nextLabel);

      if (!labelChanged || !labelEl) return;

      toggle.classList.add("justificativa-quick-add__toggle--changing");
      window.setTimeout(function () {
        labelEl.textContent = nextLabel;
        window.requestAnimationFrame(function () {
          toggle.classList.remove("justificativa-quick-add__toggle--changing");
        });
      }, 120);
    }

    function submitPanel() {
      if (typeof panel.requestSubmit === "function") {
        panel.requestSubmit();
      } else {
        panel.submit();
      }
    }

    panel.addEventListener("input", syncToggle);
    panel.addEventListener("change", syncToggle);
    toggle.addEventListener(
      "click",
      function (event) {
        if (toggle.getAttribute("aria-expanded") !== "true") return;
        if (!isReady()) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        submitPanel();
      },
      true
    );
    toggle.addEventListener("click", function () {
      window.setTimeout(syncToggle, 0);
    });
    syncToggle();
  }

  function init() {
    document.querySelectorAll("[data-justificativa-quick-add] .termo-oficio-picker").forEach(syncOficioPicker);
    initModeloJustificativa(document);
    initQuickAddSaveToggle();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
