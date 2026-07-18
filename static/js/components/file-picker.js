(function () {
  "use strict";

  var BOUND = "data-file-picker-bound";

  function formatFileSize(bytes) {
    if (!Number.isFinite(bytes)) return "Selecionado";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1).replace(".0", "") + " KB";
    return (bytes / 1048576).toFixed(1).replace(".0", "") + " MB";
  }

  function pickersWithin(root) {
    var scope = root && root.querySelectorAll ? root : document;
    var pickers = Array.prototype.slice.call(scope.querySelectorAll("[data-file-picker]"));
    if (scope.matches && scope.matches("[data-file-picker]")) pickers.unshift(scope);
    return pickers;
  }

  function inputFor(picker) {
    return picker && picker.querySelector('input[type="file"][data-file-native]');
  }

  function revokeUrls(picker) {
    (picker._fpObjectUrls || []).forEach(function (url) { URL.revokeObjectURL(url); });
    picker._fpObjectUrls = [];
  }

  function closeSelection(picker) {
    var toggle = picker.querySelector("[data-file-selection-toggle]");
    var menu = picker.querySelector("[data-file-selection-menu]");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
    if (menu && toggle && !toggle.hidden) menu.hidden = true;
    picker.classList.remove("is-selection-open");
  }

  function setSelectionOpen(picker, open) {
    var toggle = picker.querySelector("[data-file-selection-toggle]");
    var menu = picker.querySelector("[data-file-selection-menu]");
    if (!toggle || !menu || toggle.hidden) return;
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    menu.hidden = !open;
    picker.classList.toggle("is-selection-open", open);
  }

  function buildListItem(template, file, index, objectUrls) {
    var row = template.content.firstElementChild.cloneNode(true);
    var name = row.querySelector("[data-file-selection-name]");
    var size = row.querySelector("[data-file-selection-size]");
    var preview = row.querySelector("[data-file-preview-selection]");
    var url = URL.createObjectURL(file);
    row.setAttribute("data-file-selection-index", String(index));
    objectUrls.push(url);
    if (name) {
      name.textContent = file.name;
      name.title = file.name;
    }
    if (size) size.textContent = "Selecionado · " + formatFileSize(file.size);
    if (preview) preview.href = url;
    return row;
  }

  function renderSelection(picker, input) {
    var dropdown = picker.querySelector("[data-file-selection-dropdown]");
    var summary = picker.querySelector("[data-file-selection-summary]");
    var menu = picker.querySelector("[data-file-selection-menu]");
    var list = picker.querySelector("[data-file-selection-list]");
    var template = picker.querySelector("[data-file-selection-template]");
    var toggle = picker.querySelector("[data-file-selection-toggle]");
    var inlineSlot = picker.querySelector("[data-file-inline-actions]");
    if (!dropdown || !summary || !menu || !list || !template || !toggle) return;

    var wasOpen = toggle.getAttribute("aria-expanded") === "true";
    var files = input.files ? Array.prototype.slice.call(input.files) : [];
    revokeUrls(picker);
    list.innerHTML = "";
    if (inlineSlot) {
      inlineSlot.innerHTML = "";
      inlineSlot.hidden = true;
    }

    if (!files.length) {
      dropdown.hidden = true;
      closeSelection(picker);
      return;
    }

    files.forEach(function (file, index) {
      list.appendChild(buildListItem(template, file, index, picker._fpObjectUrls));
    });

    summary.textContent = files.length + (files.length === 1 ? " arquivo selecionado" : " arquivos selecionados");
    toggle.hidden = files.length === 1;
    menu.hidden = files.length > 1 && !wasOpen;
    toggle.setAttribute("aria-expanded", files.length > 1 && wasOpen ? "true" : "false");
    picker.classList.toggle("is-selection-open", files.length > 1 && wasOpen);
    dropdown.hidden = false;
  }

  function update(picker) {
    var input = inputFor(picker);
    if (!input) return;
    var files = input.files ? Array.prototype.slice.call(input.files) : [];
    var nameTarget = picker.querySelector("[data-file-picker-name]");
    var uploadButton = picker.querySelector("[data-file-upload-button]");
    var status = picker.querySelector("[data-file-picker-status]");
    var hasFiles = files.length > 0;

    if (nameTarget) {
      nameTarget.textContent = files.length === 1
        ? files[0].name
        : files.length > 1
          ? files.length + " arquivos selecionados"
          : nameTarget.getAttribute("data-default-label") || "Nenhum arquivo selecionado";
      nameTarget.classList.toggle("prestacao-file-picker__value--selected", hasFiles);
    }
    if (status) {
      status.textContent = hasFiles
        ? (files.length === 1 ? files[0].name + " selecionado" : files.length + " arquivos selecionados")
        : "Nenhum arquivo selecionado";
    }
    if (uploadButton) uploadButton.disabled = !hasFiles;
    picker.classList.toggle("is-selected", hasFiles);
    picker.classList.remove("is-error");
    renderSelection(picker, input);
    picker.dispatchEvent(new CustomEvent("cv:file-picker:change", {
      bubbles: true,
      detail: { files: files, input: input },
    }));
  }

  function replaceFiles(input, files, dispatchChange) {
    if (!input) return false;
    if (!files.length) {
      input.value = "";
      if (dispatchChange) input.dispatchEvent(new Event("change", { bubbles: true }));
      else update(input.closest("[data-file-picker]"));
      return true;
    }
    try {
      var transfer = new DataTransfer();
      files.forEach(function (file) { transfer.items.add(file); });
      input.files = transfer.files;
      if (dispatchChange) input.dispatchEvent(new Event("change", { bubbles: true }));
      else update(input.closest("[data-file-picker]"));
      return true;
    } catch (error) {
      input.value = "";
      update(input.closest("[data-file-picker]"));
      return false;
    }
  }

  function clear(target) {
    var picker = target && target.matches && target.matches("[data-file-picker]")
      ? target
      : target && target.closest ? target.closest("[data-file-picker]") : null;
    var input = inputFor(picker);
    return input ? replaceFiles(input, []) : false;
  }

  function removeFile(picker, index) {
    var input = inputFor(picker);
    if (!input || !input.files || index < 0 || index >= input.files.length) return;
    var files = Array.prototype.slice.call(input.files);
    files.splice(index, 1);
    replaceFiles(input, files);
  }

  function setBusy(target, busy) {
    var picker = target && target.matches && target.matches("[data-file-picker]")
      ? target
      : target && target.closest ? target.closest("[data-file-picker]") : null;
    if (!picker) return;
    var uploadButton = picker.querySelector("[data-file-upload-button]");
    picker.classList.toggle("is-busy", Boolean(busy));
    picker.setAttribute("aria-busy", busy ? "true" : "false");
    if (uploadButton) uploadButton.disabled = Boolean(busy) || !inputFor(picker).files.length;
  }

  function initPicker(picker) {
    if (!picker || picker.getAttribute(BOUND) === "true") return false;
    var input = inputFor(picker);
    if (!input) return false;
    picker.setAttribute(BOUND, "true");
    picker._fpObjectUrls = [];
    var status = picker.querySelector("[data-file-picker-status]");
    if (status && status.id) {
      var describedBy = (input.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
      if (describedBy.indexOf(status.id) === -1) describedBy.push(status.id);
      input.setAttribute("aria-describedby", describedBy.join(" "));
    }

    input.addEventListener("change", function () { update(picker); });

    picker.addEventListener("click", function (event) {
      var toggle = event.target.closest("[data-file-selection-toggle]");
      if (toggle) {
        event.preventDefault();
        setSelectionOpen(picker, toggle.getAttribute("aria-expanded") !== "true");
        return;
      }
      var removeButton = event.target.closest("[data-file-remove-selection]");
      if (removeButton) {
        event.preventDefault();
        var row = removeButton.closest("[data-file-selection-index]");
        removeFile(picker, row ? Number(row.getAttribute("data-file-selection-index")) : 0);
        return;
      }
      if (event.target.closest("[data-file-clear-selection]")) {
        event.preventDefault();
        clear(picker);
      }
    });

    picker.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeSelection(picker);
    });

    ["dragenter", "dragover"].forEach(function (eventName) {
      picker.addEventListener(eventName, function (event) {
        event.preventDefault();
        if (!input.disabled) picker.classList.add("is-dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (eventName) {
      picker.addEventListener(eventName, function () { picker.classList.remove("is-dragover"); });
    });
    picker.addEventListener("drop", function (event) {
      event.preventDefault();
      if (input.disabled || !event.dataTransfer || !event.dataTransfer.files.length) return;
      var files = Array.prototype.slice.call(event.dataTransfer.files);
      if (!input.multiple) files = files.slice(0, 1);
      replaceFiles(input, files, true);
    });

    var form = picker.closest("form");
    if (form) {
      form.addEventListener("submit", function () {
        if (input.files && input.files.length) setBusy(picker, true);
      });
    }
    update(picker);
    return true;
  }

  function init(root) {
    pickersWithin(root).forEach(initPicker);
  }

  document.addEventListener("click", function (event) {
    document.querySelectorAll("[data-file-picker].is-selection-open").forEach(function (picker) {
      if (!picker.contains(event.target)) closeSelection(picker);
    });
  });
  window.addEventListener("pagehide", function () {
    document.querySelectorAll("[data-file-picker]").forEach(revokeUrls);
  });

  window.CV = window.CV || {};
  window.CV.filePicker = {
    clear: clear,
    init: init,
    setBusy: setBusy,
    update: update,
  };
  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("filePicker", init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
}());
