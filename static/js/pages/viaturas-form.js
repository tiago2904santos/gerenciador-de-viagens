(function () {
  "use strict";

  function draftStorageKey() {
    return "viaturaFormDraft:" + window.location.pathname;
  }

  function serializeFormEntries(form) {
    var data = new FormData(form);
    var entries = [];
    data.forEach(function (value, key) {
      if (key === "csrfmiddlewaretoken") return;
      entries.push([key, value]);
    });
    return entries;
  }

  function saveDraft(form) {
    try {
      window.sessionStorage.setItem(draftStorageKey(), JSON.stringify(serializeFormEntries(form)));
    } catch (err) {
      /* armazenamento indisponivel (modo privado, quota etc.) */
    }
  }

  function takeDraft() {
    var key = draftStorageKey();
    var raw;
    try {
      raw = window.sessionStorage.getItem(key);
    } catch (err) {
      return null;
    }
    if (!raw) return null;
    try {
      window.sessionStorage.removeItem(key);
    } catch (err) {
      /* ignore */
    }
    var entries;
    try {
      entries = JSON.parse(raw);
    } catch (err) {
      return null;
    }
    if (!Array.isArray(entries)) return null;
    var byName = {};
    entries.forEach(function (pair) {
      var name = pair[0];
      var value = pair[1];
      if (!byName[name]) byName[name] = [];
      byName[name].push(value);
    });
    return byName;
  }

  function resetSearchPicker(select) {
    if (!select) return;
    if (select.dataset.entityPickerReady === "true") {
      delete select.dataset.entityPickerReady;
      var nextEl = select.nextElementSibling;
      if (nextEl && nextEl.classList && nextEl.classList.contains("cv-search-picker")) {
        nextEl.parentNode.removeChild(nextEl);
      }
    }
  }

  function initSearchPickers(scope) {
    if (window.CV && window.CV.picker && window.CV.picker.initSearch) {
      window.CV.picker.initSearch(scope || document);
    }
  }

  function setNativeSelectValue(select, value) {
    if (!select) return;
    select.value = value;
    /* select nativo fica escondido atras de um trigger customizado
       (cv-custom-select) que só atualiza o rótulo visível ao ouvir
       'change' no <select> — setar .value sozinho não é suficiente. */
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function setMultiSelectValues(select, ids, form) {
    if (!select) return;
    var idSet = new Set((ids || []).map(String));
    Array.prototype.slice.call(select.options).forEach(function (opt) {
      opt.selected = idSet.has(String(opt.value));
    });
    resetSearchPicker(select);
    initSearchPickers(form);
  }

  function applyDraft(form, draft) {
    ["placa", "modelo"].forEach(function (name) {
      if (!draft[name] || !draft[name].length) return;
      var input = form.querySelector('[name="' + name + '"]');
      if (input) input.value = draft[name][0];
    });

    if (draft.tipo && draft.tipo.length) {
      setNativeSelectValue(form.querySelector('select[name="tipo"]'), draft.tipo[0]);
    }

    if (draft.combustivel && draft.combustivel.length) {
      setNativeSelectValue(form.querySelector('select[name="combustivel"]'), draft.combustivel[0]);
    }

    if (draft.unidade && draft.unidade.length) {
      var unidadeSelect = form.querySelector('select[name="unidade"]');
      if (unidadeSelect) {
        unidadeSelect.value = draft.unidade[0];
        resetSearchPicker(unidadeSelect);
        initSearchPickers(form);
      }
    }

    if (draft.motoristas && draft.motoristas.length) {
      setMultiSelectValues(form.querySelector('select[name="motoristas"]'), draft.motoristas, form);
    }
  }

  function bindDraftAutosaveLinks(form) {
    form.addEventListener("click", function (event) {
      var link = event.target.closest('[data-autosave-link="1"]');
      if (!link || !form.contains(link)) return;
      saveDraft(form);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-viatura-form]");
    if (!form) return;

    var draft = takeDraft();
    if (draft) applyDraft(form, draft);

    bindDraftAutosaveLinks(form);
  });
})();
