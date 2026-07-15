(function () {
  "use strict";

  var activeTrigger = null;
  var currentRemoveUrl = "";

  function init() {
    var modal = document.querySelector("[data-attach-signed-modal]");
    if (!modal) return;

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-attach-signed-form]");
    var label = modal.querySelector("[data-attach-signed-label]");
    var nextInput = modal.querySelector("[data-attach-signed-next]");
    var currentBlock = modal.querySelector("[data-attach-signed-current]");
    var currentName = modal.querySelector("[data-attach-signed-current-name]");
    var currentOpen = modal.querySelector("[data-attach-signed-current-open]");

    function closeModal() {
      modal.hidden = true;
      document.body.classList.remove("has-delete-modal-open");
      if (activeTrigger && typeof activeTrigger.focus === "function") {
        activeTrigger.focus();
      }
      activeTrigger = null;
      currentRemoveUrl = "";
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

      var currentName_ = trigger.getAttribute("data-attach-signed-current-name") || "";
      var currentViewUrl = trigger.getAttribute("data-attach-signed-current-view-url") || "";
      currentRemoveUrl = trigger.getAttribute("data-attach-signed-current-remove-url") || "";
      if (currentBlock) {
        currentBlock.hidden = !currentName_;
      }
      if (currentName) {
        currentName.textContent = currentName_;
      }
      if (currentOpen) {
        currentOpen.setAttribute("href", currentViewUrl || "#");
      }

      modal.hidden = false;
      document.body.classList.add("has-delete-modal-open");
      if (dialog && typeof dialog.focus === "function") {
        dialog.focus();
      }
    }

    function removeCurrentSigned() {
      if (!currentRemoveUrl || !form) return;
      var csrfInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
      var token = csrfInput ? csrfInput.value : "";
      fetch(currentRemoveUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": token },
      }).then(function () {
        window.location.reload();
      });
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
        return;
      }

      if (!modal.hidden && event.target.closest("[data-attach-signed-remove]")) {
        event.preventDefault();
        removeCurrentSigned();
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
