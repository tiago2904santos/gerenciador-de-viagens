(function () {
  "use strict";

  window.CV = window.CV || {};

  var ownerByMenu = typeof WeakMap !== "undefined" ? new WeakMap() : new Map();
  var listenersBound = false;

  function triggerFor(menu) {
    if (!menu || !menu.id) return null;
    return document.querySelector('[data-action-menu-target="' + menu.id + '"]');
  }

  function close(menu) {
    if (!menu) return;
    menu.classList.remove("cv-action-menu--open");
    menu.hidden = true;
    var trigger = triggerFor(menu);
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  }

  function closeAll() {
    document.querySelectorAll(".cv-action-menu--open").forEach(close);
  }

  function rememberOwner(menu) {
    if (ownerByMenu.has(menu)) return;
    ownerByMenu.set(menu, {
      parent: menu.parentNode,
      nextSibling: menu.nextSibling,
    });
  }

  function restoreOwner(menu) {
    var owner = ownerByMenu.get(menu);
    close(menu);
    if (!owner || !owner.parent) return;
    if (owner.nextSibling && owner.nextSibling.parentNode === owner.parent) {
      owner.parent.insertBefore(menu, owner.nextSibling);
    } else {
      owner.parent.appendChild(menu);
    }
    menu.style.removeProperty("position");
    menu.style.removeProperty("top");
    menu.style.removeProperty("left");
    ownerByMenu.delete(menu);
  }

  function position(trigger, menu) {
    menu.style.position = "fixed";
    menu.style.top = "0px";
    menu.style.left = "0px";
    var rect = trigger.getBoundingClientRect();
    var menuRect = menu.getBoundingClientRect();
    var top = rect.top - menuRect.height - 6;
    if (top < 8) top = rect.bottom + 6;
    var left = rect.right - menuRect.width;
    if (left < 8) left = rect.left;
    menu.style.top = top + "px";
    menu.style.left = left + "px";
  }

  function onClick(event) {
    var trigger = event.target.closest("[data-action-menu-trigger]");
    if (trigger) {
      event.preventDefault();
      var menu = document.getElementById(trigger.getAttribute("data-action-menu-target"));
      if (!menu) return;
      var wasOpen = menu.classList.contains("cv-action-menu--open");
      closeAll();
      if (!wasOpen) {
        rememberOwner(menu);
        if (menu.parentNode !== document.body) document.body.appendChild(menu);
        menu.hidden = false;
        menu.classList.add("cv-action-menu--open");
        trigger.setAttribute("aria-expanded", "true");
        position(trigger, menu);
      }
      return;
    }

    if (event.target.closest(".cv-action-menu")) {
      closeAll();
      return;
    }

    closeAll();
  }

  function onKeydown(event) {
    if (event.key === "Escape") closeAll();
  }

  function bindListeners() {
    if (listenersBound) return;
    listenersBound = true;
    document.addEventListener("click", onClick);
    document.addEventListener("keydown", onKeydown);
    window.addEventListener("scroll", closeAll, true);
    window.addEventListener("resize", closeAll);
  }

  function menusOwnedBy(root) {
    var menus = [];
    var triggers = [];
    if (root.matches && root.matches("[data-action-menu-trigger]")) triggers.push(root);
    if (root.querySelectorAll) {
      triggers = triggers.concat(
        Array.prototype.slice.call(root.querySelectorAll("[data-action-menu-trigger]"))
      );
    }
    triggers.forEach(function (trigger) {
      var menu = document.getElementById(trigger.getAttribute("data-action-menu-target"));
      if (menu && menus.indexOf(menu) === -1) menus.push(menu);
    });
    return menus;
  }

  function init() {
    bindListeners();
  }

  function destroy(root) {
    menusOwnedBy(root).forEach(restoreOwner);
  }

  window.CV.actionMenu = {
    closeAll: closeAll,
    destroy: destroy,
    init: init,
  };

  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("actionMenu", init, destroy);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
}());
