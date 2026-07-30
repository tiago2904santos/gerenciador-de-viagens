document.documentElement.dataset.appReady = "true";

/* Registro único de componentes progressivos.
 * Cada módulo publica um inicializador idempotente; este coordenador aplica os
 * contratos no DOM inicial e em conteúdo inserido por AJAX, templates ou
 * listas dinâmicas, sem acoplar páginas à ordem dos scripts. */
(function () {
  "use strict";

  window.CV = window.CV || {};
  window.CV.util = {
    debounce: function (fn, delay) {
      var timer = null;
      function debounced() {
        var args = arguments;
        var context = this;
        window.clearTimeout(timer);
        timer = window.setTimeout(function () {
          timer = null;
          fn.apply(context, args);
        }, delay);
      }
      debounced.cancel = function () {
        window.clearTimeout(timer);
        timer = null;
      };
      return debounced;
    },
    escapeHtml: function (value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    },
    normalize: function (value) {
      return String(value || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase();
    },
  };

  var enhancers = new Map();
  var pendingRoots = new Set();
  var flushScheduled = false;
  var observer = null;

  function safelyEnhance(name, entry, root) {
    try {
      entry.init(root || document);
    } catch (error) {
      document.dispatchEvent(new CustomEvent("cv:enhancer-error", {
        detail: { name: name, message: error.message },
      }));
    }
  }

  function enhance(root) {
    enhancers.forEach(function (entry, name) {
      safelyEnhance(name, entry, root || document);
    });
  }

  function safelyDestroy(name, entry, root) {
    if (typeof entry.destroy !== "function") return;
    try {
      entry.destroy(root);
    } catch (error) {
      document.dispatchEvent(new CustomEvent("cv:enhancer-error", {
        detail: { name: name, phase: "destroy", message: error.message },
      }));
    }
  }

  function destroy(root) {
    if (!root || (root.nodeType !== 1 && root.nodeType !== 9)) return;
    pendingRoots.forEach(function (pendingRoot) {
      if (pendingRoot === root || (root.contains && root.contains(pendingRoot))) {
        pendingRoots.delete(pendingRoot);
      }
    });
    enhancers.forEach(function (entry, name) {
      safelyDestroy(name, entry, root);
    });
  }

  function flush() {
    flushScheduled = false;
    var roots = Array.from(pendingRoots);
    pendingRoots.clear();
    roots.forEach(enhance);
  }

  function schedule(root) {
    if (!root || root.nodeType !== 1) return;
    pendingRoots.add(root);
    if (flushScheduled) return;
    flushScheduled = true;
    if (typeof window.queueMicrotask === "function") window.queueMicrotask(flush);
    else window.setTimeout(flush, 0);
  }

  function register(name, initializer, destroyer) {
    if (!name || typeof initializer !== "function") return;
    var entry = { init: initializer, destroy: destroyer };
    enhancers.set(name, entry);
    if (document.readyState !== "loading") safelyEnhance(name, entry, document);
  }

  function start() {
    if (observer || !document.documentElement) return;
    enhance(document);
    if (typeof MutationObserver !== "function") return;
    observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (mutation) {
        Array.prototype.forEach.call(mutation.removedNodes, destroy);
        Array.prototype.forEach.call(mutation.addedNodes, schedule);
      });
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
  }

  window.CV.registerEnhancer = register;
  window.CV.enhance = enhance;
  window.CV.registry = {
    destroy: destroy,
    enhance: enhance,
    register: register,
    registered: function () { return Array.from(enhancers.keys()); },
  };
  window.CV.componentRegistry = {
    destroy: destroy,
    enhance: enhance,
    register: register,
    registered: function () { return Array.from(enhancers.keys()); },
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
}());

/* Dialog accessibility shared by confirmation, upload and cancellation flows. */
(function () {
  "use strict";

  window.CV = window.CV || {};

  var dialogStates = typeof WeakMap !== "undefined" ? new WeakMap() : new Map();
  var openDialogs = [];
  var focusableSelector = [
    "a[href]",
    "button:not([disabled])",
    "input:not([disabled]):not([type='hidden'])",
    "select:not([disabled])",
    "textarea:not([disabled])",
    "[tabindex]:not([tabindex='-1'])",
  ].join(",");

  function focusableElements(container) {
    return Array.prototype.filter.call(container.querySelectorAll(focusableSelector), function (element) {
      return !element.hidden && element.getAttribute("aria-hidden") !== "true";
    });
  }

  function currentDialog() {
    return openDialogs.length ? openDialogs[openDialogs.length - 1] : null;
  }

  function open(container, options) {
    if (!container) return false;
    var config = options || {};
    var opener = config.opener || document.activeElement;
    dialogStates.set(container, { opener: opener, onRequestClose: config.onRequestClose });
    openDialogs = openDialogs.filter(function (item) { return item !== container; });
    openDialogs.push(container);
    container.hidden = false;
    document.body.classList.add("has-dialog-open", "has-delete-modal-open");

    var initialFocus = config.initialFocus;
    if (!initialFocus) {
      initialFocus = focusableElements(container)[0] || container.querySelector('[role="dialog"]');
    }
    window.requestAnimationFrame(function () {
      if (initialFocus && typeof initialFocus.focus === "function") initialFocus.focus();
    });
    container.dispatchEvent(new CustomEvent("cv:dialog:opened", { bubbles: true }));
    return true;
  }

  function close(container, options) {
    if (!container) return false;
    var config = options || {};
    var state = dialogStates.get(container) || {};
    container.hidden = true;
    openDialogs = openDialogs.filter(function (item) { return item !== container; });
    if (!openDialogs.length) {
      document.body.classList.remove("has-dialog-open", "has-delete-modal-open");
    }
    dialogStates.delete(container);
    if (config.restoreFocus !== false && state.opener && typeof state.opener.focus === "function") {
      state.opener.focus();
    }
    container.dispatchEvent(new CustomEvent("cv:dialog:closed", { bubbles: true }));
    return true;
  }

  document.addEventListener("keydown", function (event) {
    var container = currentDialog();
    if (!container) return;
    var state = dialogStates.get(container) || {};

    if (event.key === "Escape") {
      event.preventDefault();
      if (typeof state.onRequestClose === "function") state.onRequestClose();
      else close(container);
      return;
    }

    if (event.key !== "Tab") return;
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
  });

  window.CV.dialogs = {
    close: close,
    current: currentDialog,
    focusableElements: focusableElements,
    open: open,
  };
}());

/* Feedback global: substitui diálogos nativos por um fluxo assíncrono acessível. */
(function () {
  "use strict";

  window.CV = window.CV || {};

  var queue = [];
  var active = null;
  var modal = null;

  function element(tag, className, attributes) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    Object.keys(attributes || {}).forEach(function (name) {
      node.setAttribute(name, attributes[name]);
    });
    return node;
  }

  function ensureModal() {
    if (modal) return modal;

    modal = element("div", "cv-dialog cv-dialog--warning delete-confirm-modal", {
      "data-cv-feedback-modal": "",
      hidden: "",
    });
    modal.hidden = true;

    var backdrop = element("div", "cv-dialog__backdrop delete-confirm-modal__backdrop", {
      "data-cv-feedback-cancel": "",
    });
    var panel = element("section", "cv-dialog__panel cv-dialog__panel--sm delete-confirm-modal__dialog", {
      role: "dialog",
      "aria-modal": "true",
      "aria-labelledby": "cv-feedback-title",
      "aria-describedby": "cv-feedback-message",
      tabindex: "-1",
    });
    var header = element("header", "cv-dialog__header cv-dialog__header--warning");
    var heading = element("div", "cv-dialog__heading delete-confirm-modal__copy");
    var eyebrow = element("span", "cv-dialog__eyebrow delete-confirm-modal__eyebrow");
    eyebrow.textContent = "Central de Viagens";
    var title = element("h2", "cv-dialog__title delete-confirm-modal__title", { id: "cv-feedback-title" });
    var closeButton = element("button", "cv-dialog__close cv-icon-btn cv-icon-btn--sm", {
      type: "button",
      "aria-label": "Fechar",
      "data-cv-feedback-cancel": "",
    });
    closeButton.textContent = "×";
    var body = element("div", "cv-dialog__body delete-confirm-modal__body");
    var message = element("p", "cv-dialog__message delete-confirm-modal__message", {
      id: "cv-feedback-message",
    });
    var footer = element("div", "cv-dialog__footer delete-confirm-modal__actions");
    var cancelButton = element("button", "cv-btn cv-btn--secondary", {
      type: "button",
      "data-cv-feedback-cancel": "",
    });
    cancelButton.textContent = "Voltar";
    var acceptButton = element("button", "cv-btn cv-btn--secondary", {
      type: "button",
      "data-cv-feedback-accept": "",
    });

    heading.appendChild(eyebrow);
    heading.appendChild(title);
    header.appendChild(heading);
    header.appendChild(closeButton);
    body.appendChild(message);
    footer.appendChild(cancelButton);
    footer.appendChild(acceptButton);
    panel.appendChild(header);
    panel.appendChild(body);
    panel.appendChild(footer);
    modal.appendChild(backdrop);
    modal.appendChild(panel);
    document.body.appendChild(modal);

    modal.addEventListener("click", function (event) {
      if (event.target.closest("[data-cv-feedback-accept]")) finish(true);
      else if (event.target.closest("[data-cv-feedback-cancel]")) finish(false);
    });
    return modal;
  }

  function renderMessage(node, value) {
    while (node.firstChild) node.removeChild(node.firstChild);
    String(value || "").split("\n").forEach(function (line, index) {
      if (index) node.appendChild(document.createElement("br"));
      node.appendChild(document.createTextNode(line));
    });
  }

  function present() {
    if (active || !queue.length) return;
    active = queue.shift();
    var container = ensureModal();
    var isConfirm = active.kind === "confirm";
    var title = container.querySelector("#cv-feedback-title");
    var message = container.querySelector("#cv-feedback-message");
    var cancelButton = container.querySelector("[data-cv-feedback-cancel].cv-btn");
    var acceptButton = container.querySelector("[data-cv-feedback-accept]");
    var panel = container.querySelector('[role="dialog"]');

    title.textContent = active.options.title || (isConfirm ? "Confirmar ação" : "Aviso");
    renderMessage(message, active.message);
    cancelButton.hidden = !isConfirm;
    acceptButton.textContent = active.options.acceptLabel || (isConfirm ? "Confirmar" : "Entendi");

    window.CV.dialogs.open(container, {
      opener: active.options.opener || document.activeElement,
      initialFocus: isConfirm ? cancelButton : acceptButton,
      onRequestClose: function () { finish(false); },
    });
    panel.setAttribute("aria-labelledby", title.id);
  }

  function finish(accepted) {
    if (!active) return;
    var completed = active;
    active = null;
    window.CV.dialogs.close(modal);
    completed.resolve(completed.kind === "confirm" ? accepted : undefined);
    window.setTimeout(present, 0);
  }

  function enqueue(kind, message, options) {
    return new Promise(function (resolve) {
      queue.push({
        kind: kind,
        message: message,
        options: options || {},
        resolve: resolve,
      });
      present();
    });
  }

  window.CV.feedback = {
    alert: function (message, options) {
      return enqueue("alert", message, options);
    },
    confirm: function (message, options) {
      return enqueue("confirm", message, options);
    },
  };
}());

