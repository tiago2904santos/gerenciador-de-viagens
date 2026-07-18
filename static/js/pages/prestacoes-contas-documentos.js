(function () {
  "use strict";

  var BOUND = "data-file-autosave-bound";

  function csrfFromForm(form) {
    if (window.CV && window.CV.http && typeof window.CV.http.getCsrfToken === "function") {
      return window.CV.http.getCsrfToken(form);
    }
    var tokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
    return tokenInput ? tokenInput.value : "";
  }

  function setState(form, state) {
    form.dataset.autosaveState = state;
  }

  function fileInputFromSource(source) {
    if (!source) return null;
    if (source.type === "file") return source;
    var picker = source.closest ? source.closest("[data-file-picker]") : null;
    return picker ? picker.querySelector('input[type="file"]') : null;
  }

  function buildData(form, source) {
    var data = new FormData();
    var token = csrfFromForm(form);
    if (token) data.append("csrfmiddlewaretoken", token);
    var numero = form.querySelector('[name="numero_solicitacao"]');
    if (numero) data.append("numero_solicitacao", numero.value || "");
    var input = fileInputFromSource(source);
    if (input && input.files && input.files.length) {
      Array.prototype.forEach.call(input.files, function (file) { data.append(input.name, file); });
    }
    if (source && source.type === "checkbox" && source.checked) data.append(source.name, "on");
    return data;
  }

  function updateSolicitacaoTitle(form) {
    var title = document.querySelector("[data-solicitacao-title]");
    var input = form.querySelector('[name="numero_solicitacao"]');
    if (!title || !input) return;
    var value = (input.value || "").trim();
    title.textContent = value ? "Solicitação " + value : "Solicitação";
  }

  function clearSelection(source) {
    var input = fileInputFromSource(source);
    if (!input) return;
    if (window.CV && window.CV.filePicker) window.CV.filePicker.clear(input);
    else {
      input.value = "";
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }

  function setPickerBusy(source, busy) {
    if (window.CV && window.CV.filePicker) window.CV.filePicker.setBusy(source, busy);
  }

  function applySuccessfulFileChange(source) {
    if (!source) return;
    var widget = source.closest("[data-file-picker]");
    if (widget) clearSelection(source);
    if (source.type === "checkbox" && source.name.slice(-6) === "-clear" && source.checked) {
      var current = source.closest(".prestacao-file-widget");
      if (current) {
        var currentFile = current.querySelector(".prestacao-file-widget__current");
        if (currentFile) currentFile.hidden = true;
        current.classList.remove("prestacao-file-widget--has-file");
      }
      source.checked = false;
    }
  }

  function send(form, source) {
    var url = form.getAttribute("data-file-autosave-url") || "";
    if (!url) return;
    setState(form, "saving");
    setPickerBusy(source, true);
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": csrfFromForm(form),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: buildData(form, source),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data || !data.ok) {
            throw new Error((data && data.message) || "Falha no autosave do arquivo.");
          }
          setState(form, "saved");
          applySuccessfulFileChange(source);
          if (source && source.hasAttribute && source.hasAttribute("data-file-upload-button")) {
            window.location.reload();
          }
        });
      })
      .catch(function (error) {
        setState(form, "error");
        setPickerBusy(source, false);
        console.error("[autosave] arquivo", error);
      });
  }

  function deleteAnexo(form, button) {
    var url = button.getAttribute("data-file-delete-url") || "";
    if (!url) return;
    setState(form, "saving");
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": csrfFromForm(form),
        "X-Requested-With": "XMLHttpRequest",
      },
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data || !data.ok) {
            throw new Error((data && data.message) || "Falha ao excluir o anexo.");
          }
          var row = button.closest("[data-documento-anexo-id]");
          var list = row ? row.closest("[data-file-list]") : null;
          if (row) row.remove();
          if (list && !list.querySelector("[data-documento-anexo-id]")) list.remove();
          setState(form, "saved");
        });
      })
      .catch(function (error) {
        setState(form, "error");
        console.error("[autosave] excluir anexo", error);
      });
  }

  function initForm(form) {
    if (!form || form.getAttribute(BOUND) === "true") return;
    form.setAttribute(BOUND, "true");
    updateSolicitacaoTitle(form);

    form.addEventListener("input", function (event) {
      if (event.target && event.target.name === "numero_solicitacao") updateSolicitacaoTitle(form);
    });
    form.addEventListener("change", function (event) {
      var target = event.target;
      if (!target || !target.name) return;
      if (target.name === "numero_solicitacao") updateSolicitacaoTitle(form);
      if (target.type !== "file" && target.name.slice(-6) === "-clear") send(form, target);
    });
    form.addEventListener("click", function (event) {
      var uploadButton = event.target.closest("[data-file-upload-button]");
      if (uploadButton) {
        event.preventDefault();
        var input = fileInputFromSource(uploadButton);
        if (input && input.files && input.files.length) send(form, uploadButton);
        return;
      }
      var deleteButton = event.target.closest("[data-file-delete-url]");
      if (deleteButton) {
        event.preventDefault();
        deleteAnexo(form, deleteButton);
      }
    });
  }

  function init(root) {
    var scope = root && root.querySelectorAll ? root : document;
    if (scope.matches && scope.matches("form[data-file-autosave-url]")) initForm(scope);
    scope.querySelectorAll("form[data-file-autosave-url]").forEach(initForm);
  }

  window.CV = window.CV || {};
  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("prestacaoDocumentos", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
}());
