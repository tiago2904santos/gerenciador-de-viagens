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
    var servidorNomeMap    = {};   // id → primeiro nome
    var unidadeNomeMap     = {};   // unidadeId → nome da unidade
    var servidorUnidadeMap = {};   // id → unidadeId (equipe)
    var motoristaUnidadeMap = {};  // id → unidadeId (motorista select)

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
      if (equipeSelect) {
        Array.from(equipeSelect.options).forEach(function (o) {
          if (o.value && o.value.indexOf("__") !== 0) {
            servidorUnidadeMap[o.value] = o.dataset.unidadeId || "";
          }
        });
      }
      if (motoristaSelect) {
        Array.from(motoristaSelect.options).forEach(function (o) {
          if (o.value && o.value.indexOf("__") !== 0) {
            motoristaUnidadeMap[o.value] = o.dataset.unidadeId || "";
          }
        });
      }
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

    /* ── Identifica o motorista ativo ────────────────────────────── */
    function getActiveDriverId() {
      /* Motorista no campo externo (card "Motorista") */
      var motId = (motoristaSelect && motoristaSelect.value) || "";
      if (motId) return motId;
      /* Driver toggle ativo na equipe picker */
      var activeToggle = step1 && step1.querySelector(
        ".cv-search-picker__driver-toggle[aria-pressed='true']"
      );
      return (activeToggle && activeToggle.dataset.value) || "";
    }

    function getDriverUnit(driverId) {
      return servidorUnidadeMap[driverId] || motoristaUnidadeMap[driverId] || "";
    }

    /* ── Seleciona / deseleciona viatura no picker ───────────────── */
    function selectViatura(id) {
      Array.from(viaturaSelect.options).forEach(function (o) { o.selected = o.value === id; });
      viaturaSelect.dispatchEvent(new Event("input",  { bubbles: true }));
      viaturaSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function deselectViatura() {
      Array.from(viaturaSelect.options).forEach(function (o) { o.selected = false; });
      viaturaSelect.dispatchEvent(new Event("input",  { bubbles: true }));
      viaturaSelect.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /* ── Atualiza classe --active nos chips já renderizados ─────── */
    function updateActiveChips() {
      var currentId = viaturaSelect.value || "";
      Array.from(chipsEl.querySelectorAll(".viatura-sugestao-chip")).forEach(function (btn) {
        btn.classList.toggle("viatura-sugestao-chip--active", btn.dataset.viaturaId === currentId);
      });
    }

    /* ── Renderiza chips ─────────────────────────────────────────── */
    function renderChips(sugestoes) {
      var currentId = viaturaSelect.value || "";
      chipsEl.innerHTML = "";
      sugestoes.forEach(function (s) {
        var btn = document.createElement("button");
        btn.type           = "button";
        btn.dataset.viaturaId = s.id;
        btn.className      = "viatura-sugestao-chip" +
          (s.id === currentId ? " viatura-sugestao-chip--active" : "");

        /* ── Conteúdo: placa (negrito) + descrição ── */
        var parts = s.label.split(" · ");

        var strong = document.createElement("strong");
        strong.textContent = parts[0] || s.label;
        btn.appendChild(strong);

        if (parts[1]) {
          btn.appendChild(document.createTextNode(" · " + parts[1]));
        }

        /* ── Badge de razão ── */
        var badge = document.createElement("span");
        badge.className   = "viatura-sugestao-badge viatura-sugestao-badge--" + s.reason;
        badge.textContent = s.badgeText;
        btn.appendChild(badge);

        btn.addEventListener("click", function () {
          if (viaturaSelect.value === s.id) {
            deselectViatura();
          } else {
            selectViatura(s.id);
          }
        });
        chipsEl.appendChild(btn);
      });
    }

    /* ── Computa sugestões ───────────────────────────────────────── */
    function computeSugestoes() {
      var activeDriverId = getActiveDriverId();

      var equipeIds = new Set(
        equipeSelect
          ? Array.from(equipeSelect.selectedOptions)
              .map(function (o) { return o.value; })
              .filter(function (v) { return v && v.indexOf("__") !== 0; })
          : []
      );

      /*
       * Escopo de unidades:
       * — Se há motorista ativo → apenas a unidade dele (ignora equipe)
       * — Caso contrário → unidades de todos da equipe
       */
      var selectedUnidades = new Set();
      if (activeDriverId) {
        var driverUnit = getDriverUnit(activeDriverId);
        if (driverUnit) selectedUnidades.add(driverUnit);
      } else {
        equipeIds.forEach(function (id) {
          var uid = servidorUnidadeMap[id];
          if (uid) selectedUnidades.add(uid);
        });
      }

      var sugestoes = [];
      var seen = new Set();

      viaturas.forEach(function (v) {
        if (seen.has(v.id)) return;

        /* Motorista direto (driver ativo) */
        var porMotoristaDirecto = activeDriverId && v.motoristaIds.has(activeDriverId);

        /* Sem motorista ativo: membro da equipe é motorista desta viatura */
        var matchingEquipeMembro = null;
        if (!activeDriverId) {
          equipeIds.forEach(function (eid) {
            if (!matchingEquipeMembro && v.motoristaIds.has(eid)) matchingEquipeMembro = eid;
          });
        }

        /* Mesma unidade (escopo filtrado pelo motorista ativo) */
        var porUnidade = v.unidadeId && selectedUnidades.has(v.unidadeId);

        if (porMotoristaDirecto || matchingEquipeMembro || porUnidade) {
          seen.add(v.id);

          var reason, badgeText;
          if (porMotoristaDirecto || matchingEquipeMembro) {
            reason    = "motorista";
            var motId = porMotoristaDirecto ? activeDriverId : matchingEquipeMembro;
            badgeText = servidorNomeMap[motId] || "Motorista";
          } else {
            reason    = "unidade";
            badgeText = unidadeNomeMap[v.unidadeId] || "Unidade";
          }

          sugestoes.push({ id: v.id, label: v.label, reason: reason, badgeText: badgeText });
        }
      });

      /* Motorista direto sempre primeiro */
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
      renderChips(sugestoes.slice(0, 8));
    }

    /* ── Auto-fill ao marcar driver ──────────────────────────────── */
    function tryAutoFillFromDriver(driverId) {
      if (!driverId) return;
      var matches = viaturas.filter(function (v) { return v.motoristaIds.has(driverId); });
      if (matches.length === 1) {
        selectViatura(matches[0].id);
      }
    }

    function tryAutoFillFromMotoristaSelect() {
      var id = (motoristaSelect && motoristaSelect.value) || "";
      if (id) tryAutoFillFromDriver(id);
    }

    /* ── Listeners ───────────────────────────────────────────────── */
    /* Quando a viatura muda via picker, re-renderiza chips (inclui estado ativo) */
    viaturaSelect.addEventListener("change", update);
    viaturaSelect.addEventListener("input",  update);

    if (equipeSelect) {
      equipeSelect.addEventListener("change", update);
    }
    if (motoristaSelect) {
      motoristaSelect.addEventListener("change", function () {
        update();
        tryAutoFillFromMotoristaSelect();
      });
    }

    if (step1) {
      step1.addEventListener("click", function (e) {
        var toggle = e.target.closest(".cv-search-picker__driver-toggle");
        if (!toggle) return;
        var driverId = toggle.dataset.value || "";
        setTimeout(function () {
          update();
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
