(function () {
  "use strict";

  var activeTrigger = null;

  function init() {
    var modal = document.querySelector("[data-delete-confirm-modal]");
    if (!modal) return;

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-delete-confirm-form]");
    var label = modal.querySelector("[data-delete-confirm-label]");
    var titleEl = modal.querySelector(".delete-confirm-modal__title");
    var defaultTitle = titleEl ? titleEl.textContent : "";

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("has-delete-modal-open");
      if (activeTrigger && typeof activeTrigger.focus === "function") {
        activeTrigger.focus();
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
      modal.hidden = false;
      document.body.classList.add("has-delete-modal-open");
      if (dialog && typeof dialog.focus === "function") {
        dialog.focus();
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
