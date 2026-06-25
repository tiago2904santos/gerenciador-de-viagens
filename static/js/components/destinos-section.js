(function () {
  "use strict";

  function asRoot(root) {
    return root || document;
  }

  function resetSearchPicker(select) {
    if (!select) return;
    if (select.dataset) {
      delete select.dataset.cvSearchPickerReady;
    }
    var nextEl = select.nextElementSibling;
    if (nextEl && nextEl.classList && nextEl.classList.contains("cv-search-picker")) {
      nextEl.parentNode.removeChild(nextEl);
    }
  }

  function initSearchPickers(scope) {
    var api = (window.CV && window.CV.fields && window.CV.fields.initSearchPickers)
      ? window.CV.fields
      : null;
    if (api && typeof api.initSearchPickers === "function") {
      api.initSearchPickers(asRoot(scope));
      return;
    }
    if (window.CvSearchPicker && typeof window.CvSearchPicker.init === "function") {
      window.CvSearchPicker.init(asRoot(scope));
    }
  }

  function reinitSearchPicker(select, scope) {
    resetSearchPicker(select);
    initSearchPickers(scope || (select && select.parentNode) || document);
  }

  function optionValue(item) {
    if (!item) return "";
    return item.id != null ? item.id : (item.value != null ? item.value : "");
  }

  function optionLabel(item) {
    if (!item) return "";
    return item.nome != null ? item.nome : (item.label != null ? item.label : String(optionValue(item)));
  }

  function setSelectOptions(select, items, selectedValue, options) {
    if (!select) return;
    options = options || {};
    var selected = String(selectedValue || "");
    resetSearchPicker(select);
    select.innerHTML = options.emptyOptionHtml || '<option value="">---------</option>';
    (items || []).forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = String(optionValue(item));
      opt.textContent = optionLabel(item);
      if (selected && String(opt.value) === selected) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
    select.disabled = !!options.disabled;
    initSearchPickers(options.scope || select.parentNode || document);
  }

  function clearSelect(select, options) {
    options = options || {};
    options.disabled = true;
    setSelectOptions(select, [], "", options);
  }

  function loadCities(params) {
    params = params || {};
    var citySelect = params.citySelect;
    var stateId = String(params.stateId || "").trim();
    var selectedId = params.selectedId;
    var scope = params.scope || params.form || (citySelect && citySelect.parentNode) || document;
    var cache = params.cache || {};
    var requestAttr = params.requestAttr || "destinosCitiesRequest";

    if (!citySelect) return Promise.resolve([]);
    if (!stateId) {
      clearSelect(citySelect, { scope: scope });
      return Promise.resolve([]);
    }

    if (cache[stateId]) {
      setSelectOptions(citySelect, cache[stateId], selectedId, { scope: scope });
      return Promise.resolve(cache[stateId]);
    }

    var url = "";
    if (typeof params.urlForState === "function") {
      url = params.urlForState(stateId, params);
    } else {
      var template = params.urlTemplate || (params.form && params.form.dataset ? params.form.dataset.apiCidadesUrl : "");
      url = template ? template.replace("/0/", "/" + encodeURIComponent(stateId) + "/") : "";
    }

    if (!url) {
      clearSelect(citySelect, { scope: scope });
      return Promise.resolve([]);
    }

    var token = String(Date.now()) + "-" + Math.random().toString(16).slice(2);
    citySelect.dataset[requestAttr] = token;
    clearSelect(citySelect, { scope: scope });

    return fetch(url, { headers: { Accept: "application/json" } })
      .then(function (response) {
        if (!response.ok) throw new Error("Falha ao carregar cidades");
        return response.json();
      })
      .then(function (data) {
        if (citySelect.dataset[requestAttr] !== token) return [];
        var cities = Array.isArray(data) ? data : (data.cidades || []);
        cache[stateId] = cities;
        setSelectOptions(citySelect, cities, selectedId, { scope: scope });
        return cities;
      })
      .catch(function () {
        if (citySelect.dataset[requestAttr] === token) {
          clearSelect(citySelect, { scope: scope });
        }
        return [];
      });
  }

  function rows(root, options) {
    options = options || {};
    var selector = options.rowSelector || ".destino-row";
    return Array.prototype.slice.call(asRoot(root).querySelectorAll(selector)).filter(function (row) {
      return !row.hidden;
    });
  }

  function updateSingleRowState(root, options) {
    options = options || {};
    var allRows = rows(root, options);
    var single = allRows.length <= (options.minRows || 1);
    allRows.forEach(function (row) {
      var button = row.querySelector(options.removeSelector || ".btn-remover-destino");
      if (button) button.hidden = single;
      row.classList.toggle(options.singleClass || "destino-row--single", single);
    });
    return allRows;
  }

  function reindexRows(root, options) {
    options = options || {};
    rows(root, options).forEach(function (row, index) {
      if (options.indexAttr && row.dataset) {
        row.dataset[options.indexAttr] = String(index);
      }
      if (typeof options.onRow === "function") {
        options.onRow(row, index);
      }
    });
  }

  function nextIndex(root, options) {
    options = options || {};
    var attr = options.indexAttr;
    var values = rows(root, options).map(function (row) {
      var raw = attr && row.dataset ? row.dataset[attr] : "";
      var value = parseInt(raw || "0", 10);
      return isNaN(value) ? 0 : value;
    });
    return values.length ? Math.max.apply(Math, values) + 1 : (options.startIndex || 1);
  }

  function appendTemplateRow(options) {
    options = options || {};
    var list = options.list;
    var template = options.template;
    if (!list || !template) return null;

    var index = options.index != null ? options.index : nextIndex(list, options);
    var holder = document.createElement("div");
    holder.innerHTML = String(template.innerHTML || "").replace(/__index__/g, String(index)).trim();
    var fragment = document.createDocumentFragment();
    while (holder.firstChild) fragment.appendChild(holder.firstChild);

    Array.prototype.slice.call(fragment.querySelectorAll("[data-cv-search-picker-ready]")).forEach(function (el) {
      delete el.dataset.cvSearchPickerReady;
    });

    var row = fragment.querySelector(options.rowSelector || ".destino-row");
    if (row && options.indexAttr && row.dataset) {
      row.dataset[options.indexAttr] = String(index);
    }
    if (typeof options.beforeAppend === "function") {
      options.beforeAppend(row, index, fragment);
    }
    list.appendChild(fragment);
    if (!row && options.indexAttr) {
      row = list.querySelector("[data-" + options.indexAttr.replace(/[A-Z]/g, function (m) { return "-" + m.toLowerCase(); }) + "='" + String(index) + "']");
    }
    if (row) {
      if (typeof options.bindRow === "function") {
        options.bindRow(row, index);
      }
      initSearchPickers(row);
    }
    updateSingleRowState(list, options);
    if (typeof options.afterAppend === "function") {
      options.afterAppend(row, index);
    }
    return row;
  }

  function clearDropTargets(root, options) {
    rows(root, options).forEach(function (row) {
      row.classList.remove("is-drop-target", "is-drop-before", "is-drop-after");
    });
  }

  function dropTarget(root, dragged, clientY, options) {
    var target = null;
    var closestDistance = Infinity;
    rows(root, options).forEach(function (row) {
      if (row === dragged) return;
      var rect = row.getBoundingClientRect();
      var centerY = rect.top + (rect.height / 2);
      var distance = Math.abs(clientY - centerY);
      if (distance < closestDistance) {
        closestDistance = distance;
        target = {
          row: row,
          placeAfter: clientY >= centerY,
        };
      }
    });
    return target;
  }

  function setDropTarget(root, target, options) {
    clearDropTargets(root, options);
    if (!target || !target.row) return;
    target.row.classList.add("is-drop-target");
    target.row.classList.add(target.placeAfter ? "is-drop-after" : "is-drop-before");
  }

  function initDragDrop(root, options) {
    root = asRoot(root);
    options = options || {};
    if (!root || root.dataset.destinosDragDropReady === "true") return;
    root.dataset.destinosDragDropReady = "true";

    var dragState = null;

    function cleanup() {
      if (dragState && dragState.row) {
        dragState.row.classList.remove("is-dragging");
      }
      dragState = null;
      document.body.classList.remove(options.bodyDraggingClass || "is-dragging-destino");
      clearDropTargets(root, options);
      document.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("pointerup", onPointerUp);
      document.removeEventListener("pointercancel", cleanup);
    }

    function moveRow(dragged, target) {
      if (!dragged || !target || !target.row || dragged === target.row) return false;
      var reference = target.placeAfter ? target.row.nextSibling : target.row;
      if (reference === dragged) return false;
      root.insertBefore(dragged, reference);
      dragged.classList.add("is-reordered");
      window.setTimeout(function () {
        dragged.classList.remove("is-reordered");
      }, 460);
      if (typeof options.onReorder === "function") {
        options.onReorder(dragged);
      }
      return true;
    }

    function onPointerMove(event) {
      if (!dragState) return;
      var dx = event.clientX - dragState.startX;
      var dy = event.clientY - dragState.startY;
      if (!dragState.active) {
        if (Math.sqrt((dx * dx) + (dy * dy)) < (options.threshold || 8)) return;
        dragState.active = true;
        dragState.row.classList.add("is-dragging");
        document.body.classList.add(options.bodyDraggingClass || "is-dragging-destino");
      }
      event.preventDefault();
      dragState.currentTarget = dropTarget(root, dragState.row, event.clientY, options);
      setDropTarget(root, dragState.currentTarget, options);
    }

    function onPointerUp(event) {
      if (!dragState) return;
      if (!dragState.active) {
        cleanup();
        return;
      }
      event.preventDefault();
      var target = dragState.currentTarget || dropTarget(root, dragState.row, event.clientY, options);
      var dragged = dragState.row;
      cleanup();
      moveRow(dragged, target);
    }

    root.addEventListener("pointerdown", function (event) {
      if (event.button !== 0) return;
      if (rows(root, options).length <= 1) return;
      var row = event.target.closest(options.rowSelector || ".destino-row");
      if (!row || !root.contains(row)) return;
      var blocked = event.target.closest(options.ignoreSelector || [
        "button",
        "input",
        "select",
        "textarea",
        "a",
        "[role='button']",
        ".cv-search-picker__control",
        ".cv-search-picker__dropdown",
        ".cv-search-picker__option",
        ".cv-search-picker__clear",
        ".cv-search-picker__remove"
      ].join(", "));
      var handleSelector = options.dragHandleSelector;
      if (handleSelector && !event.target.closest(handleSelector)) return;
      if (blocked) return;
      cleanup();
      dragState = {
        row: row,
        startX: event.clientX,
        startY: event.clientY,
        currentTarget: null,
        active: false,
      };
      document.addEventListener("pointermove", onPointerMove);
      document.addEventListener("pointerup", onPointerUp);
      document.addEventListener("pointercancel", cleanup);
    });
  }

  function initManagedRows(options) {
    options = options || {};
    var form = options.form || document;
    var section = options.section || (options.sectionSelector ? form.querySelector(options.sectionSelector) : null);
    var list = options.list || (section ? section.querySelector(options.listSelector || ".roteiro-destinos-list") : null);
    var addButton = options.addButton || (options.addSelector ? form.querySelector(options.addSelector) : null);
    var template = options.template || (options.templateSelector ? form.querySelector(options.templateSelector) : null);
    if (!list) return null;

    if (options.managedFlag && form.dataset) {
      form.dataset[options.managedFlag] = "true";
    }

    function renameRows() {
      reindexRows(list, {
        rowSelector: options.rowSelector,
        indexAttr: options.indexAttr,
        onRow: function (row, index) {
          var stateSelect = row.querySelector(options.stateSelector);
          var citySelect = row.querySelector(options.citySelector);
          if (stateSelect && options.primaryStateName && options.extraStatePrefix) {
            stateSelect.name = index === 0 ? options.primaryStateName : options.extraStatePrefix + index;
          }
          if (citySelect && options.primaryCityName && options.extraCityPrefix) {
            citySelect.name = index === 0 ? options.primaryCityName : options.extraCityPrefix + index;
          }
          if (typeof options.onRow === "function") {
            options.onRow(row, index);
          }
        }
      });
    }

    function refreshRows() {
      updateSingleRowState(list, {
        rowSelector: options.rowSelector,
        removeSelector: options.removeSelector,
      });
    }

    function notifyChange() {
      if (typeof options.onChange === "function") {
        options.onChange(list);
      }
    }

    function bindRow(row) {
      if (!row || !row.dataset) return;
      var readyKey = options.readyAttr || "destinosManagedReady";
      if (row.dataset[readyKey] === "true") return;
      row.dataset[readyKey] = "true";

      var stateSelect = row.querySelector(options.stateSelector);
      var citySelect = row.querySelector(options.citySelector);
      if (stateSelect && citySelect && typeof options.loadCities === "function") {
        var initialStateId = (stateSelect.dataset.pickerInitialValue || "").trim();
        var initialCityId = (citySelect.dataset.pickerInitialValue || "").trim();
        stateSelect.addEventListener("change", function () {
          options.loadCities(citySelect, stateSelect.value || initialStateId, citySelect.value || initialCityId, row);
          notifyChange();
        });
        options.loadCities(citySelect, stateSelect.value || initialStateId, citySelect.value || initialCityId, row);
      }

      var removeButton = row.querySelector(options.removeSelector);
      if (removeButton) {
        removeButton.addEventListener("click", function () {
          row.remove();
          renameRows();
          refreshRows();
          notifyChange();
        });
      }
    }

    rows(list, { rowSelector: options.rowSelector }).forEach(bindRow);
    renameRows();
    refreshRows();
    initDragDrop(list, {
      rowSelector: options.rowSelector,
      removeSelector: options.removeSelector,
      onReorder: function () {
        renameRows();
        refreshRows();
        notifyChange();
      }
    });

    if (addButton && template && addButton.dataset.destinosAddBound !== "true") {
      addButton.dataset.destinosAddBound = "true";
      addButton.addEventListener("click", function () {
        var currentRows = rows(list, { rowSelector: options.rowSelector });
        var referenceRow = currentRows.length ? currentRows[currentRows.length - 1] : null;
        var referenceState = referenceRow ? referenceRow.querySelector(options.stateSelector) : null;
        var referenceStateId = referenceState
          ? String(referenceState.value || referenceState.dataset.pickerInitialValue || "").trim()
          : "";
        appendTemplateRow({
          list: list,
          template: template,
          rowSelector: options.rowSelector,
          removeSelector: options.removeSelector,
          indexAttr: options.indexAttr,
          beforeAppend: function (row) {
            if (!row || !referenceStateId || options.copyLastState === false) return;
            var stateSelect = row.querySelector(options.stateSelector);
            if (stateSelect) {
              stateSelect.value = referenceStateId;
              stateSelect.dataset.pickerInitialValue = referenceStateId;
            }
          },
          bindRow: function (row) {
            bindRow(row);
            renameRows();
          },
          afterAppend: function () {
            renameRows();
            refreshRows();
            initSearchPickers(list);
            notifyChange();
          }
        });
      });
    }

    return {
      bindRow: bindRow,
      refreshRows: refreshRows,
      renameRows: renameRows,
    };
  }

  function focusFirstEmptyPicker(root, options) {
    options = options || {};
    var inputs = Array.prototype.slice.call(asRoot(root).querySelectorAll(options.inputSelector || ".cv-search-picker__input"))
      .filter(function (input) {
        return !input.disabled;
      });
    var target = inputs.find(function (input) {
      return !String(input.value || "").trim();
    }) || inputs[0];
    if (target) {
      window.setTimeout(function () {
        target.focus();
      }, 0);
    }
    return target || null;
  }

  window.CV = window.CV || {};
  window.CV.destinos = {
    appendTemplateRow: appendTemplateRow,
    clearSelect: clearSelect,
    focusFirstEmptyPicker: focusFirstEmptyPicker,
    initDragDrop: initDragDrop,
    initManagedRows: initManagedRows,
    initSearchPickers: initSearchPickers,
    loadCities: loadCities,
    nextIndex: nextIndex,
    reindexRows: reindexRows,
    reinitSearchPicker: reinitSearchPicker,
    resetSearchPicker: resetSearchPicker,
    rows: rows,
    setSelectOptions: setSelectOptions,
    updateSingleRowState: updateSingleRowState,
  };
})();
