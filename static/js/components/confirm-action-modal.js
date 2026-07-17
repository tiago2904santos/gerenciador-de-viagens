(function () {
  "use strict";

  var activeTrigger = null;
  var BOUND = "data-confirm-action-bound";

  function init(root) {
    var scope = root && root.querySelector ? root : document;
    var modal = scope.matches && scope.matches("[data-confirm-action-modal]")
      ? scope
      : scope.querySelector("[data-confirm-action-modal]");
    if (!modal || modal.getAttribute(BOUND) === "true") return false;
    modal.setAttribute(BOUND, "true");

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-confirm-action-form]");
    var label = modal.querySelector("[data-confirm-action-label]");

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
      var actionUrl = trigger.getAttribute("data-confirm-action-url");
      if (!actionUrl || !form) return;

      activeTrigger = trigger;
      form.setAttribute("action", actionUrl);
      if (label) {
        label.textContent = trigger.getAttribute("data-confirm-action-label-text") || "este registro";
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
      var trigger = event.target.closest("[data-confirm-action-trigger]");
      if (trigger) {
        event.preventDefault();
        openModal(trigger);
        return;
      }

      if (!modal.hidden && event.target.closest("[data-confirm-action-cancel]")) {
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
    window.CV.registerEnhancer("confirmActionModal", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
