(function () {
  "use strict";

  /**
   * Ancora um menu em position:fixed no body para evitar corte por overflow:hidden dos pais.
   */
  function attachFloatingMenu(menu, anchor) {
    if (!menu || !anchor) return function () {};

    let placeholder = null;

    function position() {
      const rect = anchor.getBoundingClientRect();
      menu.style.position = "fixed";
      menu.style.left = `${rect.left}px`;
      menu.style.top = `${rect.bottom}px`;
      menu.style.width = `${Math.max(rect.width, 0)}px`;
      menu.style.right = "auto";
      menu.style.minWidth = `${Math.max(rect.width, 0)}px`;
      menu.classList.add("cv-floating-dropdown--active");
    }

    function open() {
      if (menu.dataset.cvFloatingActive === "true") {
        position();
        return;
      }
      placeholder = document.createComment("cv-floating-dropdown");
      menu.parentNode.insertBefore(placeholder, menu);
      // O menu sai da árvore do anchor ao ir para o body, então tokens de tema
      // escopados por atributo (ex.: [data-oficio-wizard-step1]) deixam de
      // cascatear. Copiamos o marcador para o menu preservar o tema do anchor.
      if (anchor.closest("[data-oficio-wizard-step1]")) {
        menu.setAttribute("data-oficio-wizard-step1", "");
      }
      document.body.appendChild(menu);
      menu.dataset.cvFloatingActive = "true";
      position();
      window.addEventListener("resize", position);
      window.addEventListener("scroll", position, true);
    }

    function close() {
      if (menu.dataset.cvFloatingActive !== "true") return;
      window.removeEventListener("resize", position);
      window.removeEventListener("scroll", position, true);
      menu.classList.remove("cv-floating-dropdown--active");
      menu.style.position = "";
      menu.style.left = "";
      menu.style.top = "";
      menu.style.width = "";
      menu.style.right = "";
      menu.style.minWidth = "";
      delete menu.dataset.cvFloatingActive;
      menu.removeAttribute("data-oficio-wizard-step1");
      if (placeholder && placeholder.parentNode) {
        placeholder.parentNode.insertBefore(menu, placeholder);
        placeholder.remove();
      }
      placeholder = null;
    }

    return { open, close, reposition: position };
  }

  window.CvFloatingDropdown = { attach: attachFloatingMenu };
})();
