(function (window, document) {
  "use strict";

  window.CV = window.CV || {};

  function read(source) {
    var element = typeof source === "string" ? document.getElementById(source) : source;
    if (!element) return {};
    try {
      var parsed = JSON.parse(element.textContent || "{}");
      return parsed && typeof parsed === "object" ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function index(source) {
    var values = source || {};
    if (!Array.isArray(values)) return values;
    return values.reduce(function (result, item) {
      if (item && item.id != null) result[String(item.id)] = item;
      return result;
    }, {});
  }

  function selected(select, source) {
    if (!select) return [];
    if (source == null && select.dataset.sourceDocument) {
      source = read(select.dataset.sourceDocument);
    }
    var documents = index(source);
    return Array.from(select.options)
      .filter(function (option) { return option.selected && option.value; })
      .map(function (option) { return documents[String(option.value)] || null; })
      .filter(Boolean);
  }

  function valueAt(object, path) {
    return String(path || "").split(".").reduce(function (value, part) {
      return value == null ? undefined : value[part];
    }, object);
  }

  function matchingDocuments(documents, rule) {
    if (!rule.when) return documents;
    return documents.filter(function (item) {
      var value = valueAt(item, rule.when.path);
      return rule.when.equals == null ? !!value : String(value) === String(rule.when.equals);
    });
  }

  function resolve(documents, rule, path) {
    var values = matchingDocuments(documents, rule)
      .map(function (item) { return valueAt(item, path); })
      .filter(function (value) { return value != null && value !== ""; });
    var strategy = rule.strategy || "first";
    if (strategy === "union") {
      var unique = new Set();
      values.forEach(function (value) {
        (Array.isArray(value) ? value : [value]).forEach(function (entry) {
          if (entry != null && entry !== "") unique.add(String(entry));
        });
      });
      return Array.from(unique);
    }
    if (strategy === "min" || strategy === "max") {
      values.sort();
      return strategy === "min" ? values[0] : values[values.length - 1];
    }
    return values[0];
  }

  function field(form, name) {
    return form.querySelector('[name="' + name + '"]');
  }

  function emit(element, events) {
    if (!element || !events) return;
    ["input", "change"].forEach(function (name) {
      element.dispatchEvent(new Event(name, { bubbles: true }));
    });
  }

  function refreshPicker(form, select) {
    var rows = window.CV.locationRows;
    if (!select || !rows) return;
    rows.resetSearchPicker(select);
    rows.initSearchPickers(form);
  }

  function setValue(form, name, value, options) {
    var element = field(form, name);
    if (!element) return null;
    options = options || {};
    if (options.preserve && String(element.value || "").trim()) return element;
    element.value = value == null ? "" : value;
    if (element.tagName === "SELECT") refreshPicker(form, element);
    emit(element, options.events);
    return element;
  }

  function setMulti(form, name, values, options) {
    var select = field(form, name);
    if (!select) return null;
    var selectedValues = new Set((values || []).map(String));
    Array.from(select.options).forEach(function (option) {
      option.selected = selectedValues.has(String(option.value));
    });
    refreshPicker(form, select);
    emit(select, options && options.events);
    return select;
  }

  function setRadio(form, name, value, options) {
    var radio = form.querySelector(
      'input[type="radio"][name="' + name + '"][value="' + String(value == null ? "" : value) + '"]'
    );
    if (!radio) return null;
    radio.checked = true;
    emit(radio, options && options.events);
    return radio;
  }

  function setDateRange(form, rule, documents) {
    var start = resolve(documents, {
      strategy: rule.startStrategy || "first",
      when: rule.when,
    }, rule.startPath);
    var end = resolve(documents, {
      strategy: rule.endStrategy || "first",
      when: rule.when,
    }, rule.endPath) || start;
    if (!start && !rule.clear) return;

    setValue(form, rule.startName, start || "", rule);
    setValue(form, rule.endName, end || "", rule);

    var picker = rule.picker ? form.querySelector(rule.picker) : null;
    if (picker && picker._cvDatePicker && typeof picker._cvDatePicker.setRange === "function") {
      picker._cvDatePicker.setRange(start || "", end || "");
    }
  }

  function setLocation(form, rule, documents) {
    var candidates = matchingDocuments(documents, rule).filter(function (item) {
      return valueAt(item, rule.statePath);
    });
    var source = candidates[0];
    var state = source ? valueAt(source, rule.statePath) : "";
    var city = source ? valueAt(source, rule.cityPath) : "";
    if (!state && !rule.clear) return Promise.resolve();

    var stateSelect = field(form, rule.stateName);
    var citySelect = field(form, rule.cityName);
    if (!stateSelect || !citySelect) return Promise.resolve();
    stateSelect.value = state == null ? "" : String(state);
    refreshPicker(form, stateSelect);

    if (!state) {
      citySelect.innerHTML = '<option value="">Selecione a cidade</option>';
      citySelect.disabled = true;
      refreshPicker(form, citySelect);
      return Promise.resolve();
    }
    return window.CV.locationRows.loadCities({
      citySelect: citySelect,
      stateId: String(state),
      selectedId: city == null ? "" : String(city),
      form: form,
      scope: form,
    });
  }

  function apply(form, documents, rules) {
    var pending = [];
    (rules || []).forEach(function (rule) {
      var value;
      if (rule.type === "date-range") {
        setDateRange(form, rule, documents);
      } else if (rule.type === "location") {
        pending.push(setLocation(form, rule, documents));
      } else {
        value = resolve(documents, rule, rule.path);
        if ((value == null || value === "" || (Array.isArray(value) && !value.length)) && !rule.clear) return;
        if (rule.type === "multi") {
          setMulti(form, rule.name, value || [], rule);
        } else if (rule.type === "radio") {
          setRadio(form, rule.name, value, rule);
        } else {
          setValue(form, rule.name, value == null ? "" : value, rule);
        }
      }
      if (typeof rule.after === "function") rule.after();
    });
    return Promise.all(pending);
  }

  window.CV.documentSource = {
    apply: apply,
    index: index,
    read: read,
    selected: selected,
    setDateRange: setDateRange,
    setMulti: setMulti,
    setRadio: setRadio,
    setValue: setValue,
    valueAt: valueAt,
  };
})(window, document);
