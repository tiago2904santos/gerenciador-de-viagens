(function () {
  function preencher(select) {
    var alvo = select.getAttribute("data-rt-target");
    if (!alvo) return;
    var textarea = document.querySelector('[data-rt-textarea="' + alvo + '"]');
    if (!textarea) return;
    var opt = select.options[select.selectedIndex];
    var texto = opt ? (opt.getAttribute("data-texto-modelo") || "").trim() : "";
    if (!texto) return;
    textarea.value = texto;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function setOtherVisible(wrapper, visible) {
    if (!wrapper) return;
    wrapper.hidden = !visible;
    wrapper.classList.toggle("is-open", visible);
  }

  function syncOther(select) {
    var campo = select.getAttribute("data-rt-other-select");
    if (!campo) return;
    var otherValue = select.getAttribute("data-rt-other-value") || "__outro__";
    var wrapper = document.querySelector('[data-rt-other-wrapper="' + campo + '"]');
    var input = document.querySelector('[data-rt-other-input="' + campo + '"]');
    var visible = select.value === otherValue;
    setOtherVisible(wrapper, visible);
    if (visible && input) {
      input.removeAttribute("disabled");
    } else if (input) {
      input.setAttribute("disabled", "disabled");
      input.value = "";
    }
  }

  function init() {
    var selects = document.querySelectorAll('[data-rt-modelo-select="true"]');
    Array.prototype.forEach.call(selects, function (sel) {
      sel.addEventListener("change", function () {
        preencher(this);
      });
    });
    var otherSelects = document.querySelectorAll("[data-rt-other-select]");
    Array.prototype.forEach.call(otherSelects, function (sel) {
      sel.addEventListener("change", function () {
        syncOther(this);
      });
      syncOther(sel);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
