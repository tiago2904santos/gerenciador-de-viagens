document.documentElement.dataset.appReady = "true";

(function () {
  function getPanelId(toggle) {
    return toggle.getAttribute("aria-controls") || toggle.getAttribute("data-quick-add-toggle");
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

      toggle.addEventListener("click", function () {
        if (toggle.getAttribute("aria-expanded") === "true") {
          closePanel();
        } else {
          openPanel();
        }
      });

      closeButtons.forEach(function (button) {
        button.addEventListener("click", closePanel);
      });
    });
  }

  function initQuickEditButtons() {
    var buttons = Array.prototype.slice.call(document.querySelectorAll("[data-quick-edit]"));

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
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
          var input = panel.querySelector('[name="' + name + '"]');
          if (input) { input.value = fields[name]; }
        });

        // Abre o painel
        if (toggle.getAttribute("aria-expanded") !== "true") {
          toggle.click();
        }

        // Foca o primeiro campo editável
        var firstInput = panel.querySelector("input:not([type=hidden]), select, textarea");
        if (firstInput) {
          window.setTimeout(function () { firstInput.focus(); firstInput.select(); }, 60);
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initQuickAddToggles();
      initQuickEditButtons();
    });
  } else {
    initQuickAddToggles();
    initQuickEditButtons();
  }
}());
