(function () {
  "use strict";

  function initUsuarioQuickAdd() {
    var root = document.querySelector("[data-usuario-quick-add]");
    var panel = root ? root.closest("form.cv-inline-create__panel") : null;
    var toggle = document.querySelector(
      ".usuarios-page .cv-inline-create__toggle[data-inline-create-toggle][aria-controls='quick-add-usuario']"
    );
    if (!root || !panel || !toggle) return;
    if (toggle.dataset.usuarioSaveToggleReady === "true") return;
    toggle.dataset.usuarioSaveToggleReady = "true";

    var labelEl = toggle.querySelector(".cv-inline-create__toggle-label");
    var idleLabel =
      toggle.getAttribute("data-inline-create-idle-label") ||
      (labelEl ? labelEl.textContent.trim() : "Cadastrar usuário");
    var createLabel =
      toggle.getAttribute("data-inline-create-save-label") || "Criar usuário";
    var editLabel = "Salvar usuário";
    var createOnlyBlocks = Array.prototype.slice.call(
      panel.querySelectorAll("[data-usuario-qa-create-only]")
    );

    function fieldValue(name) {
      var field = panel.querySelector('[name="' + name + '"]');
      if (!field) return "";
      return String(field.value || "").trim();
    }

    function isEditMode() {
      return panel.dataset.editMode === "true";
    }

    function syncCreateOnlyBlocks() {
      var editing = isEditMode();
      createOnlyBlocks.forEach(function (block) {
        block.hidden = editing;
      });
    }

    function currentSaveLabel() {
      return isEditMode() ? editLabel : createLabel;
    }

    function isReady() {
      var base =
        fieldValue("usuario-username") &&
        fieldValue("usuario-email") &&
        fieldValue("usuario-nome_completo");
      if (!base) return false;
      if (isEditMode()) return true;
      return Boolean(
        fieldValue("usuario-password1") &&
          fieldValue("usuario-password2") &&
          fieldValue("usuario-area") &&
          fieldValue("usuario-papel")
      );
    }

    bindReadyToggle(
      toggle,
      panel,
      labelEl,
      idleLabel,
      currentSaveLabel,
      isReady,
      "usuario-quick-add",
      syncCreateOnlyBlocks
    );
  }

  function initAreaQuickAdd() {
    var root = document.querySelector("[data-area-quick-add]");
    var panel = root ? root.closest("form.cv-inline-create__panel") : null;
    var toggle = document.querySelector(
      ".usuarios-page .cv-inline-create__toggle[data-inline-create-toggle][aria-controls='quick-add-area']"
    );
    if (!root || !panel || !toggle) return;
    if (toggle.dataset.areaSaveToggleReady === "true") return;
    toggle.dataset.areaSaveToggleReady = "true";

    var labelEl = toggle.querySelector(".cv-inline-create__toggle-label");
    var idleLabel =
      toggle.getAttribute("data-inline-create-idle-label") ||
      (labelEl ? labelEl.textContent.trim() : "Cadastrar área");
    var saveLabel =
      toggle.getAttribute("data-inline-create-save-label") || "Criar área";

    function fieldValue(name) {
      var field = panel.querySelector('[name="' + name + '"]');
      if (!field) return "";
      return String(field.value || "").trim();
    }

    function isReady() {
      return Boolean(fieldValue("area-nome") && fieldValue("area-sigla"));
    }

    bindReadyToggle(
      toggle,
      panel,
      labelEl,
      idleLabel,
      function () {
        return saveLabel;
      },
      isReady,
      "area-quick-add"
    );
  }

  function bindReadyToggle(
    toggle,
    panel,
    labelEl,
    idleLabel,
    saveLabelFn,
    isReady,
    prefix,
    onSync
  ) {
    var readyClass = prefix + "__toggle--ready";
    var changingClass = prefix + "__toggle--changing";

    function syncToggle() {
      if (typeof onSync === "function") onSync();
      var ready = isReady();
      var saveLabel = saveLabelFn();
      var nextLabel = ready ? saveLabel : idleLabel;
      var labelChanged = labelEl && labelEl.textContent !== nextLabel;

      toggle.classList.toggle("is-filled", ready);
      toggle.classList.toggle(readyClass, ready);
      toggle.setAttribute("aria-label", nextLabel);

      if (!labelChanged || !labelEl) return;

      toggle.classList.add(changingClass);
      window.setTimeout(function () {
        labelEl.textContent = nextLabel;
        window.requestAnimationFrame(function () {
          toggle.classList.remove(changingClass);
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
    document.addEventListener("click", function (event) {
      if (!event.target.closest("[data-quick-edit]")) return;
      window.setTimeout(syncToggle, 80);
    });
    toggle.addEventListener(
      "click",
      function (event) {
        if (toggle.getAttribute("aria-expanded") !== "true") return;
        // Aberto: formulário completo → salva; incompleto → fecha (toggle).
        event.preventDefault();
        event.stopImmediatePropagation();
        if (isReady()) {
          submitPanel();
          return;
        }
        toggle.setAttribute("aria-expanded", "false");
        toggle.classList.remove("is-active", "is-filled", readyClass);
        if (labelEl) labelEl.textContent = idleLabel;
        toggle.setAttribute("aria-label", idleLabel);
        panel.classList.remove("is-open");
        window.setTimeout(function () {
          panel.hidden = true;
          var createAction = panel.getAttribute("data-create-action");
          if (createAction) panel.action = createAction;
          Array.prototype.slice
            .call(panel.querySelectorAll("input:not([type=hidden]), select, textarea"))
            .forEach(function (input) {
              if (input.type === "checkbox" || input.type === "radio") {
                input.checked = false;
              } else {
                input.value = "";
              }
            });
          delete panel.dataset.editMode;
          syncToggle();
        }, 280);
      },
      true
    );
    toggle.addEventListener("click", function () {
      window.setTimeout(syncToggle, 0);
    });
    syncToggle();
  }

  function init() {
    initUsuarioQuickAdd();
    initAreaQuickAdd();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
