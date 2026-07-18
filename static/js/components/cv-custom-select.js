/* ==========================================================================
   cv-custom-select.js
   Custom Select Premium — dropdown 100% customizado, sem menu nativo.
   O <select> nativo permanece oculto para submissão do formulário.

   Uso:
     <div class="cv-custom-select" data-cv-select>
       <select name="campo">
         <option value="">Selecione</option>
         <option value="1">Opção 1</option>
       </select>
     </div>

   Modificadores CSS:
     .cv-custom-select--sm / --lg / --disabled / --error

   Multi-select: adicione o atributo `multiple` no <select> nativo e, se quiser,
   `data-placeholder="Texto"` na div wrapper para o texto exibido quando nada
   estiver selecionado. Cliques em opções alternam a seleção sem fechar o menu.
   ========================================================================== */

(function () {
  'use strict';

  var uid = 0;

  function nextId() {
    return 'cv-cs-' + (++uid);
  }

  function svgChevron() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
  }

  function svgCheck() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Constructor
  // ─────────────────────────────────────────────────────────────────────────
  function CustomSelect(root) {
    this.root     = root;
    this.native   = root.querySelector('select');
    this.trigger  = null;
    this.menu     = null;
    this._items   = [];
    this._focused = -1;
    this._isOpen  = false;
    this._id      = nextId();

    if (!this.native) return;
    this._init();
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Init
  // ─────────────────────────────────────────────────────────────────────────
  CustomSelect.prototype._init = function () {
    var self   = this;
    var native = this.native;

    this.root.classList.add('cv-custom-select--v2');

    // 1. Ocultar native select (mantido no DOM para form submit)
    native.classList.add('cv-custom-select__native');
    native.setAttribute('aria-hidden', 'true');
    native.setAttribute('tabindex', '-1');

    // 2. Associar label ao trigger (transfere o for="id" do label)
    var nativeId = native.id;
    var labelEl  = nativeId ? document.querySelector('label[for="' + nativeId + '"]') : null;
    var triggerId = this._id + '-trigger';

    if (labelEl) {
      if (!labelEl.id) labelEl.id = this._id + '-label';
      // Label agora aponta para o trigger
      labelEl.setAttribute('for', triggerId);
    }

    // 3. Construir trigger
    var trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.id   = triggerId;
    trigger.className = 'cv-custom-select__trigger cv-custom-select__trigger--v2';
    trigger.setAttribute('role', 'combobox');
    trigger.setAttribute('aria-haspopup', 'listbox');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-controls', this._id + '-menu');
    if (labelEl) trigger.setAttribute('aria-labelledby', labelEl.id);
    if (native.disabled) {
      trigger.disabled = true;
      this.root.classList.add('cv-custom-select--disabled');
    }

    var valSpan  = document.createElement('span');
    valSpan.className = 'cv-custom-select__value';

    var chevSpan = document.createElement('span');
    chevSpan.className = 'cv-custom-select__chevron';
    chevSpan.setAttribute('aria-hidden', 'true');
    chevSpan.innerHTML = svgChevron();

    trigger.appendChild(valSpan);
    trigger.appendChild(chevSpan);
    this.trigger = trigger;

    // 4. Construir menu
    var menu = document.createElement('ul');
    menu.id        = this._id + '-menu';
    menu.className = 'cv-custom-select__menu cv-custom-select__menu--v2';
    menu.setAttribute('role', 'listbox');
    if (native.multiple) menu.setAttribute('aria-multiselectable', 'true');
    menu.hidden = true;

    var opts = Array.prototype.slice.call(native.options);
    opts.forEach(function (opt, i) {
      var li  = document.createElement('li');
      var itemId = self._id + '-opt-' + i;
      li.id        = itemId;
      li.className = 'cv-custom-select__option';
      li.setAttribute('role', 'option');
      li.setAttribute('data-value', opt.value);
      li.setAttribute('aria-selected', 'false');

      if (opt.disabled) {
        li.classList.add('cv-custom-select__option--disabled');
        li.setAttribute('aria-disabled', 'true');
      }

      var check = document.createElement('span');
      check.className = 'cv-custom-select__option-check';
      check.setAttribute('aria-hidden', 'true');
      check.innerHTML = svgCheck();

      var label = document.createElement('span');
      label.className = 'cv-custom-select__option-label';
      label.textContent = opt.text;

      li.appendChild(check);
      li.appendChild(label);
      menu.appendChild(li);

      self._items.push({
        el:       li,
        value:    opt.value,
        label:    opt.text,
        disabled: opt.disabled
      });
    });

    this.menu = menu;

    // 5. Montar na DOM
    this.root.appendChild(trigger);
    this.root.appendChild(menu);

    this._floatingMenu =
      window.CvFloatingDropdown && window.CvFloatingDropdown.attach
        ? window.CvFloatingDropdown.attach(menu, trigger)
        : null;
    if (this._floatingMenu) this.root.classList.add('cv-custom-select--menu-portal');

    // 6. Valor inicial
    this._syncFromNative();

    // 7. Eventos
    this._bindEvents();
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Sync display from native select value
  // ─────────────────────────────────────────────────────────────────────────
  CustomSelect.prototype._syncFromNative = function () {
    var native   = this.native;
    var valSpan  = this.trigger.querySelector('.cv-custom-select__value');

    this._items.forEach(function (item) {
      item.el.classList.remove('cv-custom-select__option--selected');
      item.el.setAttribute('aria-selected', 'false');
    });

    if (native.multiple) {
      var selected = Array.prototype.filter.call(native.options, function (o) { return o.selected; });
      if (selected.length) {
        valSpan.textContent = selected.map(function (o) { return o.text; }).join(', ');
        valSpan.classList.remove('cv-custom-select__value--placeholder');
      } else {
        valSpan.textContent = native.getAttribute('data-placeholder') || this.root.getAttribute('data-placeholder') || '';
        valSpan.classList.add('cv-custom-select__value--placeholder');
      }
      for (var s = 0; s < selected.length; s++) {
        for (var i = 0; i < this._items.length; i++) {
          if (this._items[i].value === selected[s].value) {
            this._items[i].el.classList.add('cv-custom-select__option--selected');
            this._items[i].el.setAttribute('aria-selected', 'true');
          }
        }
      }
      return;
    }

    var sel = native.options[native.selectedIndex];

    if (sel) {
      valSpan.textContent = sel.text;
      if (!sel.value || sel.value === '') {
        valSpan.classList.add('cv-custom-select__value--placeholder');
      } else {
        valSpan.classList.remove('cv-custom-select__value--placeholder');
        // Marcar opção selecionada no menu
        for (var i = 0; i < this._items.length; i++) {
          if (this._items[i].value === sel.value) {
            this._items[i].el.classList.add('cv-custom-select__option--selected');
            this._items[i].el.setAttribute('aria-selected', 'true');
            break;
          }
        }
      }
    } else {
      valSpan.textContent = '';
      valSpan.classList.add('cv-custom-select__value--placeholder');
    }
  };

  // Re-sincroniza o display a partir do valor atual do <select> nativo.
  // Útil quando o valor é alterado por código sem disparar "change" (ex.: init
  // do coordenador que preenche o cargo do servidor em modo silencioso).
  CustomSelect.prototype.refresh = function () {
    this._syncFromNative();
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Open / Close
  // ─────────────────────────────────────────────────────────────────────────
  CustomSelect.prototype._open = function () {
    if (this._isOpen || this.trigger.disabled) return;

    // Fechar outros selects abertos na página
    var openEls = document.querySelectorAll('.cv-custom-select--open');
    for (var i = 0; i < openEls.length; i++) {
      if (openEls[i]._cvSelect) openEls[i]._cvSelect._close();
    }

    this._isOpen = true;
    this.root.classList.add('cv-custom-select--open');
    this.menu.hidden = false;
    this.trigger.setAttribute('aria-expanded', 'true');
    if (this._floatingMenu) this._floatingMenu.open();

    // Focar opção selecionada ou a primeira disponível
    var startIdx = -1;
    for (var j = 0; j < this._items.length; j++) {
      if (this._items[j].el.classList.contains('cv-custom-select__option--selected')) {
        startIdx = j;
        break;
      }
    }
    this._setFocus(startIdx >= 0 ? startIdx : this._firstFocusable());
  };

  CustomSelect.prototype._close = function () {
    if (!this._isOpen) return;
    this._isOpen = false;
    this.root.classList.remove('cv-custom-select--open');
    this.menu.hidden = true;
    this.trigger.setAttribute('aria-expanded', 'false');
    this.trigger.removeAttribute('aria-activedescendant');
    if (this._floatingMenu) this._floatingMenu.close();
    this._clearFocus();
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Select option
  // ─────────────────────────────────────────────────────────────────────────
  CustomSelect.prototype._select = function (index) {
    var item = this._items[index];
    if (!item || item.disabled) return;

    if (this.native.multiple) {
      this.native.options[index].selected = !this.native.options[index].selected;
    } else {
      this.native.value = item.value;
    }

    // Disparar change no select nativo (compatível com frameworks)
    if (typeof Event !== 'undefined') {
      try {
        this.native.dispatchEvent(new Event('change', { bubbles: true }));
      } catch (e) {
        var ev = document.createEvent('Event');
        ev.initEvent('change', true, true);
        this.native.dispatchEvent(ev);
      }
    }

    this._syncFromNative();

    if (!this.native.multiple) {
      this._close();
      this.trigger.focus();
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Focus management
  // ─────────────────────────────────────────────────────────────────────────
  CustomSelect.prototype._setFocus = function (index) {
    if (this._focused >= 0 && this._items[this._focused]) {
      this._items[this._focused].el.classList.remove('cv-custom-select__option--focused');
    }
    this._focused = index;
    if (index >= 0 && this._items[index]) {
      var item = this._items[index];
      item.el.classList.add('cv-custom-select__option--focused');
      item.el.scrollIntoView({ block: 'nearest' });
      this.trigger.setAttribute('aria-activedescendant', item.el.id);
    }
  };

  CustomSelect.prototype._clearFocus = function () {
    if (this._focused >= 0 && this._items[this._focused]) {
      this._items[this._focused].el.classList.remove('cv-custom-select__option--focused');
    }
    this._focused = -1;
    this.trigger.removeAttribute('aria-activedescendant');
  };

  CustomSelect.prototype._firstFocusable = function () {
    for (var i = 0; i < this._items.length; i++) {
      if (!this._items[i].disabled) return i;
    }
    return 0;
  };

  CustomSelect.prototype._moveFocus = function (dir) {
    var len   = this._items.length;
    var start = this._focused >= 0 ? this._focused : (dir > 0 ? -1 : len);
    var idx   = start;
    for (var i = 0; i < len; i++) {
      idx = (idx + dir + len) % len;
      if (!this._items[idx].disabled) {
        this._setFocus(idx);
        return;
      }
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Events
  // ─────────────────────────────────────────────────────────────────────────
  CustomSelect.prototype._bindEvents = function () {
    var self = this;

    // Trigger — clique
    this.trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      if (self._isOpen) { self._close(); } else { self._open(); }
    });

    // Trigger — teclado
    this.trigger.addEventListener('keydown', function (e) {
      switch (e.key) {
        case 'Enter':
        case ' ':
          e.preventDefault();
          if (self._isOpen) {
            if (self._focused >= 0) self._select(self._focused);
          } else {
            self._open();
          }
          break;
        case 'ArrowDown':
          e.preventDefault();
          if (!self._isOpen) { self._open(); }
          else { self._moveFocus(1); }
          break;
        case 'ArrowUp':
          e.preventDefault();
          if (!self._isOpen) { self._open(); }
          else { self._moveFocus(-1); }
          break;
        case 'Home':
          if (self._isOpen) { e.preventDefault(); self._setFocus(self._firstFocusable()); }
          break;
        case 'End':
          if (self._isOpen) {
            e.preventDefault();
            for (var i = self._items.length - 1; i >= 0; i--) {
              if (!self._items[i].disabled) { self._setFocus(i); break; }
            }
          }
          break;
        case 'Escape':
          e.preventDefault();
          self._close();
          break;
        case 'Tab':
          self._close();
          break;
      }
    });

    // Menu — clique em opção
    this.menu.addEventListener('click', function (e) {
      var optEl = e.target;
      while (optEl && optEl !== self.menu) {
        if (optEl.getAttribute('role') === 'option') break;
        optEl = optEl.parentElement;
      }
      if (!optEl || optEl === self.menu) return;
      var idx = -1;
      for (var i = 0; i < self._items.length; i++) {
        if (self._items[i].el === optEl) { idx = i; break; }
      }
      if (idx >= 0) self._select(idx);
    });

    this.native.addEventListener('change', function () {
      self._syncFromNative();
    });

    // O hover pertence ao ponteiro e dura somente enquanto ele estiver sobre a
    // opção. Ao entrar no menu, removemos o foco visual criado pelo teclado;
    // o CSS :hover assume o destaque sem deixar estado preso no JavaScript.
    this.menu.addEventListener('mouseenter', function () {
      self._clearFocus();
    });

    // Clique fora → fechar (o menu pode estar "flutuando" no body via
    // CvFloatingDropdown, entao um clique nele nao conta como "fora").
    document.addEventListener('click', function (e) {
      if (self._isOpen && !self.root.contains(e.target) && !self.menu.contains(e.target)) {
        self._close();
      }
    });
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Init global
  // ─────────────────────────────────────────────────────────────────────────
  function initAll(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var els = [];
    if (scope.matches && scope.matches('[data-cv-select]')) els.push(scope);
    els = els.concat(Array.prototype.slice.call(scope.querySelectorAll('[data-cv-select]')));
    for (var i = 0; i < els.length; i++) {
      if (!els[i]._cvSelect) {
        els[i].setAttribute('data-cv-select-bound', 'true');
        var inst = new CustomSelect(els[i]);
        els[i]._cvSelect = inst;
      }
    }
  }

  window.CvCustomSelect = { init: initAll, CustomSelect: CustomSelect };
  window.CV = window.CV || {};
  window.CV.customSelect = window.CvCustomSelect;
  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('customSelect', initAll);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { initAll(document); });
  } else {
    initAll(document);
  }
}());
