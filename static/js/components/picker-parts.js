/* NOVO-16 — fábricas de markup para pickers relacionados.

   Templates e scripts de página só fornecem dados e comportamento. A estrutura
   visual BEM do picker vive aqui e em ui/forms/related_picker.html. */
(function () {
  "use strict";

  window.CV = window.CV || {};

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  /* O MESMO ícone do modelo do v2 (`{% icone_svg "document" %}` na galeria): um
     `use` do sprite, e não um desenho próprio montado aqui.

     O que estas listas mostram é um DOCUMENTO — ofício, termo, justificativa —,
     e o glifo de rota que morava aqui dizia outra coisa: era o único ícone do
     sistema desenhado à mão dentro do JS, com `fill`/`stroke` próprios, e por
     isso a lista real nunca ficava igual à do catálogo. */
  function documentIcon() {
    var namespace = "http://www.w3.org/2000/svg";
    var svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("class", "icon");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");

    var use = document.createElementNS(namespace, "use");
    use.setAttribute("href", "#cv-icon-document");
    svg.appendChild(use);
    return svg;
  }

  function routeTitle(summary) {
    var label = String(summary.label || "").trim();
    var destination = String(summary.roteiro || summary.destino || "")
      .trim()
      .replace(/\s*->\s*/g, " → ");
    return [label, destination].filter(Boolean).join(" ");
  }

  function firstNames(summary) {
    var names = summary.servidores_nomes;
    if (!names || !names.length) {
      names = String(summary.servidores_label || "")
        .split(",")
        .map(function (name) { return name.trim(); })
        .filter(Boolean);
    }
    return names
      .map(function (name) { return String(name || "").trim().split(/\s+/)[0] || ""; })
      .filter(Boolean);
  }

  function routeMeta(summary) {
    var period = String(summary.periodo || "").trim();
    var people = firstNames(summary).join(", ");
    var plate = String(summary.viatura || "").trim();
    var model = String(summary.viatura_modelo || "").trim();
    var vehicle = [plate, model].filter(Boolean).join(" ");
    var parts = [period, people, vehicle].filter(Boolean);
    return parts.length ? parts.join(" · ") : "Sem informações disponíveis";
  }

  function createRelatedCard(config) {
    var button = el(
      "button",
      "search-picker__selected-card related-route-item" + (config.active ? " is-active" : ""),
    );
    button.type = "button";
    button.dataset[config.dataKey || "routeId"] = String(config.value);
    button.setAttribute("aria-pressed", config.active ? "true" : "false");

    var avatar = el("span", "search-picker__selected-avatar");
    avatar.setAttribute("aria-hidden", "true");
    avatar.appendChild(documentIcon());

    var main = el("div", "search-picker__selected-main");
    main.appendChild(el("span", "search-picker__selected-name", config.title || ""));
    main.appendChild(el("span", "search-picker__selected-meta related-route-period", config.meta || ""));
    button.appendChild(avatar);
    button.appendChild(main);
    return button;
  }

  function createRouteCard(summary, config) {
    var options = config || {};
    return createRelatedCard({
      active: !!options.active,
      dataKey: options.dataKey || "routeId",
      meta: options.meta !== undefined ? options.meta : routeMeta(summary),
      title: options.title !== undefined ? options.title : routeTitle(summary),
      value: summary.id,
    });
  }

  function createCompactRouteCard(config) {
    var button = el("button", "related-route-item" + (config.active ? " is-active" : ""));
    button.type = "button";
    button.dataset.routeId = String(config.value);
    button.appendChild(el("span", "related-route-title", config.title || ""));
    button.appendChild(el("span", "related-route-period", config.meta || ""));
    return button;
  }

  function createOption(config) {
    var button = el("button", "search-picker__option");
    button.type = "button";
    button.dataset.value = String(config.value);
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", config.selected ? "true" : "false");
    if (config.suggestionReason) button.dataset.suggestionReason = config.suggestionReason;

    var marker = el("span", "search-picker__option-marker");
    var body = el("div", "search-picker__option-content");
    var main = el("span", "search-picker__option-main", config.title || "");
    if (config.chip) {
      main.appendChild(el("span", config.chip.className, config.chip.label));
    }
    body.appendChild(main);
    body.appendChild(el("span", "search-picker__option-meta", config.meta || ""));
    button.appendChild(marker);
    button.appendChild(body);
    button.addEventListener("mousedown", function (event) { event.preventDefault(); });
    return button;
  }

  function createSelectedCard(config) {
    var card = el(
      "div",
      "search-picker__selected-card" + (config.extraClass ? " " + config.extraClass : ""),
    );
    card.dataset.value = String(config.value || "");

    var body = el("div", "search-picker__selected-main");
    var titleRow = el("div", "search-picker__selected-title-row");
    titleRow.appendChild(el("span", "search-picker__selected-name", config.title || ""));
    if (config.chip) {
      titleRow.appendChild(el("span", config.chip.className, config.chip.label));
    }
    body.appendChild(titleRow);
    body.appendChild(el("span", "search-picker__selected-meta", config.meta || ""));
    card.appendChild(body);

    if (config.editUrl) {
      var editRow = el("div", "search-picker__driver-control oficio-viatura-edit-row");
      var editLink = el("a", "search-picker__driver-toggle oficio-viatura-edit-link");
      editLink.href = config.editUrl;
      editLink.setAttribute("aria-label", config.editAriaLabel || "Editar item selecionado");
      editLink.appendChild(el("span", "search-picker__driver-marker"));
      editLink.appendChild(el("span", "search-picker__driver-text", config.editLabel || "Editar"));
      editRow.appendChild(editLink);
      card.appendChild(editRow);
    }

    var remove = el("button", "search-picker__remove", config.removeText || "x");
    remove.type = "button";
    remove.setAttribute("aria-label", config.removeAriaLabel || "Remover item selecionado");
    if (typeof config.onRemove === "function") remove.addEventListener("click", config.onRemove);
    card.appendChild(remove);
    return card;
  }

  window.CV.pickerParts = {
    createCompactRouteCard: createCompactRouteCard,
    createOption: createOption,
    createRelatedCard: createRelatedCard,
    createRouteCard: createRouteCard,
    createSelectedCard: createSelectedCard,
    routeMeta: routeMeta,
    routeTitle: routeTitle,
  };
})();
