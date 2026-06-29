(function () {
  function init() {
    document.querySelectorAll("[data-oficio-item]").forEach(function (item) {
      var btn = item.querySelector("[data-oficio-toggle]");
      if (!btn) return;

      btn.addEventListener("click", function () {
        var open = item.classList.toggle("is-open");
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
