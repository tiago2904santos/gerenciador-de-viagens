(function () {
  "use strict";

  var activeTrigger = null;
  var currentRemoveUrl = "";
  var BOUND = "data-attach-signed-bound";

  function init(root) {
    var scope = root && root.querySelector ? root : document;
    var modal = scope.matches && scope.matches("[data-attach-signed-modal]")
      ? scope
      : scope.querySelector("[data-attach-signed-modal]");
    if (!modal || modal.getAttribute(BOUND) === "true") return false;
    modal.setAttribute(BOUND, "true");

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-attach-signed-form]");
    var label = modal.querySelector("[data-attach-signed-label]");
    var nextInput = modal.querySelector("[data-attach-signed-next]");
    var currentBlock = modal.querySelector("[data-attach-signed-current]");
    var currentName = modal.querySelector("[data-attach-signed-current-name]");
    var currentOpen = modal.querySelector("[data-attach-signed-current-open]");
    var kindSelector = modal.querySelector("[data-attach-signed-kind-selector]");
    var kindButtons = modal.querySelectorAll("[data-attach-signed-kind]");
    var primaryOptionLabel = modal.querySelector("[data-attach-signed-primary-option-label]");
    var secondaryOptionLabel = modal.querySelector("[data-attach-signed-secondary-option-label]");
    var tertiaryOptionLabel = modal.querySelector("[data-attach-signed-tertiary-option-label]");
    var tertiaryOptionButton = modal.querySelector('[data-attach-signed-kind="tertiary"]');
    var fileDescription = modal.querySelector("[data-attach-signed-file-description]");
    var fileHelp = modal.querySelector("[data-attach-signed-file-help]");
    var fileInput = modal.querySelector('input[type="file"]');
    var chooseLabel = modal.querySelector("[data-file-picker-action-label]");
    var uploadButton = modal.querySelector("[data-file-upload-button]");
    var fileDefaults = {
      accept: fileInput ? fileInput.getAttribute("accept") || "" : "",
      description: fileDescription ? fileDescription.textContent : "",
      help: fileHelp ? fileHelp.textContent : "",
      choose: chooseLabel ? chooseLabel.textContent : "",
      upload: uploadButton ? uploadButton.textContent : "",
    };

    function clearSelectedFile() {
      if (!form) return;
      var input = form.querySelector('input[type="file"]');
      if (!input || !input.value) return;
      input.value = "";
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function documentData(kind) {
      if (!activeTrigger) return null;
      var prefix = "data-attach-signed-";
      if (kind === "secondary") prefix += "secondary-";
      if (kind === "tertiary") prefix += "tertiary-";
      return {
        url: activeTrigger.getAttribute(prefix + "url") || "",
        label: activeTrigger.getAttribute(prefix + "doc-label") || "este documento",
        currentName: activeTrigger.getAttribute(prefix + "current-name") || "",
        currentViewUrl: activeTrigger.getAttribute(prefix + "current-view-url") || "",
        currentRemoveUrl: activeTrigger.getAttribute(prefix + "current-remove-url") || "",
      };
    }

    function updateReturnUrl(kind) {
      if (!nextInput) return;
      var base = window.location.pathname + window.location.search;
      var reopenKey = activeTrigger
        ? activeTrigger.getAttribute("data-attach-signed-reopen-key") || ""
        : "";
      nextInput.value = reopenKey
        ? base + "#attach-signed=" + encodeURIComponent(reopenKey) + "&kind=" + encodeURIComponent(kind)
        : base + window.location.hash;
    }

    function selectDocument(kind, clearFile) {
      var data = documentData(kind);
      if (!data || !data.url || !form) return;
      if (clearFile) clearSelectedFile();

      form.setAttribute("action", data.url);
      if (label) label.textContent = data.label;
      currentRemoveUrl = data.currentRemoveUrl;
      if (currentBlock) currentBlock.hidden = !data.currentName;
      if (currentName) currentName.textContent = data.currentName;
      if (currentOpen) currentOpen.setAttribute("href", data.currentViewUrl || "#");
      updateReturnUrl(kind);

      kindButtons.forEach(function (button) {
        var active = button.getAttribute("data-attach-signed-kind") === kind;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
      });
    }

    function closeModal() {
      if (window.CV && window.CV.dialogs) {
        window.CV.dialogs.close(modal);
      } else {
        modal.hidden = true;
        document.body.classList.remove("has-delete-modal-open");
        if (activeTrigger && typeof activeTrigger.focus === "function") activeTrigger.focus();
      }
      activeTrigger = null;
      currentRemoveUrl = "";
      clearSelectedFile();
      var hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      if (hashParams.has("attach-signed")) {
        hashParams.delete("attach-signed");
        hashParams.delete("kind");
        var remainingHash = hashParams.toString();
        window.history.replaceState(
          null,
          "",
          window.location.pathname + window.location.search + (remainingHash ? "#" + remainingHash : "")
        );
      }
    }

    function openModal(trigger, initialKind) {
      var url = trigger.getAttribute("data-attach-signed-url");
      if (!url || !form) return;

      activeTrigger = trigger;

      var secondaryUrl = trigger.getAttribute("data-attach-signed-secondary-url") || "";
      var tertiaryUrl = trigger.getAttribute("data-attach-signed-tertiary-url") || "";
      if (fileInput) {
        fileInput.setAttribute(
          "accept",
          trigger.getAttribute("data-attach-signed-accept") || fileDefaults.accept
        );
      }
      if (fileDescription) {
        fileDescription.textContent =
          trigger.getAttribute("data-attach-signed-file-description") || fileDefaults.description;
      }
      if (fileHelp) {
        fileHelp.textContent =
          trigger.getAttribute("data-attach-signed-file-help") || fileDefaults.help;
      }
      if (chooseLabel) {
        chooseLabel.textContent =
          trigger.getAttribute("data-attach-signed-choose-label") || fileDefaults.choose;
      }
      if (uploadButton) {
        uploadButton.textContent =
          trigger.getAttribute("data-attach-signed-upload-label") || fileDefaults.upload;
      }
      if (kindSelector) kindSelector.hidden = !secondaryUrl;
      if (tertiaryOptionButton) tertiaryOptionButton.hidden = !tertiaryUrl;
      if (primaryOptionLabel) {
        primaryOptionLabel.textContent =
          trigger.getAttribute("data-attach-signed-primary-option-label") || "Documento principal";
      }
      if (secondaryOptionLabel) {
        secondaryOptionLabel.textContent =
          trigger.getAttribute("data-attach-signed-secondary-option-label") || "Documento adicional";
      }
      if (tertiaryOptionLabel) {
        tertiaryOptionLabel.textContent =
          trigger.getAttribute("data-attach-signed-tertiary-option-label") || "Outro documento";
      }
      var selectedKind = initialKind || "primary";
      if (!documentData(selectedKind) || !documentData(selectedKind).url) selectedKind = "primary";
      selectDocument(selectedKind, false);

      if (window.CV && window.CV.dialogs) {
        window.CV.dialogs.open(modal, {
          opener: trigger,
          initialFocus: fileInput || dialog,
          onRequestClose: closeModal,
        });
      } else {
        modal.hidden = false;
        document.body.classList.add("has-delete-modal-open");
        if (dialog && typeof dialog.focus === "function") dialog.focus();
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
        openModal(trigger, "primary");
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
        return;
      }

      var kindButton = event.target.closest("[data-attach-signed-kind]");
      if (!modal.hidden && kindButton) {
        event.preventDefault();
        selectDocument(kindButton.getAttribute("data-attach-signed-kind"), true);
      }
    });

    document.addEventListener("keydown", function (event) {
      if ((!window.CV || !window.CV.dialogs) && !modal.hidden && event.key === "Escape") {
        closeModal();
      }
    });

    var reopenParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    var reopenKey = reopenParams.get("attach-signed");
    if (reopenKey) {
      var reopenTrigger = Array.prototype.find.call(
        document.querySelectorAll("[data-attach-signed-reopen-key]"),
        function (trigger) {
          return trigger.getAttribute("data-attach-signed-reopen-key") === reopenKey;
        }
      );
      if (reopenTrigger) openModal(reopenTrigger, reopenParams.get("kind") || "primary");
    }
    return true;
  }

  window.CV = window.CV || {};
  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("attachSignedModal", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
})();
