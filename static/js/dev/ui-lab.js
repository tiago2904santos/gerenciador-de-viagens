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

/* --------------------------------------------------------------------------
   Button demos — loading state
   -------------------------------------------------------------------------- */
(function () {
  function initButtonLoadingDemos() {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll('[data-button-loading-demo]')
    );

    buttons.forEach(function (btn) {
      var originalText = btn.textContent;

      btn.addEventListener('click', function () {
        if (btn.classList.contains('is-loading')) {
          return;
        }

        btn.classList.add('is-loading');
        btn.setAttribute('disabled', '');
        btn.textContent = 'Processando...';

        window.setTimeout(function () {
          btn.classList.remove('is-loading');
          btn.removeAttribute('disabled');
          btn.textContent = originalText;
        }, 2000);
      });
    });
  }

  initButtonLoadingDemos();
}());

/* --------------------------------------------------------------------------
   Button demos — toggle active state
   -------------------------------------------------------------------------- */
(function () {
  function initButtonToggleDemos() {
    var buttons = Array.prototype.slice.call(
      document.querySelectorAll('[data-button-toggle-demo]')
    );

    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        btn.classList.toggle('is-active');
        btn.classList.toggle('is-selected');
        var isActive = btn.classList.contains('is-active');
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      });
    });
  }

  initButtonToggleDemos();
}());
