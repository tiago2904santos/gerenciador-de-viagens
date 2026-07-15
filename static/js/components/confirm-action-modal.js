(function () {
  "use strict";

  var activeTrigger = null;

  function init() {
    var modal = document.querySelector("[data-confirm-action-modal]");
    if (!modal) return;

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-confirm-action-form]");
    var label = modal.querySelector("[data-confirm-action-label]");

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("has-delete-modal-open");
      if (activeTrigger && typeof activeTrigger.focus === "function") {
        activeTrigger.focus();
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
      modal.hidden = false;
      document.body.classList.add("has-delete-modal-open");
      if (dialog && typeof dialog.focus === "function") {
        dialog.focus();
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
      if (!modal.hidden && event.key === "Escape") {
        closeModal();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
