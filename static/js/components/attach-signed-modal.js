(function () {
  "use strict";

  var activeTrigger = null;

  function init() {
    var modal = document.querySelector("[data-attach-signed-modal]");
    if (!modal) return;

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-attach-signed-form]");
    var label = modal.querySelector("[data-attach-signed-label]");
    var nextInput = modal.querySelector("[data-attach-signed-next]");

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("has-delete-modal-open");
      if (activeTrigger && typeof activeTrigger.focus === "function") {
        activeTrigger.focus();
      }
      activeTrigger = null;
    }

    function openModal(trigger) {
      var url = trigger.getAttribute("data-attach-signed-url");
      if (!url || !form) return;

      activeTrigger = trigger;
      form.setAttribute("action", url);
      if (label) {
        label.textContent = trigger.getAttribute("data-attach-signed-doc-label") || "este documento";
      }
      if (nextInput) {
        nextInput.value = window.location.pathname + window.location.search + window.location.hash;
      }
      modal.hidden = false;
      document.body.classList.add("has-delete-modal-open");
      if (dialog && typeof dialog.focus === "function") {
        dialog.focus();
      }
    }

    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-attach-signed-trigger]");
      if (trigger) {
        event.preventDefault();
        openModal(trigger);
        return;
      }

      if (!modal.hidden && event.target.closest("[data-attach-signed-cancel]")) {
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
