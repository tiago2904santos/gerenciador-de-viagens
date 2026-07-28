(function () {
  'use strict';

  var SELECTOR = '[data-cv-date-picker]';
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
        contextStep.textContent = 'Trecho ' + currentStepNumber + ' de ' + totalSteps;
      }
      if (contextRoute) {
        contextRoute.textContent = currentStep.label || ((currentStep.from || '') + ' > ' + (currentStep.to || ''));
      }
    }

    function positionPanel() {
      if (panel.parentElement !== document.body) {
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
      panel.style.position = 'fixed';
      panel.style.width = width + 'px';

      var left = rect.right - width;
      if (vw) {
        left = Math.min(left, vw - width - margin);
        left = Math.max(left, margin);
      }

      var top = rect.bottom + 8;
      var panelHeight = panel.offsetHeight || 0;
      if (vh && panelHeight) {
        var belowSpace = vh - top - margin;
        if (belowSpace < panelHeight && rect.top - 8 - panelHeight > margin) {
          top = rect.top - 8 - panelHeight;
        }
        top = Math.max(margin, Math.min(top, vh - panelHeight - margin));
      }

      panel.style.top = top + 'px';
      panel.style.left = left + 'px';
    }

    function setOpen(nextOpen) {
      isOpen = !!nextOpen;
      panel.hidden = !isOpen;
      root.classList.toggle('cv-date-picker--open', isOpen);
      triggers.forEach(function (btn) {
        btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });
      if (isOpen) {
        positionPanel();
        // Garante animação mesmo com o panel fora do root (portal)
        panel.classList.remove('cv-date-picker__panel--entering');
        void panel.offsetWidth; // force reflow
        panel.classList.add('cv-date-picker__panel--entering');
        render();
      } else {
        panel.classList.remove('cv-date-picker__panel--entering');
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
          displayText.textContent = startRangeFormatter(selectedStart) + '  →  …';
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
        node.className = 'cv-date-picker__weekday';
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
      var isMultiRange = false;
      var isMultiStart = false;
      var isMultiMiddle = false;
      var isMultiEnd = false;
      var isMultiSingle = false;
      if (mode === 'multi' && selectedDates.length) {
        var multiStart = selectedDates[0];
        var multiEnd = selectedDates[selectedDates.length - 1];
        isMultiRange = !!multiStart && !!multiEnd && !isBeforeDay(date, multiStart) && !isAfterDay(date, multiEnd);
        isMultiStart = isMultiRange && isSameDay(date, multiStart);
        isMultiEnd = isMultiRange && isSameDay(date, multiEnd);
        isMultiMiddle = isMultiRange && !isMultiStart && !isMultiEnd;
        isMultiSingle = selectedDates.length === 1 && isMultiStart;
      }

      button.type = 'button';
      button.className = 'cv-date-picker__day';
      button.textContent = String(date.getDate());
      button.setAttribute('aria-label', dayAriaLabel);
      button.setAttribute('aria-pressed', (isStart || isEnd || isSameDay(date, selectedSingle) || isMultiRange) ? 'true' : 'false');
      button.dataset.date = formatIsoDate(date);
      button.classList.toggle('cv-date-picker__day--muted', !isCurrentMonth);
      button.classList.toggle('cv-date-picker__day--today', isToday);
      button.classList.toggle('cv-date-picker__day--selected', mode !== 'multi' && (isStart || isEnd || isSameDay(date, selectedSingle)));
      button.classList.toggle('cv-date-picker__day--range', isInRange);
      button.classList.toggle('cv-date-picker__day--range-start', isStart);
      button.classList.toggle('cv-date-picker__day--range-end', isEnd);
      button.classList.toggle('cv-date-picker__day--multi-selected', isMultiRange);
      button.classList.toggle('cv-date-picker__day--multi-start', isMultiStart);
      button.classList.toggle('cv-date-picker__day--multi-middle', isMultiMiddle);
      button.classList.toggle('cv-date-picker__day--multi-end', isMultiEnd);
      button.classList.toggle('cv-date-picker__day--multi-single', isMultiSingle);

      if (mode === 'multi' && isMultiSel) {
        // Uma mesma data pode atender mais de um trecho (chegar e seguir viagem no mesmo dia).
        var multiStepIndexes = [];
        for (var stepIndex = 0; stepIndex < selectedDates.length; stepIndex += 1) {
          if (isSameDay(selectedDates[stepIndex], date)) {
            multiStepIndexes.push(stepIndex);
          }
        }
        var multiStepIndex = multiStepIndexes.length ? multiStepIndexes[0] : -1;
        var hasMiddleStep = multiStepIndex > 0 && multiStepIndex < selectedDates.length - 1;
        if (hasMiddleStep || multiStepIndexes.length > 1) {
          var badge = document.createElement('span');
          badge.className = 'cv-date-picker__day-badge';
          badge.textContent = multiStepIndexes.map(function (index) {
            return String(index + 1);
          }).join('·');
          button.appendChild(badge);
          var stepLabels = multiStepIndexes.map(function (index) {
            return routeSteps[index] ? routeSteps[index].label : '';
          }).filter(function (label) {
            return !!label;
          });
          if (stepLabels.length) {
            button.title = stepLabels.join(' | ');
            button.setAttribute('aria-label', dayAriaLabel + ' - ' + stepLabels.join(' | '));
          }
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

    function onDocumentClick(event) {
      var path = event.composedPath ? event.composedPath() : [event.target];
      // O panel pode estar em document.body (portal), checar root E panel separadamente
      if (path.indexOf(root) === -1 && path.indexOf(panel) === -1) {
        setOpen(false);
      }
    }

    function onKeydown(event) {
      if (event.key === 'Escape' && isOpen) {
        event.preventDefault();
        closePicker();
      }
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
      display.addEventListener('click', function () {
        openPicker();
      });
      display.addEventListener('focus', function () {
        openPicker();
      });
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

    document.addEventListener('click', onDocumentClick);
    document.addEventListener('keydown', onKeydown);

    // Reposicionar ao scrollar ou redimensionar para o panel acompanhar o anchor
    function onScrollOrResize() {
      if (isOpen) positionPanel();
    }
    window.addEventListener('scroll', onScrollOrResize, { passive: true, capture: true });
    window.addEventListener('resize', onScrollOrResize, { passive: true });

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
      startDisplay.addEventListener('click', openPicker);
      startDisplay.addEventListener('focus', openPicker);
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
      endDisplay.addEventListener('click', openPicker);
      endDisplay.addEventListener('focus', openPicker);
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

  window.CvDatePicker = {
    init: init,
    boot: boot,
  };
  window.CV = window.CV || {};
  window.CV.datePicker = window.CvDatePicker;

  if (typeof window.CV.registerEnhancer === 'function') {
    window.CV.registerEnhancer('datePicker', init);
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
