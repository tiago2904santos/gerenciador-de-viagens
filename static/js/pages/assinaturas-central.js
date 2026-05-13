document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-copy-value]");
  if (!button) return;
  const value = button.dataset.copyValue || "";
  if (!value || !navigator.clipboard) return;
  navigator.clipboard.writeText(value).then(function () {
    const original = button.textContent;
    const done = button.dataset.copyDone || "Copiado";
    button.textContent = done;
    window.setTimeout(function () {
      button.textContent = original;
    }, 1800);
  });
});
