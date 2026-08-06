/* UI Lab — demos de botões (Quick Add usa core/app.js + data-quick-add-*). */

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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      initButtonLoadingDemos();
      initButtonToggleDemos();
    });
  } else {
    initButtonLoadingDemos();
    initButtonToggleDemos();
  }
})();
