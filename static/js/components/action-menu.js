(function () {
  "use strict";

  function closeAll() {
    document.querySelectorAll(".cv-action-menu--open").forEach(function (menu) {
      menu.classList.remove("cv-action-menu--open");
      menu.hidden = true;
      var trigger = document.querySelector('[data-action-menu-target="' + menu.id + '"]');
      if (trigger) trigger.setAttribute("aria-expanded", "false");
    });
  }

  function position(trigger, menu) {
    var rect = trigger.getBoundingClientRect();
    var menuRect = menu.getBoundingClientRect();
    var top = rect.top - menuRect.height - 6;
    if (top < 8) top = rect.bottom + 6;
    var left = rect.right - menuRect.width;
    if (left < 8) left = rect.left;
    menu.style.position = "fixed";
    menu.style.top = top + "px";
    menu.style.left = left + "px";
  }

  document.addEventListener("click", function (event) {
    var trigger = event.target.closest("[data-action-menu-trigger]");
    if (trigger) {
      event.preventDefault();
      var menu = document.getElementById(trigger.getAttribute("data-action-menu-target"));
      if (!menu) return;
      var wasOpen = menu.classList.contains("cv-action-menu--open");
      closeAll();
      if (!wasOpen) {
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
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeAll();
  });

  window.addEventListener("scroll", closeAll, true);
  window.addEventListener("resize", closeAll);
})();
