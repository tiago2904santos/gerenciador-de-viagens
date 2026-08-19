/**
 * Etapa 1 — visibilidade do Card de Motorista e troca SERVIDOR ↔ MANUAL.
 *
 * O card aparece quando:
 *   • viatura está selecionada (select[name="viatura"] tem valor), E
 *   • nenhum driver toggle da equipe está ativo (aria-pressed="true")
 *
 * Dentro do card, o usuário pode buscar o motorista no sistema (SERVIDOR)
 * ou digitar o nome manualmente (MANUAL), usando o toggle de botões.
 */
(function () {
  'use strict';

  var ROOT_SEL       = '[data-travel-document-wizard-step1]';
  var VIATURA_SEL    = 'select[name="viatura"][data-entity-picker]';
  var EQUIPE_SEL     = 'select[name="servidores"]';
  var MOTORISTA_SEL  = 'select[name="motorista"]';
  var MODO_SEL       = 'input[name="motorista_modo"]';
  var EXTERNAL_CARD  = '[data-oficio-driver-external-card]';
  var EXTRAS_PANEL   = '[data-oficio-motorista-extras]';
  var PANEL_SERVIDOR = '[data-oficio-motorista-servidor]';
  var PANEL_MANUAL   = '[data-oficio-motorista-manual]';
  var MODO_BTN       = '[data-oficio-motorista-modo-btn]';
  var DRIVER_ACTIVE  = '[data-entity-picker-part="driver-surface"][aria-pressed="true"], [data-entity-picker-part="driver-toggle"][aria-pressed="true"]';

  /* ── Helpers ─────────────────────────────────────────────────── */

  function setCardVisible(card, visible) {
    if (!card) return;
    if (visible) {
      card.hidden = false;
      card.classList.remove('form-field--hidden');
      card.classList.add('is-open');
    } else {
      card.classList.remove('is-open');
      card.hidden = true;
      card.classList.add('form-field--hidden');
    }
    card.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  function setPanelVisible(panel, visible) {
    if (!panel) return;
    /* Inline style garante precedência sobre qualquer regra CSS */
    panel.style.display = visible ? '' : 'none';
    panel.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  function setExtrasVisible(panel, visible) {
    if (!panel) return;
    panel.hidden = !visible;
    panel.setAttribute('aria-hidden', visible ? 'false' : 'true');
  }

  function dispatchFieldEvents(el) {
    if (!el) return;
    el.dispatchEvent(new Event('input',  { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function setModoHidden(root, modo) {
    var hidden = root.querySelector(MODO_SEL);
    if (!hidden || hidden.value === modo) return;   /* evita loop */
    hidden.value = modo;
    hidden.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function activeDriverValue(root) {
    var equipeSelect = root.querySelector(EQUIPE_SEL);
    if (equipeSelect && equipeSelect.dataset.pickerDriverValue) {
      return equipeSelect.dataset.pickerDriverValue;
    }
    var active = root.querySelector(DRIVER_ACTIVE);
    return (active && active.dataset.value) || '';
  }

  function selectHasValue(select, value) {
    if (!select || !value) return false;
    return !!select.querySelector('option[value="' + CSS.escape(value) + '"]');
  }

  function clearManualMotorista(card) {
    if (!card) return;
    var manInput = card.querySelector(PANEL_MANUAL + ' input:not([type="hidden"])');
    if (manInput && manInput.value) {
      manInput.value = '';
      dispatchFieldEvents(manInput);
    }
  }

  function syncEquipeDriverToMotorista(root) {
    var value = activeDriverValue(root);
    var motSel = root.querySelector(MOTORISTA_SEL);
    if (!motSel) return value;

    var previousDriverValue = motSel.dataset.oficioEquipeDriverValue || '';

    if (value && selectHasValue(motSel, value)) {
      if (motSel.value !== value) {
        motSel.value = value;
        dispatchFieldEvents(motSel);
      }
      motSel.dataset.oficioEquipeDriverValue = value;
      setModoHidden(root, 'SERVIDOR');
      return value;
    }

    if (previousDriverValue && motSel.value === previousDriverValue) {
      motSel.value = '';
      dispatchFieldEvents(motSel);
    }
    delete motSel.dataset.oficioEquipeDriverValue;
    return value;
  }

  /* ── Sincroniza visual do segment-toggle ─────────────────── */

  function syncModoButtons(root) {
    var modoInput = root.querySelector(MODO_SEL);
    var modo = (modoInput && modoInput.value) || 'SERVIDOR';
    root.querySelectorAll(MODO_BTN).forEach(function (btn) {
      var active    = (btn.dataset.value || 'SERVIDOR') === modo;
      var wasActive = btn.getAttribute('aria-pressed') === 'true';

      btn.setAttribute('aria-pressed', active ? 'true' : 'false');

      /* Dispara animação de entrada apenas na troca (não no carregamento) */
      if (active && !wasActive) {
        btn.classList.remove('segment-toggle__btn--pop');
        void btn.offsetWidth;   /* reinicia o keyframe */
        btn.classList.add('segment-toggle__btn--pop');
      }
    });
  }

  /* ── Trocar entre modo SERVIDOR (picker) e MANUAL (input) ────── */

  function applyModo(root, modo) {
    var card = root.querySelector(EXTERNAL_CARD);
    if (!card) return;

    var panelServ = card.querySelector(PANEL_SERVIDOR);
    var panelMan  = card.querySelector(PANEL_MANUAL);
    var isManual  = modo === 'MANUAL';

    setPanelVisible(panelServ, !isManual);
    setPanelVisible(panelMan,  isManual);
    setModoHidden(root, modo);
  }

  function switchToManual(root) {
    /* Limpa o motorista selecionado no picker antes de mudar */
    var motSel = root.querySelector(MOTORISTA_SEL);
    if (motSel && motSel.value) {
      motSel.value = '';
      dispatchFieldEvents(motSel);
    }
    applyModo(root, 'MANUAL');

    /* Foca o campo de nome */
    var card = root.querySelector(EXTERNAL_CARD);
    if (card) {
      var input = card.querySelector(PANEL_MANUAL + ' input:not([type="hidden"])');
      if (input) setTimeout(function () { input.focus(); }, 50);
    }
  }

  function switchToServidor(root) {
    /* Limpa o nome manual antes de mudar */
    var card = root.querySelector(EXTERNAL_CARD);
    if (card) {
      var input = card.querySelector(PANEL_MANUAL + ' input:not([type="hidden"])');
      if (input && input.value) { input.value = ''; dispatchFieldEvents(input); }
    }
    applyModo(root, 'SERVIDOR');
  }

  /* ── Visibilidade do card ─────────────────────────────────────── */

  function isDriverActive(root) {
    return !!activeDriverValue(root);
  }

  function hasViatura(root) {
    var sel = root.querySelector(VIATURA_SEL);
    return !!(sel && sel.value);
  }

  function sync(root) {
    var driverValue = syncEquipeDriverToMotorista(root);
    var show = hasViatura(root) && !isDriverActive(root);
    var card  = root.querySelector(EXTERNAL_CARD);
    setCardVisible(card, show);
    setExtrasVisible(card && card.querySelector(EXTRAS_PANEL), show);

    if (driverValue) {
      clearManualMotorista(card);
      return;
    }

    /* Se o card sumiu por falta de viatura, limpa motorista externo */
    if (!show && card && !card.hidden && !hasViatura(root)) {
      var motSel = root.querySelector(MOTORISTA_SEL);
      if (motSel && motSel.value) { motSel.value = ''; dispatchFieldEvents(motSel); }
      clearManualMotorista(card);
    }
  }

  /* ── Inicialização do modo (edição de ofício existente) ────────── */

  function initModo(root) {
    var modoHidden = root.querySelector(MODO_SEL);
    var modo = (modoHidden && modoHidden.value) || 'SERVIDOR';
    applyModo(root, modo);
    syncModoButtons(root);
  }

  /* ── Bind de eventos ─────────────────────────────────────────── */

  function bind(root) {
    /* Viatura: mostra/esconde card */
    var viaturaSelect = root.querySelector(VIATURA_SEL);
    if (viaturaSelect) {
      viaturaSelect.addEventListener('change', function () { sync(root); });
    }

    /* Equipe: servidor adicionado/removido pode mudar quem é driver */
    var equipeSelect = root.querySelector(EQUIPE_SEL);
    if (equipeSelect) {
      equipeSelect.addEventListener('change', function () { sync(root); });
    }

    /* O picker publica o motorista real escolhido no card da equipe. */
    root.addEventListener('cv:search-picker-driver-change', function (e) {
      if (e.target !== equipeSelect) return;
      sync(root);
    });

    /* Toggle SERVIDOR ↔ MANUAL */
    root.addEventListener('click', function (e) {
      var btn = e.target.closest(MODO_BTN);
      if (!btn) return;
      var newModo = btn.dataset.value || 'SERVIDOR';
      if (newModo === 'MANUAL') switchToManual(root);
      else                      switchToServidor(root);
      syncModoButtons(root);
    });

    /* Quando o picker de motorista seleciona alguém → garantir modo SERVIDOR */
    var motSel = root.querySelector(MOTORISTA_SEL);
    if (motSel) {
      motSel.addEventListener('change', function () {
        if (motSel.value) setModoHidden(root, 'SERVIDOR');
      });
    }

    sync(root);
    initModo(root);
  }

  /* ── Boot ────────────────────────────────────────────────────── */

  function init() {
    var root = document.querySelector(ROOT_SEL);
    if (!root) return;
    if (window.CV && window.CV.onReady) {
      window.CV.onReady(function () { bind(root); });
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
