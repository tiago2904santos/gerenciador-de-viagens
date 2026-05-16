(function () {
  function getPanelId(toggle) {
    return (
      toggle.getAttribute("aria-controls") ||
      toggle.getAttribute("data-quick-add-toggle") ||
      toggle.getAttribute("data-ui-lab-toggle")
    );
  }

  function getCloseSelector(panelId) {
    return (
      '[data-quick-add-close][aria-controls="' +
      panelId +
      '"], [data-quick-add-close], [data-ui-lab-close]'
    );
  }

  function initQuickAddToggles() {
    var toggles = Array.prototype.slice.call(
      document.querySelectorAll("[data-quick-add-toggle], [data-ui-lab-toggle]")
    );

    toggles.forEach(function (toggle) {
      var panelId = getPanelId(toggle);
      if (!panelId) {
        return;
      }

      var panel = document.getElementById(panelId);
      if (!panel) {
        return;
      }

      var closeButtons = Array.prototype.slice.call(panel.querySelectorAll(getCloseSelector(panelId)));
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

      toggle.addEventListener("click", function () {
        var expanded = toggle.getAttribute("aria-expanded") === "true";
        if (expanded) {
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

  initQuickAddToggles();
}());
