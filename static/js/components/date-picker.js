(function () {
  'use strict';

  var SELECTOR = '[data-cv-date-picker]';
  /* JS-02 — uma entrada por date picker vivo: { root, desmontar }. */
  var instancias = [];
  var MONTHS = [
    'Janeiro',
    'Fevereiro',
    'Março',
    'Abril',
    'Maio',
    'Junho',
    'Julho',
    'Agosto',
    'Setembro',
    'Outubro',
    'Novembro',
    'Dezembro',
  ];
  var WEEKDAYS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'];

  function pad2(value) {
    return value < 10 ? '0' + value : String(value);
  }

  function cloneDate(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12, 0, 0, 0);
  }

  function parseDisplayDate(value) {
    if (!value) return null;
    var match = String(value).trim().match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!match) return null;
    var day = parseInt(match[1], 10);
    var month = parseInt(match[2], 10) - 1;
    var year = parseInt(match[3], 10);
    var date = new Date(year, month, day, 12, 0, 0, 0);

    if (
      date.getFullYear() !== year ||
      date.getMonth() !== month ||
      date.getDate() !== day
    ) {
      return null;
    }

    return date;
  }

  function parseIsoDate(value) {
    if (!value) return null;
    var match = String(value).trim().match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return null;
    var year = parseInt(match[1], 10);
    var month = parseInt(match[2], 10) - 1;
    var day = parseInt(match[3], 10);
    var date = new Date(year, month, day, 12, 0, 0, 0);

    if (
      date.getFullYear() !== year ||
      date.getMonth() !== month ||
      date.getDate() !== day
    ) {
      return null;
    }

    return date;
  }

  function formatDisplayDate(date) {
    return [pad2(date.getDate()), pad2(date.getMonth() + 1), date.getFullYear()].join('/');
  }

  function formatCompactDisplayDate(date) {
    return [pad2(date.getDate()), pad2(date.getMonth() + 1)].join('/');
  }

  function formatIsoDate(date) {
    return [
      date.getFullYear(),
      pad2(date.getMonth() + 1),
      pad2(date.getDate()),
    ].join('-');
  }

  function formatMonthLabel(date) {
    return MONTHS[date.getMonth()] + ' ' + date.getFullYear();
  }

  function formatLongDate(date) {
    return date.toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
    });
  }

  function addDays(date, days) {
    var next = cloneDate(date);
    next.setDate(next.getDate() + days);
    return next;
  }

  function addMonths(date, months) {
    return new Date(date.getFullYear(), date.getMonth() + months, 1, 12, 0, 0, 0);
  }

  function startOfMonth(date) {
    return new Date(date.getFullYear(), date.getMonth(), 1, 12, 0, 0, 0);
  }

  function startOfWeekMonday(date) {
    var base = cloneDate(date);
    var day = base.getDay(); // 0 = domingo
    var offset = day === 0 ? 6 : day - 1;
    base.setDate(base.getDate() - offset);
    return base;
  }

  function isSameDay(a, b) {
    return !!a && !!b &&
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth() &&
      a.getDate() === b.getDate();
  }

  function isSameMonth(a, b) {
    return !!a && !!b &&
      a.getFullYear() === b.getFullYear() &&
      a.getMonth() === b.getMonth();
  }

  function isBeforeDay(a, b) {
    if (!a || !b) return false;
    return a.getTime() < b.getTime();
  }

  function isAfterDay(a, b) {
    if (!a || !b) return false;
    return a.getTime() > b.getTime();
  }

  function dispatchChange(input) {
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function setValueAndNotify(input, value) {
    if (!input) return;
    if (input.value !== value) {
      input.value = value;
      dispatchChange(input);
    }
  }

  function getInitialDate(root, input, fallback) {
    return (
      parseIsoDate(input && input.value) ||
      parseDisplayDate(input && input.value) ||
      parseIsoDate(root.dataset.initialDate) ||
      parseDisplayDate(root.dataset.initialDate) ||
      fallback
    );
  }

  function initPicker(root) {
    if (!root || root.dataset.cvDatePickerReady === 'true') return;
    root.dataset.cvDatePickerReady = 'true';

    var mode = root.dataset.mode === 'range' ? 'range' : root.dataset.mode === 'multi' ? 'multi' : 'single';
    // Multi sequencial (roteiro): cada clique preenche o proximo trecho, a mesma data pode se
    // repetir (sair e chegar no mesmo dia, ida e volta no mesmo dia) e o clique nao remove.
    var multiSequential = mode === 'multi' && root.dataset.allowRepeatDates === 'true';
    var triggers = Array.prototype.slice.call(root.querySelectorAll('[data-cv-date-picker-trigger]'));
    var trigger = triggers[0];
    var display = root.querySelector('[data-cv-date-picker-display]');
    var panel = root.querySelector('[data-cv-date-picker-panel]');
    var monthLabel = root.querySelector('[data-cv-date-picker-month]');
    var weekdays = root.querySelector('[data-cv-date-picker-weekdays]');
    var days = root.querySelector('[data-cv-date-picker-days]');
    var prev = root.querySelector('[data-cv-date-picker-prev]');
    var next = root.querySelector('[data-cv-date-picker-next]');
    var clear = root.querySelector('[data-cv-date-picker-clear]');
    var today = root.querySelector('[data-cv-date-picker-today]');
    var startHidden = root.querySelector('[data-cv-date-picker-start-value]');
    var endHidden = root.querySelector('[data-cv-date-picker-end-value]');
    var singleHidden = root.querySelector('[data-cv-date-picker-value]');
    var startLabel = root.querySelector('[data-cv-date-picker-start-label]');
    var endLabel = root.querySelector('[data-cv-date-picker-end-label]');
    var displayText = root.querySelector('[data-cv-date-picker-display-text]');
    var summary = root.querySelector('[data-cv-date-picker-summary]');
    var startDisplay = root.querySelector('[data-cv-date-picker-start-display]');
    var endDisplay = root.querySelector('[data-cv-date-picker-end-display]');
    var context = root.querySelector('[data-cv-date-picker-context]');
    var contextStep = root.querySelector('[data-cv-date-picker-context-step]');
    var contextRoute = root.querySelector('[data-cv-date-picker-context-route]');
    var activeDate = new Date();
    var selectedSingle = null;
    var selectedStart = null;
    var selectedEnd = null;
    var selectedDates = []; // multi mode
    var routeSteps = [];
    var isOpen = false;
    var abreParaCima = false;
    var focusedDate = null;
    var dayButtons = [];
    var confirmBtn = root.querySelector('[data-cv-date-picker-confirm]');
    var undoBtn = root.querySelector('[data-cv-date-picker-undo]');

    function syncStateFromInputs() {
      if (mode === 'multi') {
        selectedDates = [];
        if (root.dataset.selectedDates) {
          try {
            selectedDates = JSON.parse(root.dataset.selectedDates) || [];
          } catch (e) {
            selectedDates = String(root.dataset.selectedDates || '')
              .split(',')
              .map(function (date) { return String(date || '').trim(); })
              .filter(function (date) { return !!date; });
          }
          selectedDates = selectedDates.map(function (date) {
            return parseIsoDate(date) || parseDisplayDate(date) || null;
          }).filter(function (date) { return !!date; });
          selectedDates.sort(function (a, b) { return a.getTime() - b.getTime(); });
        }
        activeDate = startOfMonth(selectedDates[0] || new Date());
        return;
      }
      if (mode === 'single') {
        selectedSingle = getInitialDate(root, singleHidden, null);
        if (singleHidden && singleHidden.value) {
          selectedSingle = parseIsoDate(singleHidden.value) || parseDisplayDate(singleHidden.value);
        }
        if (!selectedSingle) {
          selectedSingle = getInitialDate(root, display, null);
        }
        activeDate = startOfMonth(selectedSingle || new Date());
      } else {
        selectedStart = parseIsoDate(startHidden && startHidden.value) || parseDisplayDate(startHidden && startHidden.value)
          || parseDisplayDate(startDisplay && startDisplay.value);
        selectedEnd = parseIsoDate(endHidden && endHidden.value) || parseDisplayDate(endHidden && endHidden.value)
          || parseDisplayDate(endDisplay && endDisplay.value);
        if (!selectedStart && selectedEnd) {
          selectedStart = selectedEnd;
          selectedEnd = null;
        } else if (selectedStart && selectedEnd && isBeforeDay(selectedEnd, selectedStart)) {
          var tmp = selectedStart;
          selectedStart = selectedEnd;
          selectedEnd = tmp;
        }
        activeDate = startOfMonth(selectedStart || selectedEnd || new Date());
      }
    }

    function readRouteSteps() {
      if (mode !== 'multi') return [];
      var raw = root.dataset.routeSteps || '';
      if (!raw) return [];
      try {
        var parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) return [];
        return parsed.map(function (step) {
          return {
            from: String(step && step.from ? step.from : '').trim(),
            to: String(step && step.to ? step.to : '').trim(),
            label: String(step && step.label ? step.label : '').trim(),
          };
        }).filter(function (step) {
          return !!step.label;
        });
      } catch (e) {
        return [];
      }
    }

    function renderRouteContext() {
      if (!context || mode !== 'multi') return;
      routeSteps = readRouteSteps();
      if (!routeSteps.length) {
        context.hidden = true;
        if (contextStep) contextStep.textContent = '';
        if (contextRoute) contextRoute.textContent = '';
        return;
      }

      var totalSteps = routeSteps.length;
      var currentStepIndex = Math.min(selectedDates.length, totalSteps - 1);
      var currentStepNumber = Math.min(selectedDates.length + 1, totalSteps);
      var currentStep = routeSteps[currentStepIndex] || routeSteps[0];

      context.hidden = false;
      if (contextStep) {
        /* "Trecho 1:", e nao "Trecho 1 de 4": o total ja se le no calendario,
         * pelas datas que voltam marcadas, e a faixa existe para dizer de QUEM
         * e a data que ele esta pedindo agora. */
        contextStep.textContent = 'Trecho ' + currentStepNumber + ':';
      }
      if (contextRoute) {
        contextRoute.textContent = currentStep.label || ((currentStep.from || '') + ' > ' + (currentStep.to || ''));
      }
    }


    function positionPanel(recalcularLado) {
      if (panel.parentElement !== document.body) {
        /* O painel vai para o `body` e perde os ancestrais — com eles some a
         * única forma de o CSS saber de que campo ele veio. Como o partial do
         * calendário é o mesmo nas telas migradas e nas legadas, sem essa marca
         * qualquer regra nova alcançaria as duas. Ela é copiada da raiz v2
         * (`.date-field`) na hora do transplante. */
        if (root.closest('.date-field')) {
          panel.classList.add('date-field__panel');
        }
        document.body.appendChild(panel);
      }
      var anchor = startDisplay || trigger;
      var rect = anchor.getBoundingClientRect();
      var margin = 8;
      var vw = window.innerWidth || document.documentElement.clientWidth || 0;
      var vh = window.innerHeight || document.documentElement.clientHeight || 0;
      var width = 326;
      if (vw) {
        width = Math.min(width, Math.max(vw - (margin * 2), 280));
      }
      /* ABSOLUTO no documento, não fixo na janela.
       *
       * Com `fixed` o painel só acompanhava a âncora enquanto coubesse na tela;
       * quando não cabia, a conta terminava num `clamp` contra as bordas da
       * janela e ele PARAVA — a página rolava por baixo e o calendário ficava
       * boiando, cada vez mais longe do campo que o abriu. Medido no editor de
       * roteiro: 120px de rolagem moviam a âncora 120 e o painel 60.
       *
       * Em coordenadas de documento ele não precisa de trava nenhuma: anda com
       * a página porque É a página. E se for mais alto do que a janela, o que
       * passa do fim continua alcançável — basta rolar, e o painel rola junto,
       * em vez de ficar cortado num ponto fixo. */
      panel.style.position = 'absolute';
      panel.style.width = width + 'px';

      var scrollX = window.scrollX || window.pageXOffset || 0;
      var scrollY = window.scrollY || window.pageYOffset || 0;

      var left = rect.right - width;
      if (vw) {
        left = Math.min(left, vw - width - margin);
        left = Math.max(left, margin);
      }

      /* Abre para BAIXO; para cima só quando não cabe embaixo e cabe em cima. A
       * escolha é feita uma vez, na abertura (`recalcularLado`): refazê-la a
       * cada rolagem faria o painel pular de um lado do campo para o outro
       * enquanto o usuário lê. */
      var panelHeight = panel.offsetHeight || 0;
      if (recalcularLado) {
        abreParaCima = !!(vh && panelHeight)
          && (vh - (rect.bottom + 8) - margin) < panelHeight
          && (rect.top - 8 - panelHeight) > margin;
      }
      var top = abreParaCima ? (rect.top - 8 - panelHeight) : (rect.bottom + 8);

      panel.style.top = (top + scrollY) + 'px';
      panel.style.left = (left + scrollX) + 'px';
    }

    function setOpen(nextOpen) {
      isOpen = !!nextOpen;
      panel.hidden = !isOpen;
      root.classList.toggle('date-picker--open', isOpen);
      triggers.forEach(function (btn) {
        btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });
      if (isOpen) {
        positionPanel(true);
        // Garante animação mesmo com o panel fora do root (portal)
        panel.classList.remove('date-picker__panel--entering');
        void panel.offsetWidth; // force reflow
        panel.classList.add('date-picker__panel--entering');
        render();
      } else {
        panel.classList.remove('date-picker__panel--entering');
      }
    }

    function closePicker() {
      setOpen(false);
      if (!startDisplay && trigger && !trigger.hidden) {
        trigger.focus();
      }
    }

    function openPicker() {
      setOpen(true);
    }

    /* Abre o calendário a partir de um campo de exibição.
     *
     * O `focus` sozinho não serve: ele chega no `mousedown`, ANTES do `mouseup`.
     * O painel nasce embaixo do cursor, o `mouseup` cai numa célula do
     * calendário em vez de cair no campo, e o navegador — vendo alvos
     * diferentes na descida e na subida — dispara o `click` no ancestral comum,
     * o `body`. O `attachDismiss` lê isso como clique fora e fecha. Resultado:
     * o primeiro clique abria e fechava no mesmo gesto, e só o segundo pegava.
     *
     * Então quando o foco vem do ponteiro, quem abre é o `click`, depois do
     * `mouseup` — o alvo continua sendo o campo e nada fecha. Pelo teclado não
     * há ponteiro, o `focus` abre como antes e o Tab continua alcançando o
     * calendário.
     */
    function bindAbertura(display) {
      var focoVeioDoPonteiro = false;

      display.addEventListener('pointerdown', function () {
        focoVeioDoPonteiro = true;
      });
      display.addEventListener('focus', function () {
        if (focoVeioDoPonteiro) return;
        openPicker();
      });
      display.addEventListener('click', function () {
        focoVeioDoPonteiro = false;
        openPicker();
      });
      display.addEventListener('blur', function () {
        focoVeioDoPonteiro = false;
      });
    }

    function setMonth(monthDate) {
      activeDate = startOfMonth(monthDate);
      render();
    }

    function clearSelection() {
      if (mode === 'multi') {
        selectedDates = [];
        root.dataset.selectedDates = '[]';
      } else if (mode === 'single') {
        selectedSingle = null;
      } else {
        selectedStart = null;
        selectedEnd = null;
      }
      syncOutputs();
      activeDate = startOfMonth(new Date());
      render();
    }

    /** Multi sequencial: desfaz a ultima data escolhida (o clique no dia nao remove mais). */
    function undoLastMultiDate() {
      if (mode !== 'multi' || !selectedDates.length) return;
      selectedDates.pop();
      syncOutputs();
      render();
    }

    function pickDate(date) {
      var picked = cloneDate(date);

      if (mode === 'multi') {
        // Respeita o limite definido pelo atributo data-max-dates (ex: número de trechos)
        var maxDates = parseInt(root.dataset.maxDates, 10);
        var hasMaxDates = !isNaN(maxDates) && maxDates > 0;
        if (multiSequential) {
          if (hasMaxDates && selectedDates.length >= maxDates) {
            return; // já atingiu o máximo permitido
          }
          var ultimaSelecionada = selectedDates[selectedDates.length - 1];
          if (ultimaSelecionada && isBeforeDay(picked, ultimaSelecionada)) {
            return; // os trechos seguem a ordem da rota: nao pode voltar no tempo
          }
          selectedDates.push(picked);
        } else {
          var found = false;
          for (var mi = 0; mi < selectedDates.length; mi++) {
            if (isSameDay(selectedDates[mi], picked)) {
              selectedDates.splice(mi, 1);
              found = true;
              break;
            }
          }
          if (!found) {
            if (hasMaxDates && selectedDates.length >= maxDates) {
              return; // já atingiu o máximo permitido
            }
            selectedDates.push(picked);
            selectedDates.sort(function (a, b) { return a.getTime() - b.getTime(); });
          }
        }
        syncOutputs();
        var expectedMultiDates = parseInt(root.dataset.maxDates, 10);
        if (!isNaN(expectedMultiDates) && expectedMultiDates > 0 && selectedDates.length === expectedMultiDates) {
          var isoList = selectedDates.map(function (d) { return formatIsoDate(d); });
          root.dataset.selectedDates = JSON.stringify(isoList);
          root.dispatchEvent(new CustomEvent('cv:multi-confirm', {
            bubbles: true,
            detail: { dates: isoList },
          }));
          closePicker();
          return;
        }
        render();
        return;
      }

      if (mode === 'single') {
        selectedSingle = picked;
        syncOutputs();
        activeDate = startOfMonth(picked);
        render();
        closePicker();
        return;
      }

      if (!selectedStart || (selectedStart && selectedEnd)) {
        selectedStart = picked;
        selectedEnd = null;
        activeDate = startOfMonth(picked);
        syncOutputs();
        render();
        return;
      }

      if (isBeforeDay(picked, selectedStart)) {
        selectedEnd = selectedStart;
        selectedStart = picked;
      } else {
        selectedEnd = picked;
      }

      syncOutputs();
      activeDate = startOfMonth(picked);
      render();
      closePicker();
    }

    function syncOutputs() {
      if (mode !== 'multi' && context) {
        context.hidden = true;
        if (contextStep) contextStep.textContent = '';
        if (contextRoute) contextRoute.textContent = '';
      }
      if (mode === 'multi') {
        var expectedMultiDates = parseInt(root.dataset.maxDates, 10);
        var hasExpectedMultiDates = !isNaN(expectedMultiDates) && expectedMultiDates > 0;
        var multiSummary = summary;
        var multiCount = selectedDates.length;
        var multiLabel = '';

        if (multiCount > 0) {
          multiLabel = selectedDates.map(function (date, index) {
            return (index + 1) + '. ' + formatDisplayDate(date);
          }).join(' • ');
        }

        if (multiSummary) {
          if (!hasExpectedMultiDates) {
            multiSummary.textContent = multiCount
              ? multiLabel
              : 'Adicione destinos para habilitar o preenchimento das datas.';
          } else if (multiCount) {
            multiSummary.textContent = multiCount + '/' + expectedMultiDates + ' datas selecionadas'
              + (multiLabel ? ' - ' + multiLabel : '');
          } else {
            multiSummary.textContent = 'Selecione ' + expectedMultiDates + ' datas para preencher os trechos e o retorno final.';
          }
        }

        if (undoBtn) {
          undoBtn.disabled = !selectedDates.length;
        }
        if (confirmBtn) {
          var n = selectedDates.length;
          confirmBtn.textContent = n > 0
            ? 'Aplicar ' + n + (n === 1 ? ' data' : ' datas')
            : 'Aplicar datas';
          confirmBtn.disabled = !n || (hasExpectedMultiDates && n !== expectedMultiDates) || !hasExpectedMultiDates;
        }
        root.dataset.selectedDates = JSON.stringify(selectedDates.map(function (date) {
          return formatIsoDate(date);
        }));
        renderRouteContext();
        return;
      }
      if (mode === 'single') {
        if (display) {
          display.value = selectedSingle ? formatDisplayDate(selectedSingle) : '';
        }
        /* Gatilho único: o rótulo do botão É o valor. Por extenso, porque num
         * botão sozinho "12 de outubro de 2026" se lê de relance e "12/10/2026"
         * obriga a decifrar. Sem data, volta ao texto de chamada. */
        if (displayText) {
          displayText.textContent = selectedSingle
            ? formatLongDate(selectedSingle)
            : (displayText.dataset.placeholder || 'Escolher data');
          root.classList.toggle('travel-period-filter--active', !!selectedSingle);
        }
        if (singleHidden) {
          singleHidden.value = selectedSingle ? formatIsoDate(selectedSingle) : '';
        }
        if (summary) {
          summary.textContent = selectedSingle ? formatLongDate(selectedSingle) : 'Nenhuma data selecionada';
        }
        return;
      }

      if (display) {
        if (selectedStart && selectedEnd) {
          display.value = formatDisplayDate(selectedStart) + ' a ' + formatDisplayDate(selectedEnd);
        } else if (selectedStart) {
          display.value = formatDisplayDate(selectedStart) + ' a ...';
        } else {
          display.value = '';
        }
      }

      setValueAndNotify(startHidden, selectedStart ? formatIsoDate(selectedStart) : '');
      setValueAndNotify(endHidden, selectedEnd ? formatIsoDate(selectedEnd) : '');
      if (startDisplay) {
        startDisplay.value = selectedStart ? formatDisplayDate(selectedStart) : '';
      }
      if (endDisplay) {
        endDisplay.value = selectedEnd ? formatDisplayDate(selectedEnd) : '';
      }
      if (startLabel) {
        startLabel.textContent = selectedStart ? formatDisplayDate(selectedStart) : 'Escolher';
      }
      if (endLabel) {
        endLabel.textContent = selectedEnd ? formatDisplayDate(selectedEnd) : 'Escolher';
      }
      if (displayText) {
        var displayPlaceholder = displayText.dataset.placeholder || 'Período da viagem';
        var compactRangeDisplay = root.dataset.compactRangeDisplay === 'true';
        var startRangeFormatter = compactRangeDisplay ? formatCompactDisplayDate : formatDisplayDate;
        if (selectedStart && selectedEnd) {
          displayText.textContent = startRangeFormatter(selectedStart) + '  →  ' + formatDisplayDate(selectedEnd);
          root.classList.add('travel-period-filter--active');
        } else if (selectedStart) {
          /* Uma data só é um resultado válido, não um intervalo pela metade: o
           * mesmo controle aceita as duas coisas. Por extenso, como no modo
           * simples — "10/08 → …" anunciava uma segunda data que pode nunca
           * vir. O calendário aberto já mostra que a volta está em aberto. */
          displayText.textContent = formatLongDate(selectedStart);
          root.classList.add('travel-period-filter--active');
        } else {
          displayText.textContent = displayPlaceholder;
          root.classList.remove('travel-period-filter--active');
        }
      }
      if (summary) {
        if (selectedStart && selectedEnd) {
          summary.textContent = formatLongDate(selectedStart) + ' a ' + formatLongDate(selectedEnd);
        } else if (selectedStart) {
          summary.textContent = 'Selecionado: ' + formatLongDate(selectedStart) + ' | defina a volta';
        } else {
          summary.textContent = 'Selecione ida e volta no mesmo calendario';
        }
      }
    }

    function buildWeekdays() {
      if (!weekdays) return;
      weekdays.innerHTML = '';
      WEEKDAYS.forEach(function (label) {
        var node = document.createElement('span');
        node.className = 'date-picker__weekday';
        node.textContent = label;
        weekdays.appendChild(node);
      });
    }

    function buildDayButton(date) {
      var button = document.createElement('button');
      var isCurrentMonth = isSameMonth(date, activeDate);
      var isToday = isSameDay(date, new Date());
      var dayAriaLabel = formatLongDate(date) + (isToday ? ' (hoje)' : '');

      // multi mode: verifica se este dia está na lista de selecionados
      var isMultiSel = false;
      if (mode === 'multi') {
        for (var mi = 0; mi < selectedDates.length; mi++) {
          if (isSameDay(selectedDates[mi], date)) { isMultiSel = true; break; }
        }
      }

      var isStart = mode === 'single' ? isSameDay(date, selectedSingle) : isSameDay(date, selectedStart);
      var isEnd = mode === 'range' && isSameDay(date, selectedEnd);
      var isInRange = mode === 'range' && selectedStart && selectedEnd &&
        !isBeforeDay(date, selectedStart) &&
        !isAfterDay(date, selectedEnd);

      /* O modo multi veste as CLASSES DO INTERVALO — as mesmas do bate-volta.
       * A viagem vai da primeira data escolhida ate a ultima, e e isso que a
       * pilula desenha: pontas arredondadas e miolo cheio. Com uma data so, o
       * intervalo ainda nao tem fim e a marca e o circulo — igual ao bate-volta
       * logo depois do primeiro clique. Nao ha classe `--multi-*`: dois
       * desenhos para a mesma ideia era o que fazia esta tela destoar. */
      var multiStart = mode === 'multi' && selectedDates.length ? selectedDates[0] : null;
      var multiEnd = mode === 'multi' && selectedDates.length > 1
        ? selectedDates[selectedDates.length - 1]
        : null;
      var isMultiStart = !!multiStart && isSameDay(date, multiStart);
      var isMultiEnd = !!multiEnd && isSameDay(date, multiEnd);
      var isInMultiRange = !!multiStart && !!multiEnd &&
        !isBeforeDay(date, multiStart) &&
        !isAfterDay(date, multiEnd);

      button.type = 'button';
      button.className = 'date-picker__day';
      button.textContent = String(date.getDate());
      button.setAttribute('aria-label', dayAriaLabel);
      button.setAttribute('aria-pressed', (isStart || isEnd || isSameDay(date, selectedSingle) || isMultiSel) ? 'true' : 'false');
      button.dataset.date = formatIsoDate(date);
      button.classList.toggle('date-picker__day--muted', !isCurrentMonth);
      button.classList.toggle('date-picker__day--today', isToday);
      button.classList.toggle(
        'date-picker__day--selected',
        mode === 'multi'
          ? (isMultiStart || isMultiEnd)
          : (isStart || isEnd || isSameDay(date, selectedSingle))
      );
      button.classList.toggle(
        'date-picker__day--range',
        mode === 'multi' ? isInMultiRange : isInRange
      );
      button.classList.toggle(
        'date-picker__day--range-start',
        mode === 'multi' ? (isMultiStart && !!multiEnd) : isStart
      );
      button.classList.toggle(
        'date-picker__day--range-end',
        mode === 'multi' ? isMultiEnd : isEnd
      );

      /* A data do MEIO nao tem forma propria: dentro da faixa ela e um dia
       * pintado como qualquer outro, e a viagem some entre a primeira e a
       * ultima. As pontas se leem pela capsula — uma abre a faixa, a outra
       * fecha; as do meio precisam de um numero, senao a pergunta "onde caiu a
       * segunda data?" nao tem resposta na tela. */
      if (mode === 'multi' && selectedDates.length > 2) {
        for (var si = 1; si < selectedDates.length - 1; si += 1) {
          if (!isSameDay(selectedDates[si], date)) continue;
          var badge = document.createElement('span');
          badge.className = 'date-picker__day-badge';
          badge.textContent = String(si + 1);
          button.appendChild(badge);
          var passo = routeSteps[si];
          if (passo && passo.label) {
            button.title = passo.label;
            button.setAttribute('aria-label', dayAriaLabel + ' - ' + passo.label);
          }
          break;
        }
      }

      if (multiSequential) {
        var maxSequentialDates = parseInt(root.dataset.maxDates, 10);
        var sequentialFull = !isNaN(maxSequentialDates)
          && maxSequentialDates > 0
          && selectedDates.length >= maxSequentialDates;
        var ultimaEscolhida = selectedDates[selectedDates.length - 1];
        button.disabled = sequentialFull || (!!ultimaEscolhida && isBeforeDay(date, ultimaEscolhida));
      }

      button.addEventListener('click', function () {
        pickDate(date);
      });

      return button;
    }

    function renderDays() {
      if (!days) return;

      var firstVisible = startOfWeekMonday(startOfMonth(activeDate));
      var i;
      var day;

      days.innerHTML = '';
      dayButtons = [];

      for (i = 0; i < 42; i += 1) {
        day = addDays(firstVisible, i);
        dayButtons.push(buildDayButton(day));
      }

      dayButtons.forEach(function (button) {
        days.appendChild(button);
      });
    }

    function render() {
      syncOutputs();
      if (monthLabel) {
        monthLabel.textContent = formatMonthLabel(activeDate);
      }
      renderDays();
    }

    if (weekdays) buildWeekdays();
    syncStateFromInputs();
    syncOutputs();
    render();

    triggers.forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (isOpen) {
          closePicker();
        } else {
          openPicker();
        }
      });
    });

    if (display) {
      bindAbertura(display);
    }

    prev.addEventListener('click', function () {
      setMonth(addMonths(activeDate, -1));
    });

    next.addEventListener('click', function () {
      setMonth(addMonths(activeDate, 1));
    });

    if (clear) {
      clear.addEventListener('click', function () {
        clearSelection();
        openPicker();
      });
    }

    if (today) {
      today.addEventListener('click', function () {
        pickDate(new Date());
      });
    }

    if (undoBtn) {
      undoBtn.addEventListener('click', function () {
        undoLastMultiDate();
        openPicker();
      });
    }

    /* JS-07 — o painel portalizado pertence à zona interna; Escape conserva
       a restauração de foco de `closePicker`, e clique externo conserva o
       fechamento simples sem alterar o foco. */
    var dismissBinding = window.CV.overlay.attachDismiss({
      inside: [root, panel],
      isOpen: function () { return isOpen; },
      onDismiss: function (reason) {
        if (reason === 'escape') closePicker();
        else setOpen(false);
      },
    });

    /* O painel mora em coordenadas de documento, então a rolagem da PÁGINA já o
     * leva junto e este ouvinte não tem trabalho. Ele existe pela rolagem de um
     * contêiner INTERNO: ali a âncora anda sem que a página role, e sem
     * recalcular o painel ficaria para trás. O lado (acima/abaixo) não é
     * refeito — só a posição. */
    function onScrollOrResize() {
      if (isOpen) positionPanel();
    }
    window.addEventListener('scroll', onScrollOrResize, { passive: true, capture: true });
    window.addEventListener('resize', onScrollOrResize, { passive: true });
    instancias.push({
      root: root,
      desmontar: function () {
        dismissBinding.destroy();
        window.removeEventListener('scroll', onScrollOrResize, { capture: true });
        window.removeEventListener('resize', onScrollOrResize);
      },
    });

    if (confirmBtn) {
      confirmBtn.addEventListener('click', function () {
        if (selectedDates.length === 0) return;
        var isoList = selectedDates.map(function (d) { return formatIsoDate(d); });
        root.dataset.selectedDates = JSON.stringify(isoList);
        root.dispatchEvent(new CustomEvent('cv:multi-confirm', {
          bubbles: true,
          detail: { dates: isoList },
        }));
        closePicker();
      });
    }

    if (startDisplay) {
      bindAbertura(startDisplay);
      startDisplay.addEventListener('change', function () {
        var parsed = parseDisplayDate(startDisplay.value);
        if (parsed) {
          selectedStart = parsed;
          if (selectedEnd && isBeforeDay(selectedEnd, selectedStart)) selectedEnd = null;
          activeDate = startOfMonth(selectedStart);
        } else if (!startDisplay.value.trim()) {
          selectedStart = null;
        }
        setValueAndNotify(startHidden, selectedStart ? formatIsoDate(selectedStart) : '');
        setValueAndNotify(endHidden, selectedEnd ? formatIsoDate(selectedEnd) : '');
        render();
      });
    }

    if (endDisplay) {
      bindAbertura(endDisplay);
      endDisplay.addEventListener('change', function () {
        var parsed = parseDisplayDate(endDisplay.value);
        if (parsed) {
          if (selectedStart && isBeforeDay(parsed, selectedStart)) {
            selectedEnd = selectedStart;
            selectedStart = parsed;
            if (startDisplay) startDisplay.value = formatDisplayDate(selectedStart);
            activeDate = startOfMonth(selectedStart);
          } else {
            selectedEnd = parsed;
          }
        } else if (!endDisplay.value.trim()) {
          selectedEnd = null;
        }
        setValueAndNotify(startHidden, selectedStart ? formatIsoDate(selectedStart) : '');
        setValueAndNotify(endHidden, selectedEnd ? formatIsoDate(selectedEnd) : '');
        render();
      });
    }

    root._cvDatePicker = {
      open: openPicker,
      close: closePicker,
      clear: clearSelection,
      setSingle: function (isoDate) {
        if (mode !== 'single') return;
        selectedSingle = parseIsoDate(isoDate) || parseDisplayDate(isoDate) || null;
        activeDate = startOfMonth(selectedSingle || new Date());
        syncOutputs();
        render();
      },
      setRange: function (startIso, endIso) {
        selectedStart = parseIsoDate(startIso) || null;
        selectedEnd = parseIsoDate(endIso) || null;
        if (selectedStart && selectedEnd && isBeforeDay(selectedEnd, selectedStart)) {
          var tmp = selectedStart;
          selectedStart = selectedEnd;
          selectedEnd = tmp;
        }
        if (selectedStart) activeDate = startOfMonth(selectedStart);
        setValueAndNotify(startHidden, selectedStart ? formatIsoDate(selectedStart) : '');
        setValueAndNotify(endHidden, selectedEnd ? formatIsoDate(selectedEnd) : '');
        render();
      },
    };
  }

  function init(root) {
    var scope = root && root.querySelectorAll ? root : document;
    if (scope.matches && scope.matches(SELECTOR)) initPicker(scope);
    Array.prototype.slice.call(scope.querySelectorAll(SELECTOR)).forEach(initPicker);
  }

  function boot() {
    init(document);
  }

  /* JS-02 — desmonta só os pickers que viviam dentro do nó removido. */
  function destroy(scope) {
    if (!scope || (scope.nodeType !== 1 && scope.nodeType !== 9)) return;
    for (var i = instancias.length - 1; i >= 0; i -= 1) {
      var entrada = instancias[i];
      if (scope === entrada.root || (scope.contains && scope.contains(entrada.root))) {
        entrada.desmontar();
        instancias.splice(i, 1);
      }
    }
  }

  window.CV = window.CV || {};
  window.CV.datePicker = {
    init: init,
    boot: boot,
  };
  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('datePicker', init, destroy);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
