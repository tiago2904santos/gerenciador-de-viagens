(function () {
  "use strict";

  var tooltip = null;
  var currentTarget = null;
  var viewportPadding = 8;
  var gap = 8;

  function ensureTooltip() {
    if (tooltip) return tooltip;
    tooltip = document.createElement("div");
    tooltip.className = "cv-global-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.hidden = true;
    document.body.appendChild(tooltip);
    document.documentElement.classList.add("has-cv-global-tooltips");
    return tooltip;
  }

  function getTarget(eventTarget) {
    if (!eventTarget || !eventTarget.closest) return null;
    return eventTarget.closest("[data-tooltip]");
  }

  function placeTooltip(target) {
    if (!tooltip || !target) return;

    var targetRect = target.getBoundingClientRect();
    var tooltipRect = tooltip.getBoundingClientRect();
    var left = targetRect.left + targetRect.width / 2 - tooltipRect.width / 2;
    var top = targetRect.top - tooltipRect.height - gap;

    left = Math.max(viewportPadding, Math.min(left, window.innerWidth - tooltipRect.width - viewportPadding));
    if (top < viewportPadding) {
      top = targetRect.bottom + gap;
    }
    top = Math.max(viewportPadding, Math.min(top, window.innerHeight - tooltipRect.height - viewportPadding));

    tooltip.style.left = left + "px";
    tooltip.style.top = top + "px";
  }

  function showTooltip(target) {
    if (!target || target.getAttribute("aria-expanded") === "true") return;
    var text = target.getAttribute("data-tooltip");
    if (!text) return;

    currentTarget = target;
    ensureTooltip();
    tooltip.textContent = text;
    tooltip.classList.toggle(
      "cv-global-tooltip--accent",
      target.classList.contains("cv-icon-btn--field-manage")
    );
    tooltip.hidden = false;
    tooltip.classList.add("is-visible");
    placeTooltip(target);
  }

  function hideTooltip(target) {
    if (target && currentTarget && target !== currentTarget) return;
    if (!tooltip) return;

    tooltip.classList.remove("is-visible");
    tooltip.classList.remove("cv-global-tooltip--accent");
    tooltip.hidden = true;
    currentTarget = null;
  }

  document.addEventListener("pointerover", function (event) {
    var target = getTarget(event.target);
    if (!target || target === currentTarget) return;
    showTooltip(target);
  });

  document.addEventListener("pointerout", function (event) {
    var target = getTarget(event.target);
    if (!target) return;
    var related = event.relatedTarget;
    if (related && target.contains(related)) return;
    hideTooltip(target);
  });

  document.addEventListener("focusin", function (event) {
    var target = getTarget(event.target);
    if (target) showTooltip(target);
  });

  document.addEventListener("focusout", function (event) {
    var target = getTarget(event.target);
    if (target) hideTooltip(target);
  });

  document.addEventListener("click", function (event) {
    var target = getTarget(event.target);
    if (target) hideTooltip(target);
  });

  window.addEventListener("scroll", function () {
    if (currentTarget) placeTooltip(currentTarget);
  }, true);

  window.addEventListener("resize", function () {
    if (currentTarget) placeTooltip(currentTarget);
  });
})();
