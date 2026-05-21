(function () {
  'use strict';

  function applyViaturaMotoristaFixoUi(form, opts) {
    var temMotoristaFixo = form.querySelector('#id_tem_motorista_fixo');
    var panel = form.querySelector('[data-viatura-motoristas-panel]');
    var motoristasSelect = form.querySelector('#id_motoristas');
    if (!temMotoristaFixo || !panel) return;

    var hasFixed = temMotoristaFixo.checked;
    panel.classList.toggle('viatura-motoristas-panel--open', hasFixed);
    panel.setAttribute('aria-hidden', hasFixed ? 'false' : 'true');

    if (!hasFixed && motoristasSelect && opts && opts.clearOnHide) {
      Array.prototype.forEach.call(motoristasSelect.options, function (option) {
        option.selected = false;
      });
      motoristasSelect.dispatchEvent(new Event('change', { bubbles: true }));
    }
  }

  function initViaturaMotoristaFixoForms() {
    document.querySelectorAll('[data-viatura-motorista-form]').forEach(function (form) {
      var temMotoristaFixo = form.querySelector('#id_tem_motorista_fixo');
      if (!temMotoristaFixo) return;

      if (window.CV && window.CV.stateToggle && typeof window.CV.stateToggle.init === 'function') {
        window.CV.stateToggle.init(form);
      }

      applyViaturaMotoristaFixoUi(form, { clearOnHide: false });

      temMotoristaFixo.addEventListener('change', function () {
        applyViaturaMotoristaFixoUi(form, { clearOnHide: true });
      });

      form.addEventListener('cv:state-toggle:change', function () {
        applyViaturaMotoristaFixoUi(form, { clearOnHide: true });
      });
    });
  }

  function boot() {
    initViaturaMotoristaFixoForms();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
