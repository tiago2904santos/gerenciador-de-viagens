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

    var mode = root.dataset.mode === 'range' ? 'range' : 'single';
    var trigger = root.querySelector('[data-cv-date-picker-trigger]');
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
    var summary = root.querySelector('[data-cv-date-picker-summary]');
    var startDisplay = root.querySelector('[data-cv-date-picker-start-display]');
    var endDisplay = root.querySelector('[data-cv-date-picker-end-display]');
    var activeDate = new Date();
    var selectedSingle = null;
    var selectedStart = null;
    var selectedEnd = null;
    var isOpen = false;
    var focusedDate = null;
    var dayButtons = [];

    function syncStateFromInputs() {
      if (mode === 'single') {
        selectedSingle = getInitialDate(root, singleHidden, selectedSingle || new Date());
        if (singleHidden && singleHidden.value) {
          selectedSingle = parseIsoDate(singleHidden.value) || parseDisplayDate(singleHidden.value);
        }
        if (!selectedSingle) selectedSingle = getInitialDate(root, display, new Date());
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

    function positionPanel() {
      var anchor = startDisplay || trigger;
      var rect = anchor.getBoundingClientRect();
      panel.style.top = (rect.bottom + 8) + 'px';
      panel.style.left = rect.left + 'px';
      panel.style.width = Math.max(rect.width, 320) + 'px';
    }

    function setOpen(nextOpen) {
      isOpen = !!nextOpen;
      panel.hidden = !isOpen;
      root.classList.toggle('cv-date-picker--open', isOpen);
      trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      if (isOpen) {
        positionPanel();
        render();
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
      if (mode === 'single') {
        selectedSingle = null;
      } else {
        selectedStart = null;
        selectedEnd = null;
      }
      syncOutputs();
      activeDate = startOfMonth(new Date());
      render();
    }

    function pickDate(date) {
      var picked = cloneDate(date);

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
      var isStart = mode === 'single' ? isSameDay(date, selectedSingle) : isSameDay(date, selectedStart);
      var isEnd = mode === 'range' && isSameDay(date, selectedEnd);
      var isInRange = mode === 'range' && selectedStart && selectedEnd &&
        !isBeforeDay(date, selectedStart) &&
        !isAfterDay(date, selectedEnd);

      button.type = 'button';
      button.className = 'cv-date-picker__day';
      button.textContent = String(date.getDate());
      button.setAttribute('aria-label', formatLongDate(date));
      button.setAttribute('aria-pressed', (isStart || isEnd || isSameDay(date, selectedSingle)) ? 'true' : 'false');
      button.dataset.date = formatIsoDate(date);
      button.classList.toggle('cv-date-picker__day--muted', !isCurrentMonth);
      button.classList.toggle('cv-date-picker__day--today', isToday);
      button.classList.toggle('cv-date-picker__day--selected', isStart || isEnd || isSameDay(date, selectedSingle));
      button.classList.toggle('cv-date-picker__day--range', isInRange);
      button.classList.toggle('cv-date-picker__day--range-start', isStart);
      button.classList.toggle('cv-date-picker__day--range-end', isEnd);
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
      if (path.indexOf(root) === -1) {
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

    trigger.addEventListener('click', function () {
      if (isOpen) {
        closePicker();
      } else {
        openPicker();
      }
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

    document.addEventListener('click', onDocumentClick);
    document.addEventListener('keydown', onKeydown);

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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
