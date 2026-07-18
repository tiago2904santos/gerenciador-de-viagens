(function () {
  "use strict";

  var activeTrigger = null;
  var BOUND = "data-delete-confirm-bound";

  function init(root) {
    var scope = root && root.querySelector ? root : document;
    var modal = scope.matches && scope.matches("[data-delete-confirm-modal]")
      ? scope
      : scope.querySelector("[data-delete-confirm-modal]");
    if (!modal || modal.getAttribute(BOUND) === "true") return false;
    modal.setAttribute(BOUND, "true");

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-delete-confirm-form]");
    var label = modal.querySelector("[data-delete-confirm-label]");
    var titleEl = modal.querySelector(".delete-confirm-modal__title");
    var defaultTitle = titleEl ? titleEl.textContent : "";

    function closeModal() {
      if (window.CV && window.CV.dialogs) window.CV.dialogs.close(modal);
      else {
        modal.hidden = true;
        document.body.classList.remove("has-delete-modal-open");
        if (activeTrigger && typeof activeTrigger.focus === "function") activeTrigger.focus();
      }
      activeTrigger = null;
    }

    function openModal(trigger) {
      var deleteUrl = trigger.getAttribute("data-delete-url");
      if (!deleteUrl || !form) return;

      activeTrigger = trigger;
      form.setAttribute("action", deleteUrl);
      if (label) {
        label.textContent = trigger.getAttribute("data-delete-label") || "este registro";
      }
      if (titleEl) {
        titleEl.textContent = trigger.getAttribute("data-delete-title") || defaultTitle;
      }
      if (window.CV && window.CV.dialogs) {
        window.CV.dialogs.open(modal, { opener: trigger, initialFocus: dialog, onRequestClose: closeModal });
      } else {
        modal.hidden = false;
        document.body.classList.add("has-delete-modal-open");
        if (dialog && typeof dialog.focus === "function") dialog.focus();
      }
    }

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-delete-modal-trigger]");
      if (trigger) {
        event.preventDefault();
        openModal(trigger);
        return;
      }

      if (!modal.hidden && event.target.closest("[data-delete-modal-cancel]")) {
        event.preventDefault();
        closeModal();
      }
    });

    document.addEventListener("keydown", function (event) {
      if ((!window.CV || !window.CV.dialogs) && !modal.hidden && event.key === "Escape") {
        closeModal();
      }
    });
    return true;
  }

  window.CV = window.CV || {};
  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("deleteConfirmModal", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
