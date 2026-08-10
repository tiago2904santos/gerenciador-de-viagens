(function () {
  const storageKey = "centralViagens.sidebar.openItems";

  function readOpenItems() {
    try {
      return new Set(JSON.parse(localStorage.getItem(storageKey) || "[]"));
    } catch (_error) {
      return new Set();
    }
  }

  function writeOpenItems(openItems) {
    localStorage.setItem(storageKey, JSON.stringify(Array.from(openItems)));
  }

  function isCadastrosPath() {
    const p = window.location.pathname;
    return p === "/cadastros" || p.startsWith("/cadastros/");
  }

  function setOpenState(item, isOpen) {
    const toggle = item.querySelector("[data-sidebar-toggle]");
    const accordion = item.querySelector(".sidebar-accordion");
    item.classList.toggle("is-open", isOpen);
    if (toggle) {
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }
    if (accordion) {
      accordion.hidden = !isOpen;
    }
  }

  function getCollapsibleItems() {
    return document.querySelectorAll(".sidebar-item--collapsible");
  }

  function closeAllCollapsible(openItems) {
    getCollapsibleItems().forEach(function (item) {
      const itemId = item.getAttribute("data-sidebar-item");
      setOpenState(item, false);
      if (itemId) {
        openItems.delete(itemId);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    let openItems = readOpenItems();
    const onCadastros = isCadastrosPath();
    const mobileQuery = window.matchMedia("(max-width: 840px)");
    const sidebar = document.querySelector("[data-sidebar]");
    const drawerToggles = document.querySelectorAll("[data-sidebar-drawer-toggle]");
    const drawerCloseButtons = document.querySelectorAll("[data-sidebar-drawer-close]");
    let drawerOpener = null;

    function drawerIsOpen() {
      return document.body.classList.contains("has-sidebar-open");
    }

    function setDrawerOpen(isOpen, restoreFocus) {
      if (!sidebar || !drawerToggles.length) return;

      const shouldOpen = mobileQuery.matches && isOpen;
      document.body.classList.toggle("has-sidebar-open", shouldOpen);
      drawerToggles.forEach(function (toggle) {
        toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
        toggle.setAttribute("aria-label", shouldOpen ? "Fechar menu principal" : "Abrir menu principal");
      });

      if (mobileQuery.matches) {
        sidebar.inert = !shouldOpen;
        sidebar.setAttribute("aria-hidden", shouldOpen ? "false" : "true");
      } else {
        sidebar.inert = false;
        sidebar.removeAttribute("aria-hidden");
      }

      if (shouldOpen) {
        drawerOpener = document.activeElement;
        const closeButton = sidebar.querySelector(".sidebar-drawer-close");
        window.requestAnimationFrame(function () {
          if (closeButton) closeButton.focus();
        });
      } else if (restoreFocus && drawerOpener && typeof drawerOpener.focus === "function") {
        drawerOpener.focus();
        drawerOpener = null;
      }
    }

    function syncDrawerMode() {
      setDrawerOpen(false, false);
    }

    drawerToggles.forEach(function (toggle) {
      toggle.addEventListener("click", function () {
        setDrawerOpen(!drawerIsOpen(), false);
      });
    });

    drawerCloseButtons.forEach(function (button) {
      button.addEventListener("click", function () {
        setDrawerOpen(false, true);
      });
    });

    if (typeof mobileQuery.addEventListener === "function") {
      mobileQuery.addEventListener("change", syncDrawerMode);
    } else if (typeof mobileQuery.addListener === "function") {
      mobileQuery.addListener(syncDrawerMode);
    }
    syncDrawerMode();

    if (!onCadastros) {
      closeAllCollapsible(openItems);
      writeOpenItems(openItems);
    }

    getCollapsibleItems().forEach(function (item) {
      const itemId = item.getAttribute("data-sidebar-item");

      if (onCadastros) {
        setOpenState(item, true);
        if (itemId) {
          openItems.add(itemId);
        }
      }

      const toggle = item.querySelector("[data-sidebar-toggle]");
      if (!toggle) {
        return;
      }

      toggle.addEventListener("click", function (event) {
        event.stopPropagation();
        const shouldOpen = !item.classList.contains("is-open");
        setOpenState(item, shouldOpen);
        if (itemId) {
          if (shouldOpen) {
            openItems.add(itemId);
          } else {
            openItems.delete(itemId);
          }
          writeOpenItems(openItems);
        }
      });
    });

    if (onCadastros) {
      writeOpenItems(openItems);
    }

    document.querySelectorAll("[data-sidebar-root-link]").forEach(function (link) {
      link.addEventListener("click", function () {
        openItems = readOpenItems();
        closeAllCollapsible(openItems);
        writeOpenItems(openItems);
        if (mobileQuery.matches) setDrawerOpen(false, false);
      });
    });

    document.querySelectorAll("[data-sidebar-panel-link]").forEach(function (link) {
      link.addEventListener("click", function () {
        if (mobileQuery.matches) setDrawerOpen(false, false);
      });
    });

    document.addEventListener("keydown", function (event) {
      if (!mobileQuery.matches || !drawerIsOpen() || !sidebar) return;

      if (event.key === "Escape") {
        event.preventDefault();
        setDrawerOpen(false, true);
        return;
      }

      if (event.key !== "Tab") return;
      // `tabIndex >= 0` e nao o seletor: `button:not([disabled])` casava com
      // botao `tabindex="-1"`, que o navegador nunca foca por Tab. O seletor
      // so descartava `tabindex="-1"` no ramo generico `[tabindex]`.
      //
      // Isso quebrava a armadilha no TEMA ESCURO (`NOVO-85`). O seletor de tema
      // e o ultimo bloco da barra e e um radiogroup rotativo: `theme-toggle.js`
      // deixa `tabindex="0"` so no tema ativo. No claro, o botao "Claro" e o
      // ultimo do DOM E o ultimo tabulavel, entao `last` acertava por acidente.
      // No escuro "Claro" vira `-1` mas continua sendo o `last` calculado, o
      // ultimo tabulavel de verdade passa a ser "Escuro", a comparacao com
      // `activeElement` da falso, o `preventDefault()` nao roda — e o foco sai
      // da gaveta para o conteudo atras do scrim, com o `body` travado.
      //
      // Vale tambem antes de o `theme-toggle.js` rodar: o template nasce com os
      // DOIS botoes em `tabindex="-1"`, e ele desiste cedo se `CV.theme` faltar.
      const focusable = Array.from(sidebar.querySelectorAll(
        'a[href], button, input, select, textarea, [tabindex]'
      )).filter(function (element) {
        if (element.disabled) return false;
        if (element.tabIndex < 0) return false;
        return !element.hidden && element.getAttribute("aria-hidden") !== "true";
      });
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  });
})();
