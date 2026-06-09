(function () {
  "use strict";

  function readSummaries() {
    var script = document.getElementById("termos-oficios-summary");
    if (!script) return {};
    try {
      return JSON.parse(script.textContent || "{}");
    } catch (err) {
      return {};
    }
  }

  function syncOficioSummary(form, summaries) {
    var select = form.querySelector("select[name='oficio']");
    var root = form.querySelector("[data-termo-oficio-summary]");
    if (!select || !root) return;

    var empty = root.querySelector(".termo-oficio-summary__empty");
    var grid = root.querySelector(".termo-oficio-summary__grid");
    var destino = root.querySelector("[data-termo-oficio-destino]");
    var periodo = root.querySelector("[data-termo-oficio-periodo]");
    var servidores = root.querySelector("[data-termo-oficio-servidores]");
    var viatura = root.querySelector("[data-termo-oficio-viatura]");

    function render() {
      var summary = summaries[select.value || ""];
      var hasSummary = !!summary;
      if (empty) empty.hidden = hasSummary;
      if (grid) grid.hidden = !hasSummary;
      if (!hasSummary) return;
      if (destino) destino.textContent = summary.destino || "-";
      if (periodo) periodo.textContent = summary.periodo || "-";
      if (servidores) servidores.textContent = String(summary.servidores || 0);
      if (viatura) viatura.textContent = summary.viatura || "-";
    }

    select.addEventListener("change", render);
    render();
  }

  function syncAnchors() {
    var anchors = Array.from(document.querySelectorAll("[data-termo-anchor]"));
    if (!anchors.length) return;
    var targets = anchors
      .map(function (anchor) {
        var id = (anchor.getAttribute("href") || "").replace("#", "");
        return { anchor: anchor, target: document.getElementById(id) };
      })
      .filter(function (item) {
        return !!item.target;
      });

    function update() {
      var current = targets[0];
      targets.forEach(function (item) {
        if (item.target.getBoundingClientRect().top <= 160) {
          current = item;
        }
      });
      targets.forEach(function (item) {
        item.anchor.classList.toggle("is-active", item === current);
      });
    }

    window.addEventListener("scroll", update, { passive: true });
    update();
  }

  function syncSingleDayRange(form) {
    var start = form.querySelector("input[name='data_evento_inicio']");
    var end = form.querySelector("input[name='data_evento_fim']");
    if (!start || !end) return;
    form.addEventListener("submit", function () {
      if (start.value && !end.value) {
        end.value = start.value;
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector("[data-termo-form]");
    if (!form) return;
    syncOficioSummary(form, readSummaries());
    syncSingleDayRange(form);
    syncAnchors();
  });
})();
