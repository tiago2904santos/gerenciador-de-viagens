(function () {
  function onlyDigits(value) {
    return (value || "").replace(/\D/g, "");
  }

  function resolveYear(wrapper, hidden) {
    const raw =
      (wrapper && wrapper.dataset.oficioAno) ||
      (hidden && hidden.dataset.oficioAno) ||
      (hidden && hidden.dataset.maskYear) ||
      "";
    const y = parseInt(String(raw), 10);
    if (y >= 1900 && y <= 2100) {
      return y;
    }
    return new Date().getFullYear();
  }

  function parseNumeroFromHidden(hidden) {
    const v = (hidden.value || "").trim();
    if (!v) {
      return "";
    }
    const head = v.split("/")[0];
    return onlyDigits(head).slice(0, 3);
  }

  function syncFromHidden(wrapper) {
    const hidden = wrapper.querySelector("[data-oficio-motorista-hidden]");
    const num = wrapper.querySelector("[data-oficio-motorista-number]");
    if (!hidden || !num) {
      return;
    }
    num.value = parseNumeroFromHidden(hidden);
  }

  function syncToHidden(wrapper) {
    const hidden = wrapper.querySelector("[data-oficio-motorista-hidden]");
    const num = wrapper.querySelector("[data-oficio-motorista-number]");
    if (!hidden || !num) {
      return;
    }
    const year = resolveYear(wrapper, hidden);
    let digits = onlyDigits(num.value).slice(0, 3);
    num.value = digits;
    hidden.value = digits ? `${digits}/${year}` : "";
    hidden.dispatchEvent(new Event("input", { bubbles: true }));
    hidden.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function initWrapper(wrapper) {
    const hidden = wrapper.querySelector("[data-oficio-motorista-hidden]");
    const num = wrapper.querySelector("[data-oficio-motorista-number]");
    if (!hidden || !num) {
      return;
    }
    syncFromHidden(wrapper);
    ["input", "blur"].forEach(function (ev) {
      num.addEventListener(ev, function () {
        syncToHidden(wrapper);
      });
    });
  }

  function boot() {
    document.querySelectorAll("[data-oficio-motorista-addon]").forEach(initWrapper);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
