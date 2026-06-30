(function () {
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

  function buildData(form, source) {
    var data = new FormData();
    var token = csrfFromForm(form);
    if (token) data.append("csrfmiddlewaretoken", token);
    var numero = form.querySelector('[name="numero_solicitacao"]');
    if (numero) data.append("numero_solicitacao", numero.value || "");
    var input = fileInputFromSource(source);
    if (input && input.files && input.files.length) {
      Array.prototype.forEach.call(input.files, function (file) {
        data.append(input.name, file);
      });
    }
    if (source && source.type === "checkbox" && source.checked) {
      data.append(source.name, "on");
    }
    return data;
  }

  function fileInputFromSource(source) {
    if (!source) return null;
    if (source.type === "file") return source;
    var picker = source.closest ? source.closest("[data-file-picker]") : null;
    return picker ? picker.querySelector('input[type="file"]') : null;
  }

  function updatePickerState(source) {
    if (!source || source.type !== "file") return;
    var picker = source.closest("[data-file-picker]");
    var nameTarget = picker ? picker.querySelector("[data-file-picker-name]") : null;
    var uploadButton = picker ? picker.querySelector("[data-file-upload-button]") : null;
    if (!nameTarget) return;
    var count = source.files ? source.files.length : 0;
    var hasFiles = count > 0;
    if (count === 1) {
      nameTarget.textContent = source.files[0].name;
    } else {
      nameTarget.textContent = hasFiles
      ? count + " arquivos selecionados"
      : nameTarget.getAttribute("data-default-label") || "Nenhum arquivo selecionado";
    }
    nameTarget.classList.toggle("prestacao-file-picker__value--selected", hasFiles);
    if (uploadButton) uploadButton.disabled = !hasFiles;
    renderSelectionDropdown(source);
  }

  function updateSolicitacaoTitle(form) {
    var title = document.querySelector("[data-solicitacao-title]");
    var input = form.querySelector('[name="numero_solicitacao"]');
    if (!title || !input) return;
    var value = (input.value || "").trim();
    title.textContent = value ? "Solicitação " + value : "Solicitação";
  }

  function formatFileSize(bytes) {
    if (!Number.isFinite(bytes)) return "Selecionado";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1).replace(".0", "") + " KB";
    return (bytes / 1048576).toFixed(1).replace(".0", "") + " MB";
  }

  function renderSelectionDropdown(input) {
    var picker = input.closest("[data-file-picker]");
    var dropdown = picker ? picker.querySelector("[data-file-selection-dropdown]") : null;
    var toggle = picker ? picker.querySelector("[data-file-selection-toggle]") : null;
    var summary = picker ? picker.querySelector("[data-file-selection-summary]") : null;
    var menu = picker ? picker.querySelector("[data-file-selection-menu]") : null;
    var list = picker ? picker.querySelector("[data-file-selection-list]") : null;
    var template = picker ? picker.querySelector("[data-file-selection-template]") : null;
    var inlineSlot = picker ? picker.querySelector("[data-file-inline-actions]") : null;
    if (!dropdown || !toggle || !summary || !menu || !list || !template) return;

    revokeSelectionUrls(picker);
    var files = input.files ? Array.prototype.slice.call(input.files) : [];
    list.innerHTML = "";
    if (inlineSlot) inlineSlot.innerHTML = "";

    if (inlineSlot) { inlineSlot.innerHTML = ""; inlineSlot.hidden = true; }

    if (!files.length) {
      dropdown.hidden = true;
      return;
    }

    files.forEach(function (file, index) {
      var row = template.content.firstElementChild.cloneNode(true);
      var name = row.querySelector("[data-file-selection-name]");
      var size = row.querySelector("[data-file-selection-size]");
      var preview = row.querySelector("[data-file-preview-selection]");
      var url = URL.createObjectURL(file);
      row.setAttribute("data-file-selection-index", String(index));
      picker._selectionObjectUrls.push(url);
      if (name) {
        name.textContent = file.name;
        name.setAttribute("title", file.name);
      }
      if (size) size.textContent = "Selecionado · " + formatFileSize(file.size);
      if (preview) preview.setAttribute("href", url);
      list.appendChild(row);
    });

    if (toggle) toggle.hidden = true;
    menu.hidden = false;
    dropdown.hidden = false;
  }

  function setSelectionDropdownOpen(dropdown, isOpen) {
    var toggle = dropdown ? dropdown.querySelector("[data-file-selection-toggle]") : null;
    var menu = dropdown ? dropdown.querySelector("[data-file-selection-menu]") : null;
    if (!toggle || !menu) return;
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    menu.hidden = !isOpen;
    dropdown.classList.toggle("prestacao-file-selection--open", isOpen);
  }

  function toggleSelectionDropdown(button) {
    var dropdown = button.closest("[data-file-selection-dropdown]");
    var expanded = button.getAttribute("aria-expanded") === "true";
    setSelectionDropdownOpen(dropdown, !expanded);
  }

  function revokeSelectionUrls(picker) {
    if (!picker) return;
    var urls = picker._selectionObjectUrls || [];
    urls.forEach(function (url) {
      URL.revokeObjectURL(url);
    });
    picker._selectionObjectUrls = [];
  }

  function setSelectedFiles(input, files) {
    if (!input) return;
    if (!files.length) {
      input.value = "";
      updatePickerState(input);
      return;
    }
    try {
      var transfer = new DataTransfer();
      files.forEach(function (file) {
        transfer.items.add(file);
      });
      input.files = transfer.files;
    } catch (error) {
      input.value = "";
      console.error("[autosave] atualizar seleção", error);
    }
    updatePickerState(input);
  }

  function fileSelectionIndex(button) {
    if (button.closest("[data-file-inline-actions]")) return 0;
    var row = button.closest("[data-file-selection-index]");
    if (!row) return -1;
    var index = Number(row.getAttribute("data-file-selection-index"));
    return Number.isFinite(index) ? index : -1;
  }

  function removeSelectedFile(button) {
    var input = fileInputFromSource(button);
    var index = fileSelectionIndex(button);
    if (!input || index < 0 || !input.files || index >= input.files.length) return;
    var files = Array.prototype.slice.call(input.files);
    files.splice(index, 1);
    setSelectedFiles(input, files);
  }

  function applySuccessfulFileChange(source) {
    if (!source) return;
    var widget = source.closest(".prestacao-file-widget");
    if (!widget) return;
    var input = fileInputFromSource(source);
    if (input) clearSelection(input);
    if (source.type === "checkbox" && source.name.slice(-6) === "-clear" && source.checked) {
      var current = widget.querySelector(".prestacao-file-widget__current");
      if (current) current.hidden = true;
      widget.classList.remove("prestacao-file-widget--has-file");
      source.checked = false;
    }
  }

  function send(form, source) {
    var url = form.getAttribute("data-file-autosave-url") || "";
    if (!url) return;
    setState(form, "saving");
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": csrfFromForm(form),
        "X-Requested-With": "XMLHttpRequest"
      },
      body: buildData(form, source)
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
        console.error("[autosave] arquivo", error);
      });
  }

  function init() {
    var forms = document.querySelectorAll("form[data-file-autosave-url]");
    Array.prototype.forEach.call(forms, function (form) {
      updateSolicitacaoTitle(form);

      form.addEventListener("input", function (event) {
        var target = event.target;
        if (target && target.name === "numero_solicitacao") {
          updateSolicitacaoTitle(form);
        }
      });

      form.addEventListener("change", function (event) {
        var target = event.target;
        if (!target || !target.name) return;
        if (target.name === "numero_solicitacao") {
          updateSolicitacaoTitle(form);
        }
        updatePickerState(target);
        if (target.type !== "file" && target.name.slice(-6) === "-clear") {
          send(form, target);
        }
      });

      form.addEventListener("click", function (event) {
        var selectionToggle = event.target.closest("[data-file-selection-toggle]");
        if (selectionToggle) {
          toggleSelectionDropdown(selectionToggle);
          return;
        }

        var removeSelectionButton = event.target.closest("[data-file-remove-selection]");
        if (removeSelectionButton) {
          removeSelectedFile(removeSelectionButton);
          return;
        }

        var clearSelectionButton = event.target.closest("[data-file-clear-selection]");
        if (clearSelectionButton) {
          var input = fileInputFromSource(clearSelectionButton);
          if (input) clearSelection(input);
          return;
        }

        var uploadButton = event.target.closest("[data-file-upload-button]");
        if (uploadButton) {
          var uploadInput = fileInputFromSource(uploadButton);
          if (uploadInput && uploadInput.files && uploadInput.files.length) {
            send(form, uploadButton);
          }
          return;
        }

        var deleteButton = event.target.closest("[data-file-delete-url]");
        if (deleteButton) {
          deleteAnexo(form, deleteButton);
        }
      });
    });
  }

  function clearSelection(input) {
    input.value = "";
    updatePickerState(input);
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
        "X-Requested-With": "XMLHttpRequest"
      }
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data || !data.ok) {
            throw new Error((data && data.message) || "Falha ao excluir o anexo.");
          }
          var row = button.closest("[data-documento-anexo-id]");
          var list = row ? row.closest("[data-file-list]") : null;
          if (row) row.remove();
          if (list && !list.querySelector("[data-documento-anexo-id]")) {
            list.remove();
          }
          setState(form, "saved");
        });
      })
      .catch(function (error) {
        setState(form, "error");
        console.error("[autosave] excluir anexo", error);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
