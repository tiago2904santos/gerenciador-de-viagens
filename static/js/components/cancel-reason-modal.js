(function () {
  "use strict";

  var activeTrigger = null;

  function init() {
    var modal = document.querySelector("[data-cancel-reason-modal]");
    if (!modal) return;

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-cancel-reason-form]");
    var label = modal.querySelector("[data-cancel-reason-label]");
    var textarea = modal.querySelector("#id-cancel-reason-motivo");

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("has-delete-modal-open");
      if (textarea) textarea.value = "";
      if (activeTrigger && typeof activeTrigger.focus === "function") {
        activeTrigger.focus();
      }
      activeTrigger = null;
    }

    function openModal(trigger) {
      var cancelUrl = trigger.getAttribute("data-cancel-url");
      if (!cancelUrl || !form) return;

      activeTrigger = trigger;
      form.setAttribute("action", cancelUrl);
      if (label) {
        label.textContent = trigger.getAttribute("data-cancel-label") || "este registro";
      }
      modal.hidden = false;
      document.body.classList.add("has-delete-modal-open");
      if (textarea && typeof textarea.focus === "function") {
        textarea.focus();
      } else if (dialog && typeof dialog.focus === "function") {
        dialog.focus();
      }
    }

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-cancel-modal-trigger]");
      if (trigger) {
        event.preventDefault();
        openModal(trigger);
        return;
      }

      if (!modal.hidden && event.target.closest("[data-cancel-modal-cancel]")) {
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
