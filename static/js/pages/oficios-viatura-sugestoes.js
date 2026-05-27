(function () {
  "use strict";

  function init() {
    var viaturaSelect   = document.querySelector("select[name='viatura'][data-cv-search-picker]");
    if (!viaturaSelect) return;

    var equipeSelect    = document.querySelector("select[name='servidores']");
    var motoristaSelect = document.querySelector("select[name='motorista']");
    var step1           = document.querySelector("[data-oficio-wizard-step1]");

    var container = document.querySelector("[data-viatura-sugestoes]");
    var chipsEl   = container && container.querySelector("[data-viatura-sugestoes-chips]");
    if (!container || !chipsEl) return;

    /* ── Mapas de nome e unidade ─────────────────────────────────── */
    var servidorNomeMap  = {};   // id → primeiro nome
    var unidadeNomeMap   = {};   // unidadeId → nome da unidade

    function buildMaps() {
      var sources = [];
      if (equipeSelect)    sources.push(equipeSelect);
      if (motoristaSelect) sources.push(motoristaSelect);
      sources.forEach(function (sel) {
        Array.from(sel.options).forEach(function (o) {
          if (!o.value || o.value.indexOf("__") === 0) return;
          var fullName  = (o.textContent || "").trim();
          var firstName = fullName.split(" ")[0] || fullName;
          servidorNomeMap[o.value] = firstName;
          if (o.dataset.unidadeId && o.dataset.unidade) {
            unidadeNomeMap[o.dataset.unidadeId] = o.dataset.unidade;
          }
        });
      });
    }
    buildMaps();

    /* ── Dados das viaturas ──────────────────────────────────────── */
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

    /* Mapa de unidade dos servidores (equipe), construído uma vez */
    var servidorUnidadeMap = {};
    if (equipeSelect) {
      Array.from(equipeSelect.options).forEach(function (o) {
        if (o.value && o.value.indexOf("__") !== 0) {
          servidorUnidadeMap[o.value] = o.dataset.unidadeId || "";
        }
      });
    }

    /* ── Seleciona viatura no picker ─────────────────────────────── */
    function selectViatura(id) {
      Array.from(viaturaSelect.options).forEach(function (o) { o.selected = o.value === id; });
      viaturaSelect.dispatchEvent(new Event("input",  { bubbles: true }));
      viaturaSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /* ── Renderiza chips ─────────────────────────────────────────── */
    function renderChips(sugestoes) {
      chipsEl.innerHTML = "";
      sugestoes.forEach(function (s) {
        var btn = document.createElement("button");
        btn.type      = "button";
        btn.className = "viatura-sugestao-chip";

        /* Placa em negrito + modelo */
        var parts  = s.label.split(" · ");
        var strong = document.createElement("strong");
        strong.textContent = parts[0] || s.label;
        btn.appendChild(strong);
        if (parts[1]) {
          btn.appendChild(document.createTextNode(" · " + parts[1]));
        }

        /* Badge com nome real da unidade ou primeiro nome do motorista */
        var badge = document.createElement("span");
        badge.className   = "viatura-sugestao-badge viatura-sugestao-badge--" + s.reason;
        badge.textContent = s.badgeText;
        btn.appendChild(badge);

        btn.addEventListener("click", function () { selectViatura(s.id); });
        chipsEl.appendChild(btn);
      });
    }

    /* ── Computa sugestões ───────────────────────────────────────── */
    function computeSugestoes() {
      var currentMotoristaId = (motoristaSelect && motoristaSelect.value) || "";

      var equipeIds = new Set(
        equipeSelect
          ? Array.from(equipeSelect.selectedOptions)
              .map(function (o) { return o.value; })
              .filter(function (v) { return v && v.indexOf("__") !== 0; })
          : []
      );

      /* Unidades da equipe + motorista */
      var selectedUnidades = new Set();
      equipeIds.forEach(function (id) {
        var uid = servidorUnidadeMap[id];
        if (uid) selectedUnidades.add(uid);
      });
      if (currentMotoristaId && motoristaSelect) {
        var motOpt    = motoristaSelect.querySelector("option[value='" + currentMotoristaId + "']");
        var motUnidade = (motOpt && motOpt.dataset.unidadeId) || "";
        if (motUnidade) selectedUnidades.add(motUnidade);
      }

      var sugestoes = [];
      var seen = new Set();

      viaturas.forEach(function (v) {
        if (seen.has(v.id)) return;

        /* Motorista direto (campo motorista) */
        var porMotoristaDirecto = currentMotoristaId && v.motoristaIds.has(currentMotoristaId);

        /* Membro da equipe é motorista desta viatura */
        var matchingEquipeMembro = null;
        equipeIds.forEach(function (eid) {
          if (!matchingEquipeMembro && v.motoristaIds.has(eid)) matchingEquipeMembro = eid;
        });

        /* Mesma unidade */
        var porUnidade = v.unidadeId && selectedUnidades.has(v.unidadeId);

        if (porMotoristaDirecto || matchingEquipeMembro || porUnidade) {
          seen.add(v.id);

          var reason, badgeText;
          if (porMotoristaDirecto || matchingEquipeMembro) {
            reason    = "motorista";
            var motId = porMotoristaDirecto ? currentMotoristaId : matchingEquipeMembro;
            badgeText = servidorNomeMap[motId] || "Motorista";
          } else {
            reason    = "unidade";
            badgeText = unidadeNomeMap[v.unidadeId] || "Unidade";
          }

          sugestoes.push({ id: v.id, label: v.label, reason: reason, badgeText: badgeText });
        }
      });

      /* Motorista direto primeiro */
      sugestoes.sort(function (a, b) {
        return (b.reason === "motorista" ? 1 : 0) - (a.reason === "motorista" ? 1 : 0);
      });

      return sugestoes;
    }

    /* ── Atualiza UI ─────────────────────────────────────────────── */
    function update() {
      var sugestoes = computeSugestoes();
      if (sugestoes.length === 0) {
        container.hidden = true;
        return;
      }
      container.hidden = false;
      renderChips(sugestoes.slice(0, 6));
    }

    /* ── Auto-fill ao marcar motorista (driver toggle) ───────────── */
    function tryAutoFillFromDriver(driverId) {
      if (!driverId) return;
      var matches = viaturas.filter(function (v) { return v.motoristaIds.has(driverId); });
      if (matches.length === 1) {
        selectViatura(matches[0].id);
      }
    }

    /* ── Auto-fill ao selecionar campo motorista ─────────────────── */
    function tryAutoFillFromMotoristaSelect() {
      var id = (motoristaSelect && motoristaSelect.value) || "";
      if (id) tryAutoFillFromDriver(id);
    }

    /* ── Listeners ───────────────────────────────────────────────── */
    if (equipeSelect) {
      equipeSelect.addEventListener("change", update);
    }
    if (motoristaSelect) {
      motoristaSelect.addEventListener("change", function () {
        update();
        tryAutoFillFromMotoristaSelect();
      });
    }

    /* Driver toggle no equipe picker — setDriverValue não dispara evento;
       usamos delegação de clique + setTimeout para ler aria-pressed depois */
    if (step1) {
      step1.addEventListener("click", function (e) {
        var toggle = e.target.closest(".cv-search-picker__driver-toggle");
        if (!toggle) return;
        var driverId = toggle.dataset.value || "";
        setTimeout(function () {
          update();
          /* Só auto-fill se o toggle acabou de ser ATIVADO */
          if (toggle.getAttribute("aria-pressed") === "true") {
            tryAutoFillFromDriver(driverId);
          }
        }, 0);
      });
    }

    /* Verificação inicial (modo edição com valores pré-selecionados) */
    update();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
