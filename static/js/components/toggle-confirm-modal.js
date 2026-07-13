(function () {
  "use strict";

  var activeTrigger = null;

  function init() {
    var modal = document.querySelector("[data-toggle-confirm-modal]");
    if (!modal) return;

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-toggle-confirm-form]");
    var title = modal.querySelector("[data-toggle-confirm-title]");
    var message = modal.querySelector("[data-toggle-confirm-message]");
    var submit = modal.querySelector("[data-toggle-confirm-submit] span");

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("has-delete-modal-open");
      if (activeTrigger && typeof activeTrigger.focus === "function") {
        activeTrigger.focus();
      }
      activeTrigger = null;
    }

    function openModal(trigger) {
      var toggleUrl = trigger.getAttribute("data-toggle-url");
      if (!toggleUrl || !form) return;

      activeTrigger = trigger;
      form.setAttribute("action", toggleUrl);
      if (title) {
        title.textContent = trigger.getAttribute("data-toggle-title") || "Confirmar ação?";
      }
      if (message) {
        message.textContent = trigger.getAttribute("data-toggle-message") || "";
      }
      if (submit) {
        submit.textContent = trigger.getAttribute("data-toggle-confirm-label") || "Confirmar";
      }
      modal.hidden = false;
      document.body.classList.add("has-delete-modal-open");
      if (dialog && typeof dialog.focus === "function") {
        dialog.focus();
      }
    }

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-toggle-modal-trigger]");
      if (trigger) {
        event.preventDefault();
        openModal(trigger);
        return;
      }

      if (!modal.hidden && event.target.closest("[data-toggle-modal-cancel]")) {
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
