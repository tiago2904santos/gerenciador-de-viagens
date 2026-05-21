/**
 * Etapa 1 — exibe/oculta Card 4 (motorista externo) conforme motorista na equipe.
 */
(function () {
  'use strict';

  var ROOT_SEL = '[data-oficio-wizard-step1]';
  var EQUIPE_SEL = 'select[name="servidores"]';
  var MOTORISTA_SEL = 'select[name="motorista"]';
  var MODO_SEL = 'input[name="motorista_modo"]';
  var EXTERNAL_CARD_SEL = '[data-oficio-driver-external-card]';
  var MANUAL_PANEL_SEL = '[data-oficio-motorista-manual]';
  var EXTRAS_SEL = '[data-oficio-motorista-extras]';

  function parseEquipeIds(root) {
    var viaturaRoot = root.querySelector('.oficio-transporte-root');
    var csv = (viaturaRoot && viaturaRoot.dataset.equipeServidorIds) || '';
    if (csv) {
      return csv.split(',').map(function (id) {
        return id.trim();
      }).filter(Boolean);
    }
    var select = root.querySelector(EQUIPE_SEL);
    if (!select) return [];
    return Array.prototype.slice
      .call(select.selectedOptions || [])
      .map(function (opt) {
        return String(opt.value || '').trim();
      })
      .filter(Boolean);
  }

  function readMotoristaId(root) {
    var select = root.querySelector(MOTORISTA_SEL);
    if (!select) return '';
    return String(select.value || '').trim();
  }

  function setModo(root, modo) {
    var hidden = root.querySelector(MODO_SEL);
    if (!hidden) return;
    hidden.value = modo;
    hidden.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function setCardVisible(card, visible) {
    if (!card) return;
    card.hidden = !visible;
    card.classList.toggle('form-field--hidden', !visible);
    card.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  function sync(root) {
    var motoristaId = readMotoristaId(root);
    var equipeIds = parseEquipeIds(root);
    var inTeam = motoristaId && equipeIds.indexOf(motoristaId) !== -1;
    var externalCard = root.querySelector(EXTERNAL_CARD_SEL);

    if (inTeam) {
      setModo(root, 'SERVIDOR');
      setCardVisible(externalCard, false);
      return;
    }

    if (motoristaId) {
      setModo(root, 'SERVIDOR');
      setCardVisible(externalCard, true);
      return;
    }

    setModo(root, 'MANUAL');
    setCardVisible(externalCard, true);
    var manual = root.querySelector(MANUAL_PANEL_SEL);
    var extras = root.querySelector(EXTRAS_SEL);
    if (manual) manual.classList.remove('form-field--hidden');
    if (extras) extras.classList.remove('form-field--hidden');
  }

  function bind(root) {
    var motoristaSelect = root.querySelector(MOTORISTA_SEL);
    var equipeSelect = root.querySelector(EQUIPE_SEL);

    if (motoristaSelect) {
      motoristaSelect.addEventListener('change', function () {
        sync(root);
      });
    }
    if (equipeSelect) {
      equipeSelect.addEventListener('change', function () {
        var viaturaRoot = root.querySelector('.oficio-transporte-root');
        if (viaturaRoot) {
          var ids = Array.prototype.slice
            .call(equipeSelect.selectedOptions || [])
            .map(function (o) {
              return o.value;
            })
            .filter(Boolean)
            .join(',');
          viaturaRoot.dataset.equipeServidorIds = ids;
        }
        sync(root);
      });
    }

    document.addEventListener('cv:state-toggle:change', function () {
      sync(root);
    });

    sync(root);
  }

  function init() {
    var root = document.querySelector(ROOT_SEL);
    if (!root) return;

    if (window.CV && window.CV.onReady) {
      window.CV.onReady(function () {
        bind(root);
      });
    } else {
      bind(root);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
