document.documentElement.dataset.appReady = "true";

(function () {
  function getPanelId(toggle) {
    return toggle.getAttribute("aria-controls") || toggle.getAttribute("data-quick-add-toggle");
  }

  function initQuickAddToggles() {
    var toggles = Array.prototype.slice.call(document.querySelectorAll("[data-quick-add-toggle]"));

    toggles.forEach(function (toggle) {
      var panelId = getPanelId(toggle);
      var panel = panelId ? document.getElementById(panelId) : null;

      if (!panel) {
        return;
      }

      var closeButtons = Array.prototype.slice.call(panel.querySelectorAll("[data-quick-add-close]"));
      var hideTimer = null;

      function finishHide() {
        panel.hidden = true;
        panel.removeEventListener("transitionend", finishHide);
      }

      function openPanel() {
        if (hideTimer) {
          window.clearTimeout(hideTimer);
          hideTimer = null;
        }

        panel.hidden = false;
        window.requestAnimationFrame(function () {
          panel.classList.add("is-open");
        });
        toggle.setAttribute("aria-expanded", "true");
        toggle.classList.add("is-active");
      }

      function closePanel() {
        toggle.setAttribute("aria-expanded", "false");
        toggle.classList.remove("is-active");
        panel.classList.remove("is-open");
        panel.addEventListener("transitionend", finishHide);
        hideTimer = window.setTimeout(finishHide, 280);
      }

      if (toggle.getAttribute("aria-expanded") === "true") {
        openPanel();
      }

      toggle.addEventListener("click", function () {
        if (toggle.getAttribute("aria-expanded") === "true") {
          closePanel();
        } else {
          openPanel();
        }
      });

      closeButtons.forEach(function (button) {
        button.addEventListener("click", closePanel);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initQuickAddToggles);
  } else {
    initQuickAddToggles();
  }
}());
