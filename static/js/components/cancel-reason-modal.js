(function () {
  "use strict";

  var activeTrigger = null;
  var BOUND = "data-cancel-reason-bound";

  function init(root) {
    var scope = root && root.querySelector ? root : document;
    var modal = scope.matches && scope.matches("[data-cancel-reason-modal]")
      ? scope
      : scope.querySelector("[data-cancel-reason-modal]");
    if (!modal || modal.getAttribute(BOUND) === "true") return false;
    modal.setAttribute(BOUND, "true");

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-cancel-reason-form]");
    var label = modal.querySelector("[data-cancel-reason-label]");
    var textarea = modal.querySelector("#id-cancel-reason-motivo");

    function closeModal() {
      if (window.CV && window.CV.dialogs) window.CV.dialogs.close(modal);
      else {
        modal.hidden = true;
        document.body.classList.remove("has-delete-modal-open");
        if (activeTrigger && typeof activeTrigger.focus === "function") activeTrigger.focus();
      }
      if (textarea) textarea.value = "";
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
      var initialFocus = textarea && typeof textarea.focus === "function" ? textarea : dialog;
      if (window.CV && window.CV.dialogs) {
        window.CV.dialogs.open(modal, { opener: trigger, initialFocus: initialFocus, onRequestClose: closeModal });
      } else {
        modal.hidden = false;
        document.body.classList.add("has-delete-modal-open");
        if (initialFocus && typeof initialFocus.focus === "function") initialFocus.focus();
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
      if ((!window.CV || !window.CV.dialogs) && !modal.hidden && event.key === "Escape") {
        closeModal();
      }
    });
    return true;
  }

  window.CV = window.CV || {};
  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("cancelReasonModal", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