(function () {
  function getPanelId(toggle) {
    return toggle.getAttribute("aria-controls") || toggle.getAttribute("data-quick-add-toggle");
  }

  function initPanelFields(panel) {
    if (!panel) return;
    if (window.CV && window.CV.fields && typeof window.CV.fields.init === "function") {
      window.CV.fields.init(panel);
      return;
    }
    if (window.MaskEngine && typeof window.MaskEngine.scan === "function") {
      window.MaskEngine.scan(panel);
    } else if (window.CV && window.CV.masks && typeof window.CV.masks.scan === "function") {
      window.CV.masks.scan(panel);
    }
  }

  function initQuickAddToggles() {
    var toggles = Array.prototype.slice.call(document.querySelectorAll("[data-quick-add-toggle]"));

    toggles.forEach(function (toggle) {
      var panelId = getPanelId(toggle);
      var panel = panelId ? document.getElementById(panelId) : null;

      if (!panel) {
        return;
      }

      var closeButtons = Array.prototype.slice.call(panel.querySelectorAll("[data-quick-add-close]"));
      var hideTimer = null;

      function resetToCreateMode() {
        var createAction = panel.getAttribute("data-create-action");
        if (createAction) {
          panel.action = createAction;
        }
        Array.prototype.slice.call(
          panel.querySelectorAll("input:not([type=hidden]), select, textarea")
        ).forEach(function (input) {
          if (input.type === "checkbox" || input.type === "radio") {
            input.checked = false;
          } else {
            input.value = "";
          }
        });
        delete panel.dataset.editMode;
      }

      function finishHide() {
        panel.hidden = true;
        panel.removeEventListener("transitionend", finishHide);
      }

      function openPanel() {
        if (hideTimer) {
          window.clearTimeout(hideTimer);
          hideTimer = null;
        }

        panel.hidden = false;
        window.requestAnimationFrame(function () {
          panel.classList.add("is-open");
          initPanelFields(panel);
        });
        toggle.setAttribute("aria-expanded", "true");
        toggle.classList.add("is-active");
      }

      function closePanel() {
        toggle.setAttribute("aria-expanded", "false");
        toggle.classList.remove("is-active");
        panel.classList.remove("is-open");
        panel.addEventListener("transitionend", finishHide);
        hideTimer = window.setTimeout(finishHide, 280);
        resetToCreateMode();
      }

      if (toggle.getAttribute("aria-expanded") === "true") {
        openPanel();
      }

      function submitPanel() {
        if (typeof panel.requestSubmit === "function") {
          panel.requestSubmit();
        } else {
          panel.submit();
        }
      }

      toggle.addEventListener("click", function () {
        if (toggle.getAttribute("aria-expanded") !== "true") {
          openPanel();
          return;
        }
        // Painel aberto: no modo compacto o botão de rodapé salva quando há
        // valor preenchido e apenas recolhe quando está vazio.
        if (toggle.hasAttribute("data-quick-add-submit-when-open")) {
          var field = panel.querySelector("input:not([type=hidden]), select, textarea");
          var filled = field && String(field.value || "").trim() !== "";
          if (filled) {
            submitPanel();
          } else {
            closePanel();
          }
          return;
        }
        closePanel();
      });

      closeButtons.forEach(function (button) {
        button.addEventListener("click", closePanel);
      });

      if (toggle.hasAttribute("data-quick-add-submit-when-open")) {
        var labelEl = toggle.querySelector(".quick-add-footer-button__label");
        var originalLabel = labelEl ? labelEl.textContent : null;
        var saveLabel = toggle.getAttribute("data-quick-add-save-label") || "Salvar";

        function updateToggleState() {
          var field = panel.querySelector("input:not([type=hidden]), select, textarea");
          var filled = field && String(field.value || "").trim() !== "";
          toggle.classList.toggle("is-filled", filled);
          if (labelEl) labelEl.textContent = filled ? saveLabel : originalLabel;
        }

        panel.addEventListener("input", updateToggleState);

        var origClose = closePanel;
        closePanel = function () {
          origClose();
          toggle.classList.remove("is-filled");
          if (labelEl) labelEl.textContent = originalLabel;
        };
      }
    });
  }

  function initQuickEditButtons() {
    // Delegado no document: os botões costumam ser trocados via AJAX (filtro
    // de listas com live-search-submit.js), então um bind direto nos nós
    // encontrados no load perde os botões recriados depois do swap do painel.
    document.addEventListener("click", function (event) {
      var button = event.target.closest("[data-quick-edit]");
      if (!button) { return; }

      var editUrl = button.getAttribute("data-edit-url");
      var fieldsJson = button.getAttribute("data-edit-fields") || "{}";
      var fields = {};
      try { fields = JSON.parse(fieldsJson); } catch (e) {}

      var toggle = document.querySelector("[data-quick-add-toggle]");
      if (!toggle) { return; }

      var panelId = getPanelId(toggle);
      var panel = panelId ? document.getElementById(panelId) : null;
      if (!panel) { return; }

      // Aponta o form para a URL de edição
      if (editUrl) {
        panel.action = editUrl;
        panel.dataset.editMode = "true";
      }

      // Preenche os campos pelo name
      Object.keys(fields).forEach(function (name) {
        var inputs = panel.querySelectorAll('[name="' + name + '"]');
        var input = inputs[0];
        if (!input) { return; }
        if (inputs.length > 1 && Array.isArray(fields[name]) &&
            (input.type === "checkbox" || input.type === "radio")) {
          var checkedValues = {};
          fields[name].forEach(function (value) { checkedValues[String(value)] = true; });
          Array.prototype.forEach.call(inputs, function (choice) {
            choice.checked = Boolean(checkedValues[String(choice.value)]);
            choice.dispatchEvent(new Event("change", { bubbles: true }));
          });
          return;
        } else if (input.tagName === "SELECT" && input.multiple && Array.isArray(fields[name])) {
          var wanted = {};
          fields[name].forEach(function (value) { wanted[String(value)] = true; });
          Array.prototype.forEach.call(input.options, function (option) {
            option.selected = Boolean(wanted[String(option.value)]);
          });
        } else if (input.type === "checkbox" || input.type === "radio") {
          input.checked = Boolean(fields[name]) && fields[name] !== "false" && fields[name] !== "0";
        } else {
          input.value = fields[name];
        }
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });

      // Abre o painel
      if (toggle.getAttribute("aria-expanded") !== "true") {
        toggle.click();
      } else {
        initPanelFields(panel);
      }

      // Foca o primeiro campo editável
      var firstInput = panel.querySelector("input:not([type=hidden]), select, textarea");
      if (firstInput) {
        window.setTimeout(function () {
          initPanelFields(panel);
          firstInput.focus();
          firstInput.select();
        }, 60);
      }
    });
  }

  function initConfirmSubmitContracts() {
    var confirmedSubmissions = new WeakSet();
    var pendingConfirmations = new WeakSet();

    // Um unico ouvinte, em `submit`. Antes havia dois — um em `click` e outro em
    // `submit` — e quando o atributo estava no <form> os dois disparavam para o
    // mesmo envio: o usuario confirmava duas vezes (J-11).
    //
    // O atributo aparece nas duas posicoes no sistema: no proprio <form>
    // (perfil/Drive, reativar evento) e no <button type="submit"> (excluir
    // documento, remover evento do plano). Por isso o dono da confirmacao e
    // resolvido a partir do botao que enviou E do formulario — ficar so no
    // `form[data-confirm-submit]` tiraria a confirmacao dos botoes de excluir.
    document.addEventListener("submit", function (event) {
      var form = event.target;
      if (!form || !form.matches) return;
      if (confirmedSubmissions.has(form)) {
        confirmedSubmissions.delete(form);
        return;
      }

      // `submitter` diz qual botao enviou; activeElement cobre navegadores
      // antigos que ainda nao o expoem.
      var submitter = event.submitter || document.activeElement;
      var holder = null;
      if (submitter && submitter.closest) {
        holder = submitter.closest("[data-confirm-submit]");
      }
      if (!holder && form.matches("[data-confirm-submit]")) {
        holder = form;
      }
      if (!holder) return;

      var message = holder.getAttribute("data-confirm-message") || "Confirmar esta ação?";
      event.preventDefault();
      if (pendingConfirmations.has(form)) return;
      pendingConfirmations.add(form);

      window.CV.feedback.confirm(message, { opener: submitter }).then(function (accepted) {
        pendingConfirmations.delete(form);
        if (!accepted) return;
        confirmedSubmissions.add(form);
        if (typeof form.requestSubmit === "function") {
          if (submitter) form.requestSubmit(submitter);
          else form.requestSubmit();
        } else form.submit();
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initQuickAddToggles();
      initQuickEditButtons();
      initConfirmSubmitContracts();
    });
  } else {
    initQuickAddToggles();
    initQuickEditButtons();
    initConfirmSubmitContracts();
  }
}());
