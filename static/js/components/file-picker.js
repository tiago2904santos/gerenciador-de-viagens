(function () {
  function formatFileSize(bytes) {
    if (!Number.isFinite(bytes)) return "Selecionado";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1).replace(".0", "") + " KB";
    return (bytes / 1048576).toFixed(1).replace(".0", "") + " MB";
  }

  function revokeUrls(picker) {
    (picker._fpObjectUrls || []).forEach(function (u) { URL.revokeObjectURL(u); });
    picker._fpObjectUrls = [];
  }

  function renderDropdown(picker, input) {
    var dropdown = picker.querySelector("[data-file-selection-dropdown]");
    var summary  = picker.querySelector("[data-file-selection-summary]");
    var menu     = picker.querySelector("[data-file-selection-menu]");
    var list     = picker.querySelector("[data-file-selection-list]");
    var tpl      = picker.querySelector("[data-file-selection-template]");
    if (!dropdown || !summary || !menu || !list || !tpl) return;

    revokeUrls(picker);
    var files = input.files ? Array.prototype.slice.call(input.files) : [];
    list.innerHTML = "";
    dropdown.hidden = !files.length;
    if (!files.length) return;

    summary.textContent = files.length === 1 ? files[0].name : files.length + " arquivos selecionados";
    var toggle = picker.querySelector("[data-file-selection-toggle]");
    if (toggle) toggle.setAttribute("aria-expanded", "true");
    menu.hidden = false;

    files.forEach(function (file, index) {
      var row     = tpl.content.firstElementChild.cloneNode(true);
      var nameEl  = row.querySelector("[data-file-selection-name]");
      var sizeEl  = row.querySelector("[data-file-selection-size]");
      var preview = row.querySelector("[data-file-preview-selection]");
      var url     = URL.createObjectURL(file);
      row.setAttribute("data-file-selection-index", String(index));
      picker._fpObjectUrls.push(url);
      if (nameEl) { nameEl.textContent = file.name; nameEl.title = file.name; }
      if (sizeEl) sizeEl.textContent = "Selecionado · " + formatFileSize(file.size);
      if (preview) preview.href = url;
      list.appendChild(row);
    });
  }

  function updatePickerState(picker, input) {
    var nameTarget   = picker.querySelector("[data-file-picker-name]");
    var clearButton  = picker.querySelector("[data-file-clear-selection]");
    var uploadButton = picker.querySelector("[data-file-upload-button]");
    var count   = input.files ? input.files.length : 0;
    var hasFiles = count > 0;

    if (nameTarget) {
      nameTarget.textContent = count === 1
        ? input.files[0].name
        : count > 1
          ? count + " arquivos selecionados"
          : nameTarget.getAttribute("data-default-label") || "Nenhum arquivo selecionado";
      nameTarget.classList.toggle("prestacao-file-picker__value--selected", hasFiles);
    }
    if (clearButton) clearButton.hidden = !hasFiles;
    if (uploadButton) uploadButton.disabled = !hasFiles;
    renderDropdown(picker, input);
  }

  function clearInput(picker, input) {
    input.value = "";
    updatePickerState(picker, input);
  }

  function removeFile(picker, input, index) {
    if (!input.files || index < 0 || index >= input.files.length) return;
    var files = Array.prototype.slice.call(input.files);
    files.splice(index, 1);
    try {
      var dt = new DataTransfer();
      files.forEach(function (f) { dt.items.add(f); });
      input.files = dt.files;
    } catch (e) { input.value = ""; }
    updatePickerState(picker, input);
  }

  function initPicker(picker) {
    picker._fpObjectUrls = [];
    var input = picker.querySelector('input[type="file"][data-file-native]');
    if (!input) return;

    input.addEventListener("change", function () {
      updatePickerState(picker, input);
    });

    picker.addEventListener("click", function (event) {
      var toggle = event.target.closest("[data-file-selection-toggle]");
      if (toggle) {
        var dropdown = toggle.closest("[data-file-selection-dropdown]");
        var expanded = toggle.getAttribute("aria-expanded") === "true";
        var menu = dropdown && dropdown.querySelector("[data-file-selection-menu]");
        toggle.setAttribute("aria-expanded", expanded ? "false" : "true");
        if (menu) menu.hidden = expanded;
        return;
      }

      var removeBtn = event.target.closest("[data-file-remove-selection]");
      if (removeBtn) {
        var row = removeBtn.closest("[data-file-selection-index]");
        var idx = row ? Number(row.getAttribute("data-file-selection-index")) : -1;
        removeFile(picker, input, idx);
        return;
      }

      var clearBtn = event.target.closest("[data-file-clear-selection]");
      if (clearBtn) { clearInput(picker, input); return; }
    });
  }

  function init() {
    document.querySelectorAll("[data-file-picker]").forEach(function (picker) {
      if (picker.closest("form[data-file-autosave-url]")) return;
      initPicker(picker);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
