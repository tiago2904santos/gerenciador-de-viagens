(function () {
  const consent = document.getElementById("signature-consent-checkbox");
  const confirmOpen = document.getElementById("signature-confirm-open");
  const confirmModal = document.getElementById("signature-confirmation-modal");
  const refuseModal = document.getElementById("signature-refuse-modal");
  const detailsModal = document.getElementById("signature-details-modal");

  function openDialog(dialog) {
    if (!dialog) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "open");
  }

  function closeDialog(dialog) {
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function syncConsent() {
    if (!confirmOpen || !consent) return;
    confirmOpen.disabled = !consent.checked;
  }

  if (consent) {
    consent.addEventListener("change", syncConsent);
    syncConsent();
  }

  if (confirmOpen) {
    confirmOpen.addEventListener("click", function () {
      if (!consent || !consent.checked) return;
      openDialog(confirmModal);
    });
  }

  document.addEventListener("click", function (event) {
    const close = event.target.closest("[data-modal-close]");
    if (close) {
      closeDialog(close.closest("dialog"));
      return;
    }
    if (event.target.closest("[data-signature-refuse-open]")) {
      openDialog(refuseModal);
      return;
    }
    if (event.target.closest("[data-signature-details-open]")) {
      openDialog(detailsModal);
    }
  });
})();
