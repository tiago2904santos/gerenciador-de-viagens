(function () {
  "use strict";

  var locationCache = {};

  function asRoot(root) {
    return root || document;
  }

  function resetSearchPicker(select) {
    if (!select) return;
    if (select.dataset) {
      delete select.dataset.entityPickerReady;
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
    if (window.CV && window.CV.picker && typeof window.CV.picker.initSearch === "function") {
      window.CV.picker.initSearch(asRoot(scope));
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
      if (selected && (String(opt.value) === selected || String(opt.textContent).trim() === selected)) {
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
    var requestAttr = params.requestAttr || "destinationCitiesRequest";

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

    return window.CV.http.fetchJson(url, { headers: { Accept: "application/json" } })
      .then(function (result) {
        if (!result.ok) throw new Error("Falha ao carregar cidades");
        return result.data;
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
    var selector = options.rowSelector || "[data-location-row]";
    return Array.prototype.slice.call(asRoot(root).querySelectorAll(selector)).filter(function (row) {
      return !row.hidden;
    });
  }

  function updateSingleRowState(root, options) {
    options = options || {};
    var allRows = rows(root, options);
    var single = allRows.length <= (options.minRows || 1);
    allRows.forEach(function (row) {
      var button = row.querySelector(options.removeSelector || "[data-location-remove]");
      if (button) button.hidden = single;
      row.classList.toggle(options.singleClass || "destination-row--single", single);
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

    Array.prototype.slice.call(fragment.querySelectorAll("[data-entity-picker-ready]")).forEach(function (el) {
      delete el.dataset.entityPickerReady;
    });

    var row = fragment.querySelector(options.rowSelector || "[data-location-row]");
    if (row && options.indexAttr && row.dataset) {
      row.dataset[options.indexAttr] = String(index);
    }
    if (typeof options.beforeAppend === "function") {
      options.beforeAppend(row, index, fragment);
    }
    var insertAfter = options.insertAfter;
    var insertBefore = options.insertBefore;
    if (insertAfter && insertAfter.parentNode === list) {
      list.insertBefore(fragment, insertAfter.nextSibling);
    } else if (insertBefore && insertBefore.parentNode === list) {
      list.insertBefore(fragment, insertBefore);
    } else {
      list.appendChild(fragment);
    }
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
    if (!root || root.dataset.locationDragDropReady === "true") return;
    root.dataset.locationDragDropReady = "true";

    var dragState = null;

    function cleanup() {
      if (dragState && dragState.row) {
        dragState.row.classList.remove("is-dragging");
      }
      dragState = null;
      document.body.classList.remove(options.bodyDraggingClass || "is-dragging-destination");
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
        document.body.classList.add(options.bodyDraggingClass || "is-dragging-destination");
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
      var row = event.target.closest(options.rowSelector || "[data-location-row]");
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

  function selectedOptionText(select) {
    if (!select || select.selectedIndex < 0 || !select.options || !select.options[select.selectedIndex]) {
      return "";
    }
    return String(select.options[select.selectedIndex].text || "").trim();
  }

  function escapeHtml(value) {
    if (window.CV && window.CV.util && typeof window.CV.util.escapeHtml === "function") {
      return window.CV.util.escapeHtml(value);
    }
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function cityLabel(raw, fallback) {
    var nome = String(raw || "").trim();
    if (!nome || nome === "---------") return fallback;
    return nome;
  }

  function trechoHtml(step) {
    return (
      '<span class="route-destinos-trechos__from">' + escapeHtml(step.from) + "</span>" +
      '<span class="route-destinos-trechos__sep" aria-hidden="true">&gt;</span>' +
      '<span class="route-destinos-trechos__to">' + escapeHtml(step.to) + "</span>"
    );
  }

  /**
   * Prévia Sede/Destino > Destino no rail do layout split.
   * Sem origem: pares consecutivos entre destinos. Com origem: origem → d1 → d2…
   */
  function renderTrechosPreview(options) {
    options = options || {};
    var section = options.section
      || (options.sectionSelector ? document.querySelector(options.sectionSelector) : null)
      || document.querySelector(".route-destinos-block--split")
      || document.querySelector(".route-destinos-block");
    if (!section) return null;
    var trechosList = section.querySelector(options.trechosSelector || "[data-route-destinos-trechos]");
    if (!trechosList) return null;
    var subtitle = section.querySelector(options.subtitleSelector || "[data-route-destinos-subtitle]");
    var rowList = section.querySelector(options.listSelector || "[data-location-list]") || section;
    var citySelector = options.citySelector || "[data-location-city]";
    var rowSelector = options.rowSelector || "[data-location-row]";

    function staticSubtitleCopy() {
      if (!subtitle) return "Locais na ordem da visita.";
      var fromData = String(subtitle.getAttribute("data-static-copy") || "").trim();
      return fromData || "Locais na ordem da visita.";
    }

    function setMode(mode, opts) {
      var single = mode === "single";
      var restCount = opts && opts.restCount ? opts.restCount : 0;
      trechosList.hidden = single || restCount === 0;
      if (subtitle) {
        if (single) {
          subtitle.textContent = staticSubtitleCopy();
          subtitle.hidden = false;
        } else if (opts && opts.firstHtml) {
          subtitle.innerHTML = opts.firstHtml;
          subtitle.hidden = false;
        }
      }
      section.classList.toggle("route-destinos-block--single", single);
      section.classList.toggle("route-destinos-block--multi", !single);
      section.classList.toggle("route-destinos-block--with-trechos", !single && restCount > 0);
    }

    var names = rows(rowList, { rowSelector: rowSelector }).map(function (row, index) {
      var citySelect = row.querySelector(citySelector);
      return cityLabel(selectedOptionText(citySelect), "Destino " + (index + 1));
    });

    var originLabel = "";
    var rawOrigin = null;
    if (typeof options.getOriginLabel === "function") {
      rawOrigin = options.getOriginLabel();
    } else if (options.originLabel != null) {
      rawOrigin = options.originLabel;
    }
    if (rawOrigin != null && String(rawOrigin).trim()) {
      originLabel = cityLabel(rawOrigin, options.originFallback || "Sede");
    } else if (options.originFallback) {
      // Roteiro: sem cidade de sede ainda, mantém o rótulo "Sede" na prévia.
      originLabel = String(options.originFallback).trim();
    }

    if (names.length <= 1 && !originLabel) {
      trechosList.innerHTML = "";
      setMode("single");
      return section;
    }
    // Com origem, um único destino ainda é modo single no rail (cópia estática),
    // alinhado ao editor de roteiro: trechos só a partir do 2º destino.
    if (names.length <= 1) {
      trechosList.innerHTML = "";
      setMode("single");
      return section;
    }

    var steps = [];
    var from = originLabel || names[0];
    var startIndex = originLabel ? 0 : 1;
    for (var i = startIndex; i < names.length; i += 1) {
      steps.push({ from: from, to: names[i] });
      from = names[i];
    }
    if (!steps.length) {
      trechosList.innerHTML = "";
      setMode("single");
      return section;
    }

    var first = steps.shift();
    trechosList.innerHTML = steps.map(function (step) {
      return '<li class="route-destinos-trechos__item">' + trechoHtml(step) + "</li>";
    }).join("");
    setMode("multi", {
      firstHtml: first ? trechoHtml(first) : "",
      restCount: steps.length,
    });
    return section;
  }

  function initManagedRows(options) {
    options = options || {};
    var form = options.form || document;
    var section = options.section || (options.sectionSelector ? form.querySelector(options.sectionSelector) : form.querySelector("[data-location-rows]"));
    var list = options.list || (section ? section.querySelector(options.listSelector || "[data-location-list]") : null);
    var addButton = options.addButton || form.querySelector(options.addSelector || "[data-location-add]");
    var template = options.template || form.querySelector(options.templateSelector || "template[data-location-template]");
    options.rowSelector = options.rowSelector || "[data-location-row]";
    options.stateSelector = options.stateSelector || "[data-location-state]";
    options.citySelector = options.citySelector || "[data-location-city]";
    options.removeSelector = options.removeSelector || "[data-location-remove]";
    options.indexAttr = options.indexAttr || "locationIndex";
    options.primaryStateName = options.primaryStateName || "destino_estado";
    options.primaryCityName = options.primaryCityName || "destino_cidade";
    options.extraStatePrefix = options.extraStatePrefix || "destino_estado_";
    options.extraCityPrefix = options.extraCityPrefix || "destino_cidade_";
    if (!list) return null;

    if (options.managedFlag && form.dataset) {
      form.dataset[options.managedFlag] = "true";
    }

    function refreshTrechosPreview() {
      if (!section || !section.querySelector("[data-route-destinos-trechos]")) return;
      renderTrechosPreview({
        section: section,
        listSelector: options.listSelector || "[data-location-list]",
        rowSelector: options.rowSelector,
        citySelector: options.citySelector,
        getOriginLabel: options.getOriginLabel,
        originLabel: options.originLabel,
        originFallback: options.originFallback,
      });
    }

    function renameRows() {
      reindexRows(list, {
        rowSelector: options.rowSelector,
        indexAttr: options.indexAttr,
        onRow: function (row, index) {
          var stateSelect = row.querySelector(options.stateSelector);
          var citySelect = row.querySelector(options.citySelector);
          if (options.renameFields !== false && stateSelect && options.primaryStateName && options.extraStatePrefix) {
            stateSelect.name = index === 0 ? options.primaryStateName : options.extraStatePrefix + index;
          }
          if (options.renameFields !== false && citySelect && options.primaryCityName && options.extraCityPrefix) {
            citySelect.name = index === 0 ? options.primaryCityName : options.extraCityPrefix + index;
          }
          var badge = row.querySelector("[data-location-order]");
          if (badge) badge.textContent = String(index + 1);
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
      refreshTrechosPreview();
      if (typeof options.onChange === "function") {
        options.onChange(list);
      }
    }

    function bindRow(row) {
      if (!row || !row.dataset) return;
      var readyKey = options.readyAttr || "locationRowReady";
      if (row.dataset[readyKey] === "true") return;
      row.dataset[readyKey] = "true";

      var stateSelect = row.querySelector(options.stateSelector);
      var citySelect = row.querySelector(options.citySelector);
      if (stateSelect && citySelect) {
        var initialStateId = (stateSelect.dataset.pickerInitialValue || "").trim();
        var initialCityId = (citySelect.dataset.pickerInitialValue || "").trim();
        stateSelect.addEventListener("change", function () {
          loadCities({
            citySelect: citySelect,
            stateId: stateSelect.value,
            selectedId: "",
            form: form,
            scope: row,
            cache: options.cache || locationCache,
          }).then(function (cities) {
            if (typeof options.afterCitiesLoaded === "function") {
              options.afterCitiesLoaded(citySelect, cities, row);
            }
            notifyChange();
          });
        });
        loadCities({
          citySelect: citySelect,
          stateId: stateSelect.value || initialStateId,
          selectedId: citySelect.value || initialCityId,
          form: form,
          scope: row,
          cache: options.cache || locationCache,
        }).then(function (cities) {
          if (typeof options.afterCitiesLoaded === "function") {
            options.afterCitiesLoaded(citySelect, cities, row);
          }
        });
        citySelect.addEventListener("change", notifyChange);
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
    refreshTrechosPreview();
    initDragDrop(list, {
      rowSelector: options.rowSelector,
      removeSelector: options.removeSelector,
      onReorder: function () {
        renameRows();
        refreshRows();
        notifyChange();
      }
    });

    var addRoot = section || list;
    var addSelector = options.addSelector || "[data-location-add]";
    if (template && addRoot && addRoot.dataset && addRoot.dataset.locationAddBound !== "true") {
      addRoot.dataset.locationAddBound = "true";
      addRoot.addEventListener("click", function (event) {
        var button = event.target.closest(addSelector);
        if (!button || !addRoot.contains(button)) return;

        var sourceRow = button.closest(options.rowSelector);
        if (sourceRow && !list.contains(sourceRow)) sourceRow = null;

        var currentRows = rows(list, { rowSelector: options.rowSelector });
        var referenceRow = sourceRow || (currentRows.length ? currentRows[currentRows.length - 1] : null);
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
          insertAfter: sourceRow || null,
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
      refreshTrechosPreview: refreshTrechosPreview,
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

  function init(root) {
    var scope = asRoot(root);
    var sections = Array.prototype.slice.call(
      scope.querySelectorAll ? scope.querySelectorAll("[data-location-rows]") : []
    );
    if (scope.matches && scope.matches("[data-location-rows]")) {
      sections.unshift(scope);
    }
    sections.forEach(initSearchPickers);
  }

  window.CV = window.CV || {};
  window.CV.locationRows = {
    appendTemplateRow: appendTemplateRow,
    clearSelect: clearSelect,
    focusFirstEmptyPicker: focusFirstEmptyPicker,
    initDragDrop: initDragDrop,
    init: init,
    initManagedRows: initManagedRows,
    initSearchPickers: initSearchPickers,
    loadCities: loadCities,
    nextIndex: nextIndex,
    reindexRows: reindexRows,
    reinitSearchPicker: reinitSearchPicker,
    renderTrechosPreview: renderTrechosPreview,
    resetSearchPicker: resetSearchPicker,
    rows: rows,
    setSelectOptions: setSelectOptions,
    updateSingleRowState: updateSingleRowState,
  };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("locationRows", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
})();
