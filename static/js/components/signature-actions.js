(function () {
  "use strict";

  function copySignatureLink(button) {
    const card = button.closest("[data-cv-signature-card]");
    const input = card ? card.querySelector("[data-cv-signature-link]") : null;
    if (!input) return;

    const originalLabel = button.textContent;
    const markCopied = function () {
      button.textContent = "Copiado!";
      window.setTimeout(function () {
        button.textContent = originalLabel;
      }, 1500);
    };

    input.select();
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(input.value).then(markCopied, function () {
        document.execCommand("copy");
        markCopied();
      });
      return;
    }
    document.execCommand("copy");
    markCopied();
  }

  function openWhatsApp(button) {
    const phone = (button.dataset.waPhone || "").replace(/\D/g, "");
    const encodedText = encodeURIComponent(button.dataset.waText || "");
    const fallbackUrl = "https://wa.me/" + phone + "?text=" + encodedText;

    if (/Android/i.test(navigator.userAgent || "")) {
      const packageName = button.dataset.waApp === "business" ? "com.whatsapp.w4b" : "com.whatsapp";
      const query = (phone ? "phone=" + phone + "&" : "") + "text=" + encodedText;
      window.location.href =
        "intent://send?" + query + "#Intent;scheme=whatsapp;package=" + packageName +
        ";S.browser_fallback_url=" + encodeURIComponent(fallbackUrl) + ";end";
      return;
    }
    window.open(fallbackUrl, "_blank", "noopener");
  }

  document.addEventListener("click", function (event) {
    const copyButton = event.target.closest("[data-cv-signature-copy]");
    if (copyButton) {
      event.preventDefault();
      copySignatureLink(copyButton);
      return;
    }

    const whatsappButton = event.target.closest("[data-cv-signature-wa]");
    if (whatsappButton) {
      event.preventDefault();
      openWhatsApp(whatsappButton);
    }
  });
})();
