(function () {
  "use strict";

  function init() {
    var viaturaSelect = document.querySelector("select[name='viatura'][data-cv-search-picker]");
    if (!viaturaSelect) return;

    var equipeSelect    = document.querySelector("select[name='servidores']");
    var motoristaSelect = document.querySelector("select[name='motorista']");

    var container = document.querySelector("[data-viatura-sugestoes]");
    var chipsEl   = container && container.querySelector("[data-viatura-sugestoes-chips]");
    if (!container || !chipsEl) return;

    /* ── Lê dados das opções de viatura ─────────────────── */
    var viaturas = Array.from(viaturaSelect.options)
      .filter(function (o) { return o.value; })
      .map(function (o) {
        return {
          id:           o.value,
          label:        (o.textContent || "").trim(),
          motoristaIds: new Set((o.dataset.motoristaIds || "").split(",").filter(Boolean)),
          unidadeId:    o.dataset.unidadeId || "",
        };
      });

    /* ── Mapa servidorId → unidadeId (lido uma vez) ──────── */
    function buildServidorUnidadeMap(select) {
      var map = {};
      if (!select) return map;
      Array.from(select.options).forEach(function (o) {
        if (o.value && o.value.indexOf("__") !== 0) {
          map[o.value] = o.dataset.unidadeId || "";
        }
      });
      return map;
    }
    var servidorUnidadeMap = buildServidorUnidadeMap(equipeSelect);

    /* ── Seleciona uma viatura no picker nativo ───────────── */
    function selectViatura(id) {
      Array.from(viaturaSelect.options).forEach(function (o) {
        o.selected = o.value === id;
      });
      viaturaSelect.dispatchEvent(new Event("input",  { bubbles: true }));
      viaturaSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /* ── Renderiza chips ─────────────────────────────────── */
    function renderChips(sugestoes) {
      chipsEl.innerHTML = "";
      sugestoes.forEach(function (s) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "viatura-sugestao-chip";

        /* Placa em negrito + modelo */
        var parts = s.label.split(" · ");
        var strong = document.createElement("strong");
        strong.textContent = parts[0] || s.label;
        btn.appendChild(strong);
        if (parts[1]) {
          btn.appendChild(document.createTextNode(" · " + parts[1]));
        }

        /* Badge de motivo */
        var badge = document.createElement("span");
        badge.className = "viatura-sugestao-badge viatura-sugestao-badge--" + s.reason;
        badge.textContent = s.reason === "motorista" ? "Motorista" : "Unidade";
        btn.appendChild(badge);

        btn.addEventListener("click", function () { selectViatura(s.id); });
        chipsEl.appendChild(btn);
      });
    }

    /* ── Computa sugestões e atualiza UI ─────────────────── */
    function update(fromMotorista) {
      var currentMotoristaId = (motoristaSelect && motoristaSelect.value) || "";

      var equipeIds = new Set(
        equipeSelect
          ? Array.from(equipeSelect.selectedOptions)
              .map(function (o) { return o.value; })
              .filter(function (v) { return v && v.indexOf("__") !== 0; })
          : []
      );

      /* Unidades representadas na equipe + motorista */
      var selectedUnidades = new Set();
      equipeIds.forEach(function (id) {
        var uid = servidorUnidadeMap[id];
        if (uid) selectedUnidades.add(uid);
      });
      if (currentMotoristaId && motoristaSelect) {
        var motOpt = motoristaSelect.querySelector("option[value='" + currentMotoristaId + "']");
        var motUnidade = (motOpt && motOpt.dataset.unidadeId) || "";
        if (motUnidade) selectedUnidades.add(motUnidade);
      }

      /* Sugere viaturas por motorista direto, equipe ou unidade */
      var sugestoes = [];
      var seen = new Set();
      viaturas.forEach(function (v) {
        if (seen.has(v.id)) return;
        var porMotorista = currentMotoristaId && v.motoristaIds.has(currentMotoristaId);
        var porEquipe    = equipeIds.size > 0 && Array.from(equipeIds).some(function (eid) {
          return v.motoristaIds.has(eid);
        });
        var porUnidade   = v.unidadeId && selectedUnidades.has(v.unidadeId);

        if (porMotorista || porEquipe || porUnidade) {
          seen.add(v.id);
          sugestoes.push({
            id:     v.id,
            label:  v.label,
            reason: (porMotorista || porEquipe) ? "motorista" : "unidade",
          });
        }
      });

      /* Motorista direto primeiro */
      sugestoes.sort(function (a, b) {
        return (b.reason === "motorista" ? 1 : 0) - (a.reason === "motorista" ? 1 : 0);
      });

      if (sugestoes.length === 0) {
        container.hidden = true;
        return;
      }
      container.hidden = false;
      renderChips(sugestoes.slice(0, 6));

      /* Auto-fill: só quando motorista muda, exatamente uma vtr vinculada, campo vazio */
      if (fromMotorista && currentMotoristaId && !viaturaSelect.value) {
        var motoristaDiretos = sugestoes.filter(function (s) { return s.reason === "motorista"; });
        if (motoristaDiretos.length === 1) {
          selectViatura(motoristaDiretos[0].id);
        }
      }
    }

    if (equipeSelect) {
      equipeSelect.addEventListener("change", function () { update(false); });
    }
    if (motoristaSelect) {
      motoristaSelect.addEventListener("change", function () { update(true); });
    }

    /* Verificação inicial (modo edição com valores pré-selecionados) */
    update(false);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
