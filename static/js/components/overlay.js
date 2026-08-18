(function () {
  "use strict";

  window.CV = window.CV || {};

  var dialogStates = typeof WeakMap !== "undefined" ? new WeakMap() : new Map();
  var openDialogs = [];
  var ownerByOverlay = typeof WeakMap !== "undefined" ? new WeakMap() : new Map();
  var listenersBound = false;
  var focusableSelector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled]):not([type='hidden'])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  var simpleDialogs = [
    {
      target: "delete-confirm-modal",
      modal: "[data-delete-confirm-modal]",
      cancel: "[data-overlay-close]",
      form: "[data-delete-confirm-form]",
      action: "data-delete-url",
      label: "[data-delete-confirm-label]",
      labelAttribute: "data-delete-label",
      title: ".delete-confirm-modal__title",
      titleAttribute: "data-delete-title",
    },
    {
      target: "cancel-reason-modal",
      modal: "[data-cancel-reason-modal]",
      cancel: "[data-overlay-close]",
      form: "[data-cancel-reason-form]",
      action: "data-cancel-url",
      label: "[data-cancel-reason-label]",
      labelAttribute: "data-cancel-label",
      initialFocus: "#id-cancel-reason-motivo",
      reset: "#id-cancel-reason-motivo",
    },
    {
      target: "confirm-action-modal",
      modal: "[data-confirm-action-modal]",
      cancel: "[data-overlay-close]",
      form: "[data-confirm-action-form]",
      action: "data-confirm-action-url",
      label: "[data-confirm-action-label]",
      labelAttribute: "data-confirm-action-label-text",
    },
    {
      target: "vincular-usuario-modal",
      modal: "[data-vincular-usuario-modal]",
      cancel: "[data-overlay-close]",
      form: "[data-vincular-usuario-form]",
      action: "data-vincular-url",
      label: "[data-vincular-usuario-label]",
      labelAttribute: "data-vincular-usuario-label",
      valueFields: [
        {
          selector: "input[name='vinculo-usuario']",
          attribute: "data-vincular-usuario-id",
        },
      ],
    },
  ];

  function focusableElements(container) {
    return Array.prototype.filter.call(
      container.querySelectorAll(focusableSelector),
      function (element) {
        return !element.hidden && element.getAttribute("aria-hidden") !== "true";
      }
    );
  }

  function currentDialog() {
    return openDialogs.length ? openDialogs[openDialogs.length - 1] : null;
  }

  function openDialog(container, options) {
    if (!container) return false;
    var config = options || {};
    var opener = config.opener || document.activeElement;
    dialogStates.set(container, {
      opener: opener,
      onRequestClose: config.onRequestClose,
    });
    openDialogs = openDialogs.filter(function (item) {
      return item !== container;
    });
    openDialogs.push(container);
    /* Duas famílias de diálogo convivem: o legado é um `<div hidden>` e abre
       tirando o atributo; o do v2 é `<dialog>` nativo, e um `<dialog>` sem o
       atributo `open` continua invisível por regra de agente do usuário — tirar o
       `hidden` dele não faz nada. Foi assim que os três diálogos de ação do v2
       abriam "com sucesso" sem aparecer na tela.

       `showModal()` também traz de graça o que o caminho legado faz à mão: foco
       presso, Esc e a camada de topo. */
    if (container.tagName === "DIALOG") {
      if (!container.open && typeof container.showModal === "function") {
        container.showModal();
      }
    } else {
      container.hidden = false;
    }
    document.body.classList.add("has-dialog-open", "has-delete-modal-open");

    var initialFocus =
      config.initialFocus ||
      focusableElements(container)[0] ||
      container.querySelector('[role="dialog"]');
    window.requestAnimationFrame(function () {
      if (initialFocus && typeof initialFocus.focus === "function") {
        initialFocus.focus();
      }
    });
    container.dispatchEvent(
      new CustomEvent("cv:dialog:opened", { bubbles: true })
    );
    return true;
  }

  function closeDialog(container, options) {
    if (!container) return false;
    var config = options || {};
    var state = dialogStates.get(container) || {};
    /* Par do `showModal()`: `<dialog>` fecha por `close()`. Pôr `hidden` num
       `<dialog>` aberto não o fecha — ele fica aberto e invisível, e o Esc para de
       responder porque o navegador ainda o considera modal. */
    if (container.tagName === "DIALOG") {
      if (container.open && typeof container.close === "function") container.close();
    } else {
      container.hidden = true;
    }
    openDialogs = openDialogs.filter(function (item) {
      return item !== container;
    });
    if (!openDialogs.length) {
      document.body.classList.remove(
        "has-dialog-open",
        "has-delete-modal-open"
      );
    }
    dialogStates.delete(container);
    if (
      config.restoreFocus !== false &&
      state.opener &&
      typeof state.opener.focus === "function"
    ) {
      state.opener.focus();
    }
    container.dispatchEvent(
      new CustomEvent("cv:dialog:closed", { bubbles: true })
    );
    return true;
  }

  function rememberOwner(overlay) {
    if (ownerByOverlay.has(overlay)) return;
    ownerByOverlay.set(overlay, {
      parent: overlay.parentNode,
      nextSibling: overlay.nextSibling,
    });
  }

  function restoreOwner(overlay) {
    var owner = ownerByOverlay.get(overlay);
    if (!owner || !owner.parent) return;
    if (owner.nextSibling && owner.nextSibling.parentNode === owner.parent) {
      owner.parent.insertBefore(overlay, owner.nextSibling);
    } else {
      owner.parent.appendChild(overlay);
    }
    ownerByOverlay.delete(overlay);
  }

  function positionMenu(trigger, menu) {
    menu.style.position = "fixed";
    menu.style.top = "0px";
    menu.style.left = "0px";
    var rect = trigger.getBoundingClientRect();
    var menuRect = menu.getBoundingClientRect();
    var top = rect.top - menuRect.height - 6;
    if (top < 8) top = rect.bottom + 6;
    var left = rect.right - menuRect.width;
    if (left < 8) left = rect.left;
    menu.style.top = top + "px";
    menu.style.left = left + "px";
  }

  function triggerForMenu(menu) {
    if (!menu || !menu.id) return null;
    return document.querySelector(
      '[data-overlay-kind="menu"][data-overlay-target="' + menu.id + '"]'
    );
  }

  function closeMenu(menu) {
    if (!menu) return;
    menu.classList.remove("action-menu--open");
    menu.hidden = true;
    menu.style.removeProperty("position");
    menu.style.removeProperty("top");
    menu.style.removeProperty("left");
    var trigger = triggerForMenu(menu);
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  }

  function closeMenus() {
    document
      .querySelectorAll(".action-menu--open")
      .forEach(closeMenu);
  }

  /** Menus sob demanda (PF-04).
   *
   * A lista manda só os gatilhos; o corpo do menu vem de `data-overlay-src` no
   * primeiro clique. Um card serve todos os seus menus numa requisição só, então
   * `buscasEmVoo` guarda a promessa por URL: dois cliques rápidos em gatilhos do
   * mesmo card não viram duas viagens.
   *
   * Materializado uma vez, o menu fica no DOM. A segunda abertura é instantânea
   * e todo o caminho existente (rememberOwner, closeMenu, posicionamento) não
   * sabe que a origem mudou.
   */
  var buscasEmVoo = {};

  function materializarMenus(src) {
    if (buscasEmVoo[src]) return buscasEmVoo[src];
    if (!window.CV || !window.CV.http) {
      return Promise.reject(new Error("CV.http indisponível"));
    }
    var promessa = window.CV.http
      .fetchText(src)
      .then(function (resultado) {
        if (!resultado.ok) {
          throw new Error("HTTP " + resultado.status);
        }
        // DOMParser, e não innerHTML: o fragmento é marcação nossa, vinda do
        // servidor e já escapada pelo Django, então escapá-la de novo a
        // destruiria — mas parsear fora do documento vivo não executa script e
        // não é o padrão que o auditor de frontend proíbe.
        var doc = new DOMParser().parseFromString(resultado.data, "text/html");
        var inseridos = 0;
        Array.prototype.slice
          .call(doc.querySelectorAll(".action-menu"))
          .forEach(function (bloco) {
            if (bloco.id && document.getElementById(bloco.id)) return;
            document.body.appendChild(document.importNode(bloco, true));
            inseridos += 1;
          });
        if (!inseridos) {
          throw new Error("resposta sem menu");
        }
        return inseridos;
      })
      .catch(function (erro) {
        // Sem isto, a falha some: o usuário clica e nada acontece. Solta a
        // promessa para que o próximo clique tente de novo.
        delete buscasEmVoo[src];
        throw erro;
      });
    buscasEmVoo[src] = promessa;
    return promessa;
  }

  /** Menu de erro, para o clique nunca terminar em silêncio. */
  function menuDeFalha(id) {
    var bloco = document.createElement("div");
    bloco.className = "action-menu action-menu--rich";
    bloco.id = id;
    bloco.setAttribute("role", "menu");
    bloco.hidden = true;
    var aviso = document.createElement("p");
    aviso.className = "action-menu__erro";
    aviso.setAttribute("role", "alert");
    aviso.textContent =
      "Não foi possível carregar as ações. Verifique a conexão e tente de novo.";
    bloco.appendChild(aviso);
    document.body.appendChild(bloco);
    return bloco;
  }

  function openMenu(trigger) {
    var alvo = trigger.getAttribute("data-overlay-target");
    var src = trigger.getAttribute("data-overlay-src");
    var menu = document.getElementById(alvo);
    if (!menu && src) {
      if (trigger.getAttribute("aria-busy") === "true") return;
      trigger.setAttribute("aria-busy", "true");
      materializarMenus(src)
        .then(function () {
          trigger.removeAttribute("aria-busy");
          if (document.getElementById(alvo)) openMenu(trigger);
          else abrirMenuResolvido(trigger, menuDeFalha(alvo));
        })
        .catch(function () {
          trigger.removeAttribute("aria-busy");
          abrirMenuResolvido(trigger, menuDeFalha(alvo));
        });
      return;
    }
    if (!menu) return;
    abrirMenuResolvido(trigger, menu);
  }

  function abrirMenuResolvido(trigger, menu) {
    var wasOpen = !menu.hidden;
    closeMenus();
    if (wasOpen) return;
    rememberOwner(menu);
    if (menu.parentNode !== document.body) document.body.appendChild(menu);
    menu.hidden = false;
    menu.classList.add("action-menu--open");
    trigger.setAttribute("aria-expanded", "true");
    positionMenu(trigger, menu);
  }

  function copyThemeMarkers(anchor, menu) {
    [
      "data-travel-document-wizard-step1",
      "data-travel-document-wizard-roteiro",
      "data-travel-document-wizard-justificativa",
      "data-travel-document-wizard-documentos",
    ].forEach(function (attribute) {
      if (anchor.closest("[" + attribute + "]")) {
        menu.setAttribute(attribute, "");
      }
    });
  }

  function clearThemeMarkers(menu) {
    [
      "data-travel-document-wizard-step1",
      "data-travel-document-wizard-roteiro",
      "data-travel-document-wizard-justificativa",
      "data-travel-document-wizard-documentos",
    ].forEach(function (attribute) {
      menu.removeAttribute(attribute);
    });
  }

  function attachDismiss(options) {
    options = options || {};
    var inside = options.inside || [];
    var isOpen = typeof options.isOpen === "function"
      ? options.isOpen
      : function () { return true; };
    var onDismiss = typeof options.onDismiss === "function"
      ? options.onDismiss
      : function () {};

    function eventIsInside(event) {
      var path = event.composedPath ? event.composedPath() : null;
      return inside.some(function (node) {
        if (!node) return false;
        if (path && path.indexOf(node) !== -1) return true;
        return node === event.target ||
          (node.contains && node.contains(event.target));
      });
    }

    function onDocumentClick(event) {
      if (isOpen() && !eventIsInside(event)) {
        onDismiss("outside", event);
      }
    }

    function onDocumentKeydown(event) {
      if (event.key !== "Escape" || !isOpen()) return;
      if (
        typeof options.escapeWhen === "function" &&
        !options.escapeWhen(event)
      ) return;
      event.preventDefault();
      onDismiss("escape", event);
    }

    /* CAPTURA, não bolha: na fase de bolha qualquer componente que chame
       `stopPropagation` no caminho impede o clique de chegar ao documento, e o
       que estava aberto não fecha. Medido no editor de roteiro — o calendário
       dos trechos abre por cima do mapa, e o Leaflet interrompe a propagação
       dos cliques no próprio contêiner: clicar no mapa não fechava o
       calendário. Na captura o documento vê o clique primeiro, antes de
       qualquer um poder interrompê-lo.

       Quem legitimamente não deve fechar continua protegido: `eventIsInside`
       compara com os nós declarados em `inside`, e isso independe de fase. */
    document.addEventListener("click", onDocumentClick, true);
    document.addEventListener("keydown", onDocumentKeydown);

    return {
      destroy: function () {
        document.removeEventListener("click", onDocumentClick, true);
        document.removeEventListener("keydown", onDocumentKeydown);
      },
    };
  }

  function attachDropdown(menu, anchor) {
    if (!menu || !anchor) {
      return { open: function () {}, close: function () {}, reposition: function () {} };
    }

    function position() {
      // `position: fixed` ANTES de medir a âncora. O `open()` faz
      // `body.appendChild(menu)` com o menu ainda em fluxo: ele alonga o
      // documento, a barra de rolagem aparece e o conteúdo estreita. Medindo
      // nesse estado, a âncora vem deslocada pela largura da barra (15px
      // medidos), e ao tirar o menu do fluxo o conteúdo volta a alargar — o
      // menu fica com a medida velha, à esquerda do gatilho. Só alinhava ao
      // rolar, porque o `scroll` reexecuta esta função com o menu já fixo.
      menu.style.position = "fixed";
      var rect = anchor.getBoundingClientRect();
      menu.style.left = rect.left + "px";
      menu.style.top = rect.bottom + "px";
      menu.style.width = Math.max(rect.width, 0) + "px";
      menu.style.right = "auto";
      menu.style.minWidth = Math.max(rect.width, 0) + "px";
      menu.classList.add("floating-dropdown--active");
    }

    function open() {
      if (menu.dataset.cvFloatingActive === "true") {
        position();
        return;
      }
      rememberOwner(menu);
      copyThemeMarkers(anchor, menu);
      document.body.appendChild(menu);
      menu.dataset.cvFloatingActive = "true";
      position();
      window.addEventListener("resize", position);
      window.addEventListener("scroll", position, true);
    }

    function close() {
      if (menu.dataset.cvFloatingActive !== "true") return;
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
      menu.classList.remove("floating-dropdown--active");
      ["position", "left", "top", "width", "right", "min-width"].forEach(
        function (property) {
          menu.style.removeProperty(property);
        }
      );
      delete menu.dataset.cvFloatingActive;
      clearThemeMarkers(menu);
      restoreOwner(menu);
    }

    return { open: open, close: close, reposition: position };
  }

  function findSimpleDialog(trigger) {
    return simpleDialogs.find(function (config) {
      return trigger.getAttribute("data-overlay-target") === config.target;
    });
  }

  function closeSimple(config, modal) {
    if (config.reset) {
      var resetControl = modal.querySelector(config.reset);
      if (resetControl) resetControl.value = "";
    }
    closeDialog(modal);
  }

  function openSimple(config, trigger) {
    var modal = document.querySelector(config.modal);
    if (!modal) return;
    var form = modal.querySelector(config.form);
    var action = trigger.getAttribute(config.action);
    if (!form || !action) return;
    form.setAttribute("action", action);

    var label = modal.querySelector(config.label);
    if (label) {
      label.textContent =
        trigger.getAttribute(config.labelAttribute) || "este registro";
    }
    var title = config.title ? modal.querySelector(config.title) : null;
    if (title) {
      if (!title.dataset.overlayDefaultTitle) {
        title.dataset.overlayDefaultTitle = title.textContent;
      }
      title.textContent =
        trigger.getAttribute(config.titleAttribute) ||
        title.dataset.overlayDefaultTitle;
    }
    (config.valueFields || []).forEach(function (field) {
      var input = modal.querySelector(field.selector);
      if (!input) return;
      input.value = trigger.getAttribute(field.attribute) || "";
    });
    var initialFocus = config.initialFocus
      ? modal.querySelector(config.initialFocus)
      : modal.querySelector('[role="dialog"]');
    openDialog(modal, {
      opener: trigger,
      initialFocus: initialFocus,
      onRequestClose: function () {
        closeSimple(config, modal);
      },
    });
  }

  function onClick(event) {
    var menuTrigger = event.target.closest(
      '[data-overlay-trigger][data-overlay-kind="menu"]'
    );
    if (menuTrigger) {
      event.preventDefault();
      openMenu(menuTrigger);
      return;
    }
    if (event.target.closest(".action-menu")) {
      closeMenus();
    } else {
      closeMenus();
    }

    var simpleTrigger = event.target.closest(
      '[data-overlay-trigger][data-overlay-kind="dialog"]'
    );
    if (simpleTrigger) {
      var simpleConfig = findSimpleDialog(simpleTrigger);
      if (simpleConfig) {
        event.preventDefault();
        openSimple(simpleConfig, simpleTrigger);
        return;
      }
    }

    simpleDialogs.some(function (config) {
      var modal = document.querySelector(config.modal);
      if (
        modal &&
        !modal.hidden &&
        event.target.closest(config.cancel)
      ) {
        event.preventDefault();
        closeSimple(config, modal);
        return true;
      }
      return false;
    });
  }

  function onKeydown(event) {
    var container = currentDialog();
    if (container) {
      var state = dialogStates.get(container) || {};
      if (event.key === "Escape") {
        event.preventDefault();
        if (typeof state.onRequestClose === "function") state.onRequestClose();
        else closeDialog(container);
        return;
      }
      if (event.key === "Tab") {
        var focusable = focusableElements(container);
        if (!focusable.length) {
          event.preventDefault();
          var dialog = container.querySelector('[role="dialog"]');
          if (dialog) dialog.focus();
          return;
        }
        var first = focusable[0];
        var last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    if (event.key === "Escape") closeMenus();
  }

  function bindListeners() {
    if (listenersBound) return;
    listenersBound = true;
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKeydown);
    window.addEventListener("scroll", closeMenus, true);
    window.addEventListener("resize", closeMenus);
  }

  function menusOwnedBy(root) {
    var menus = [];
    var triggers = [];
    if (
      root.matches &&
      root.matches('[data-overlay-trigger][data-overlay-kind="menu"]')
    ) {
      triggers.push(root);
    }
    if (root.querySelectorAll) {
      triggers = triggers.concat(
        Array.prototype.slice.call(
          root.querySelectorAll(
            '[data-overlay-trigger][data-overlay-kind="menu"]'
          )
        )
      );
    }
    triggers.forEach(function (trigger) {
      var menu = document.getElementById(
        trigger.getAttribute("data-overlay-target")
      );
      if (menu && menus.indexOf(menu) === -1) menus.push(menu);
    });
    return menus;
  }

  function init() {
    bindListeners();
  }

  function destroy(root) {
    menusOwnedBy(root).forEach(function (menu) {
      closeMenu(menu);
      restoreOwner(menu);
    });
    openDialogs.slice().forEach(function (dialog) {
      if (root === dialog || (root.contains && root.contains(dialog))) {
        closeDialog(dialog, { restoreFocus: false });
      }
    });
  }

  window.CV.overlay = {
    attachDismiss: attachDismiss,
    attachDropdown: attachDropdown,
    closeDialog: closeDialog,
    closeMenus: closeMenus,
    currentDialog: currentDialog,
    destroy: destroy,
    focusableElements: focusableElements,
    init: init,
    openDialog: openDialog,
  };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("overlay", init, destroy);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
}());
