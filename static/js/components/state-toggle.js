/**
 * State toggle global — opções ou botão binário com checkbox.
 */
(function () {
  'use strict';

  var BOUND = 'data-cv-state-bound';
  var EVENT_NAME = 'cv:state-toggle:change';

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function resolveInput(container) {
    var selector = container.getAttribute('data-cv-state-input');
    if (selector) {
      if (selector.charAt(0) === '#') {
        return document.getElementById(selector.slice(1));
      }
      return container.querySelector(selector);
    }
    return (
      container.querySelector('[data-cv-state-input]') ||
      container.querySelector('input[type="checkbox"]')
    );
  }

  function readValue(input) {
    if (!input) return '';
    if (input.type === 'checkbox') {
      return input.checked ? 'true' : 'false';
    }
    return String(input.value == null ? '' : input.value);
  }

  function writeValue(input, value) {
    if (!input) return;
    if (input.type === 'checkbox') {
      var on =
        value === true ||
        value === 'true' ||
        value === '1' ||
        value === 'on' ||
        value === 'yes';
      input.checked = !!on;
      return;
    }
    input.value = value == null ? '' : String(value);
  }

  function emitChange(container, input, value, extra) {
    var detail = Object.assign(
      {
        value: value,
        input: input,
        toggle: container,
      },
      extra || {}
    );
    try {
      container.dispatchEvent(
        new CustomEvent(EVENT_NAME, { bubbles: true, detail: detail })
      );
    } catch (e) {
      /* ignore */
    }
  }

  function syncOptionGroup(container) {
    var input = resolveInput(container);
    if (!input) return;

    var options = qsa('[data-cv-state-option]', container);
    if (!options.length) return;

    var current = readValue(input);

    options.forEach(function (option) {
      var value = option.getAttribute('data-value');
      if (value == null) value = option.dataset.value || '';
      var active = String(value) === String(current);
      option.classList.toggle('is-active', active);
      option.classList.toggle('is-success', active);
      option.classList.toggle('is-danger', !active);
      option.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function bindOptionGroup(container) {
    var input = resolveInput(container);
    if (!input) return;

    var options = qsa('[data-cv-state-option]', container);
    if (!options.length) return;

    function setValue(value, fromUser) {
      writeValue(input, value);
      syncOptionGroup(container);
      emitChange(container, input, readValue(input), { fromUser: !!fromUser });
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    options.forEach(function (option) {
      option.addEventListener('click', function (event) {
        event.preventDefault();
        var value = option.getAttribute('data-value');
        if (value == null) value = option.dataset.value || '';
        setValue(value, true);
      });
      option.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        option.click();
      });
    });

    input.addEventListener('change', function () {
      syncOptionGroup(container);
    });

    syncOptionGroup(container);
  }

  function findBinaryTrigger(container) {
    return (
      container.querySelector('[data-cv-state-trigger]') ||
      container.querySelector('[data-cv-state-option]') ||
      container.querySelector('[data-rg-toggle]') ||
      container.querySelector('[data-motorista-fixo-toggle]')
    );
  }

  function syncBinaryButton(container, input, trigger) {
    if (!input || !trigger) return;

    var active = input.type === 'checkbox' ? input.checked : readValue(input) === 'true';

    trigger.classList.toggle('is-active', active);
    trigger.classList.toggle('is-inactive', !active);
    trigger.classList.toggle('cv-field-side-action--success', active);
    trigger.classList.toggle('cv-field-side-action--danger', !active);
    trigger.setAttribute('aria-pressed', active ? 'true' : 'false');

    var labelEl = trigger.querySelector('span:last-child');
    var activeLabel =
      trigger.getAttribute('data-active-label') ||
      trigger.dataset.rgLabelActive ||
      trigger.dataset.mfLabelActive ||
      container.getAttribute('data-active-label') ||
      '';
    var inactiveLabel =
      trigger.getAttribute('data-inactive-label') ||
      trigger.dataset.rgLabelInactive ||
      trigger.dataset.mfLabelInactive ||
      container.getAttribute('data-inactive-label') ||
      '';

    if (labelEl && (activeLabel || inactiveLabel)) {
      labelEl.textContent = active ? activeLabel || labelEl.textContent : inactiveLabel || labelEl.textContent;
    }
  }

  function bindBinary(container) {
    var input = resolveInput(container);
    var trigger = findBinaryTrigger(container);
    if (!input || !trigger) return;

    function sync(fromUser) {
      syncBinaryButton(container, input, trigger);
      emitChange(container, input, readValue(input), { fromUser: !!fromUser });
    }

    trigger.addEventListener('click', function (event) {
      event.preventDefault();
      if (input.type === 'checkbox') {
        input.checked = !input.checked;
      } else {
        var on = readValue(input) === 'true';
        writeValue(input, on ? 'false' : 'true');
      }
      input.dispatchEvent(new Event('change', { bubbles: true }));
      sync(true);
    });

    input.addEventListener('change', function () {
      sync(false);
    });

    sync(false);
  }

  function initContainer(container) {
    if (!container || container.getAttribute(BOUND) === 'true') return;
    container.setAttribute(BOUND, 'true');

    var isBinary =
      container.hasAttribute('data-cv-state-binary') ||
      container.querySelector('[data-rg-toggle]') ||
      container.querySelector('[data-motorista-fixo-toggle]');

    if (isBinary && !qsa('[data-cv-state-option]', container).length) {
      bindBinary(container);
      return;
    }

    if (qsa('[data-cv-state-option]', container).length) {
      bindOptionGroup(container);
      return;
    }

    if (isBinary) {
      bindBinary(container);
    }
  }

  function init(root) {
    var scope = root && root.querySelectorAll ? root : document;
    if (!scope || !scope.querySelectorAll) return;

    if (scope.matches && scope.matches('[data-cv-state-toggle]')) {
      initContainer(scope);
    }

    qsa('[data-cv-state-toggle]', scope).forEach(initContainer);
  }

  function update(group, value) {
    if (!group) return;
    var input = resolveInput(group);
    if (!input) return;
    writeValue(input, value);
    if (group.hasAttribute('data-cv-state-binary') || findBinaryTrigger(group)) {
      syncBinaryButton(group, input, findBinaryTrigger(group));
    } else {
      syncOptionGroup(group);
    }
    emitChange(group, input, readValue(group), { fromUser: false });
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  window.CV = window.CV || {};
  window.CV.stateToggle = {
    init: init,
    update: update,
  };

  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('stateToggle', init);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(document); });
  } else {
    init(document);
  }
})();
