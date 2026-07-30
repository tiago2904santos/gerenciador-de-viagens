/* ==========================================================================
   cv-select.js
   Sistema global de dropdown / action menu / filter dropdown
   Central de Viagens 3.0

   Componentes ativados por data-attributes:
     [data-cv-dropdown]         — wrapper do action dropdown
     [data-cv-dropdown-trigger] — botao que abre/fecha o menu
     [data-cv-dropdown-menu]    — menu flutuante de acoes

     [data-cv-filter-dropdown]         — wrapper do filter dropdown
     [data-cv-filter-dropdown-trigger] — botao que abre/fecha
     [data-cv-filter-dropdown-menu]    — menu flutuante de filtros
     [data-cv-filter-dropdown-option]  — opcao selecionavel

   Nenhum codigo especifico de pagina aqui — tudo via data-attrs.
   ========================================================================== */

(function () {
  'use strict';

  /* ─────────────────────────────────────────────────────────────────────────
     Utilitarios
     ───────────────────────────────────────────────────────────────────────── */

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function matching(selector, root) {
    var scope = root && root.querySelectorAll ? root : document;
    var nodes = qsa(selector, scope);
    if (scope.matches && scope.matches(selector)) nodes.unshift(scope);
    return nodes;
  }

  /* ─────────────────────────────────────────────────────────────────────────
     Fechar todos os dropdowns abertos (exceto um)
     ───────────────────────────────────────────────────────────────────────── */

  function closeAllDropdowns(except) {
    qsa('[data-cv-dropdown], [data-cv-filter-dropdown]').forEach(function (wrapper) {
      if (wrapper === except) return;
      setDropdownOpen(wrapper, false);
    });
  }

  function setDropdownOpen(wrapper, open) {
    var trigger = qs('[data-cv-dropdown-trigger], [data-cv-filter-dropdown-trigger]', wrapper);
    var menu    = qs('[data-cv-dropdown-menu], [data-cv-filter-dropdown-menu]', wrapper);

    if (!trigger || !menu) return;

    wrapper.classList.toggle('cv-action-dropdown--open', open);
    wrapper.classList.toggle('cv-filter-dropdown--open', open);
    trigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    menu.hidden = !open;

    if (open) {
      // Foco no primeiro item focavel do menu
      var firstItem = qs('button:not(:disabled), a:not([disabled]), [tabindex="0"]', menu);
      if (firstItem) {
        setTimeout(function () { firstItem.focus(); }, 16);
      }
      // Ajusta posicao se sair da tela
      _repositionMenu(wrapper, menu);
    }
  }

  function isDropdownOpen(wrapper) {
    return wrapper.classList.contains('cv-action-dropdown--open') ||
           wrapper.classList.contains('cv-filter-dropdown--open');
  }

  /* ─────────────────────────────────────────────────────────────────────────
     Reposicionar menu se sair da viewport
     ───────────────────────────────────────────────────────────────────────── */

  function _repositionMenu(wrapper, menu) {
    menu.classList.remove('cv-action-dropdown__menu--up', 'cv-action-dropdown__menu--left');
    var rect    = menu.getBoundingClientRect();
    var vpH     = window.innerHeight || document.documentElement.clientHeight;
    var vpW     = window.innerWidth  || document.documentElement.clientWidth;

    if (rect.bottom > vpH && rect.top > vpH / 2) {
      menu.classList.add('cv-action-dropdown__menu--up');
    }
    if (rect.right > vpW) {
      menu.classList.add('cv-action-dropdown__menu--left');
    }
  }

  /* ─────────────────────────────────────────────────────────────────────────
     Navegacao por teclado dentro de um menu
     ───────────────────────────────────────────────────────────────────────── */

  function handleMenuKeydown(e, wrapper, menu) {
    var items = qsa(
      'button:not(:disabled), a:not([disabled]), [tabindex="0"]',
      menu
    ).filter(function (el) { return !el.hidden; });

    if (!items.length) return;

    var idx = items.indexOf(document.activeElement);

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        items[Math.min(idx + 1, items.length - 1)].focus();
        break;
      case 'ArrowUp':
        e.preventDefault();
        items[Math.max(idx - 1, 0)].focus();
        break;
      case 'Home':
        e.preventDefault();
        items[0].focus();
        break;
      case 'End':
        e.preventDefault();
        items[items.length - 1].focus();
        break;
      case 'Tab':
        setDropdownOpen(wrapper, false);
        break;
      case 'Escape':
        e.preventDefault();
        setDropdownOpen(wrapper, false);
        var trigger = qs('[data-cv-dropdown-trigger], [data-cv-filter-dropdown-trigger]', wrapper);
        if (trigger) trigger.focus();
        break;
    }
  }

  /* ─────────────────────────────────────────────────────────────────────────
     Action Dropdown — [data-cv-dropdown]
     ───────────────────────────────────────────────────────────────────────── */

  function initCvDropdowns(root) {
    matching('[data-cv-dropdown]', root).forEach(function (wrapper) {
      if (wrapper._cvDropdownReady) return;
      wrapper._cvDropdownReady = true;

      var trigger = qs('[data-cv-dropdown-trigger]', wrapper);
      var menu    = qs('[data-cv-dropdown-menu]', wrapper);

      if (!trigger || !menu) return;

      // ARIA inicial
      var menuId = menu.id || ('cv-dd-menu-' + (++_uid));
      menu.id = menuId;
      trigger.setAttribute('aria-haspopup', 'true');
      trigger.setAttribute('aria-expanded', 'false');
      trigger.setAttribute('aria-controls', menuId);
      menu.hidden = true;

      // Clique no trigger
      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = isDropdownOpen(wrapper);
        closeAllDropdowns(open ? null : wrapper);
        if (!open) setDropdownOpen(wrapper, true);
      });

      // Teclado no trigger
      trigger.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
          if (!isDropdownOpen(wrapper)) {
            e.preventDefault();
            closeAllDropdowns(wrapper);
            setDropdownOpen(wrapper, true);
          }
        }
        if (e.key === 'Escape') {
          setDropdownOpen(wrapper, false);
        }
      });

      // Teclado no menu
      menu.addEventListener('keydown', function (e) {
        handleMenuKeydown(e, wrapper, menu);
      });
    });
  }

  /* ─────────────────────────────────────────────────────────────────────────
     Filter Dropdown — [data-cv-filter-dropdown]
     Opcoes com checkmark. Dispara evento 'cv:filter-change' no wrapper
     com { name, values } para integracao com outros sistemas de filtro.
     ───────────────────────────────────────────────────────────────────────── */

  function initCvFilterDropdowns(root) {
    matching('[data-cv-filter-dropdown]', root).forEach(function (wrapper) {
      if (wrapper._cvFilterDropdownReady) return;
      wrapper._cvFilterDropdownReady = true;

      var trigger = qs('[data-cv-filter-dropdown-trigger]', wrapper);
      var menu    = qs('[data-cv-filter-dropdown-menu]', wrapper);
      var badge   = qs('.cv-filter-dropdown__trigger-badge', wrapper);

      if (!trigger || !menu) return;

      // ARIA inicial
      var menuId = menu.id || ('cv-fd-menu-' + (++_uid));
      menu.id = menuId;
      trigger.setAttribute('aria-haspopup', 'listbox');
      trigger.setAttribute('aria-expanded', 'false');
      trigger.setAttribute('aria-controls', menuId);
      menu.hidden = true;

      var filterName = wrapper.dataset.cvFilterDropdown || '';

      function getSelectedValues() {
        return qsa('[data-cv-filter-dropdown-option]', menu)
          .filter(function (o) { return o.dataset.selected === 'true'; })
          .map(function (o) { return o.dataset.value || o.textContent.trim(); });
      }

      function updateBadge() {
        var count = getSelectedValues().length;
        if (badge) {
          badge.textContent = count > 0 ? String(count) : '';
          badge.hidden = count === 0;
        }
      }

      function dispatchChange() {
        var event = new CustomEvent('cv:filter-change', {
          bubbles: true,
          detail: { name: filterName, values: getSelectedValues() }
        });
        wrapper.dispatchEvent(event);
      }

      // Inicializar opcoes
      qsa('[data-cv-filter-dropdown-option]', menu).forEach(function (option) {
        var selected = option.dataset.selected === 'true';
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', selected ? 'true' : 'false');
        option.classList.toggle('cv-filter-dropdown__option--selected', selected);

        option.addEventListener('click', function () {
          var isSelected = option.dataset.selected === 'true';
          option.dataset.selected = isSelected ? 'false' : 'true';
          option.setAttribute('aria-selected', isSelected ? 'false' : 'true');
          option.classList.toggle('cv-filter-dropdown__option--selected', !isSelected);
          updateBadge();
          dispatchChange();
        });
      });

      updateBadge();

      // Clique no trigger
      trigger.addEventListener('click', function (e) {
        e.stopPropagation();
        var open = isDropdownOpen(wrapper);
        closeAllDropdowns(open ? null : wrapper);
        if (!open) setDropdownOpen(wrapper, true);
      });

      // Teclado
      trigger.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
          if (!isDropdownOpen(wrapper)) {
            e.preventDefault();
            closeAllDropdowns(wrapper);
            setDropdownOpen(wrapper, true);
          }
        }
      });

      menu.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          var focused = document.activeElement;
          if (focused && menu.contains(focused) && focused.hasAttribute('data-cv-filter-dropdown-option')) {
            e.preventDefault();
            focused.click();
            return;
          }
        }
        handleMenuKeydown(e, wrapper, menu);
      });
    });
  }

  /* ─────────────────────────────────────────────────────────────────────────
     Contador de UID para IDs unicos
     ───────────────────────────────────────────────────────────────────────── */

  var _uid = 0;

  /* ─────────────────────────────────────────────────────────────────────────
     Fechar ao clicar fora
     ───────────────────────────────────────────────────────────────────────── */

  document.addEventListener('click', function (e) {
    if (!e.target.closest('[data-cv-dropdown], [data-cv-filter-dropdown]')) {
      closeAllDropdowns();
    }
  });

  /* ─────────────────────────────────────────────────────────────────────────
     Fechar com ESC (nivel documento)
     ───────────────────────────────────────────────────────────────────────── */

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      closeAllDropdowns();
    }
  });

  /* ─────────────────────────────────────────────────────────────────────────
     Inicializacao
     ───────────────────────────────────────────────────────────────────────── */

  function init(root) {
    var scope = root && root.querySelectorAll ? root : document;
    initCvDropdowns(scope);
    initCvFilterDropdowns(scope);
  }

  window.CV = window.CV || {};
  window.CV.dropdowns = {
    init: init,
    initDropdowns: initCvDropdowns,
    initFilterDropdowns: initCvFilterDropdowns,
    closeAll: closeAllDropdowns
  };
  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('dropdowns', init);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(document); });
  } else {
    init(document);
  }

}());
