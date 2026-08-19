(function () {
  function normalizePlate(value) {
    return String(value || "")
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "");
  }

  function dispatchFieldEvents(element) {
    if (!element) return;
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function OficioTransporte(root) {
    this.root = root;
    this.apiUrl = root.dataset.apiViaturaUrl || "";
    this.buscaInput = root.querySelector("[data-oficio-viatura-busca]");
    this.placaHidden = root.querySelector("[data-oficio-placa-hidden]");
    this.viaturaInput = root.querySelector("[data-oficio-viatura-id]");
    this.modeloInput = root.querySelector("[data-oficio-viatura-modelo]");
    this.combustivelSelect = root.querySelector("[data-oficio-viatura-combustivel]");
    this.tipoSelect = root.querySelector("[data-oficio-viatura-tipo]");
    this.foundBanner = root.querySelector("[data-oficio-viatura-found]");
    this.dropdown = root.querySelector("[data-oficio-viatura-dropdown]");
    this.resultsEl = root.querySelector("[data-oficio-viatura-results]");
    this.emptyEl = root.querySelector("[data-oficio-viatura-empty]");
    this.selectedViaturaId = (this.viaturaInput && this.viaturaInput.value) || "";
    this.equipeServidorIds = (root.dataset.equipeServidorIds || "")
      .split(",")
      .map(function (id) {
        return id.trim();
      })
      .filter(Boolean);
    this.pickerRoot = root.querySelector("[data-oficio-vehicle-picker]");
    this.controlEl = root.querySelector("[data-entity-picker-part='control']");
    this.clearBtn = root.querySelector("[data-oficio-viatura-clear]");
    this.viaturaFloatingMenu =
      window.CV &&
      window.CV.overlay &&
      window.CV.overlay.attachDropdown &&
      this.dropdown &&
      this.controlEl
        ? window.CV.overlay.attachDropdown(this.dropdown, this.controlEl)
        : null;
    // Painel "VIATURA SELECIONADA" — card visualmente igual ao multiselect detalhado
    this.selectedList = root.querySelector("[data-oficio-viatura-selected-list]");
    this.selectedEmpty = root.querySelector("[data-oficio-viatura-selected-empty]");
    this.manualPanelVeic = root.querySelector("[data-oficio-viatura-manual-panel]");
    this.modHidden = root.querySelector("[data-oficio-motorista-modo]");
    this.servidorPanel = root.querySelector("[data-oficio-motorista-servidor]");
    this.manualPanel = root.querySelector("[data-oficio-motorista-manual]");
    this.extrasPanel = root.querySelector("[data-oficio-motorista-extras]");
    this.helperIn = root.querySelector("[data-oficio-motorista-helper-in]");
    this.helperOut = root.querySelector("[data-oficio-motorista-helper-out]");
    this.helperManual = root.querySelector("[data-oficio-motorista-helper-manual]");
    this.toggleBtn = root.querySelector("[data-oficio-motorista-toggle]");
    this.motoristaSelect = root.querySelector("select[name='motorista']");
    this.bindViaturaBusca();
    this.bindViaturaClear();
    this.bindMotoristaToggle();
    this.bindMotoristaSelectWatch();
    this.applyInitialMotoristaModo();
    this.updateMotoristaExtrasVisibility();
    this.syncViaturaLockFromDom();
    document.addEventListener("click", this.handleDocClick.bind(this));
  }

  OficioTransporte.prototype.handleDocClick = function (event) {
    // Considera tanto o picker novo (search-picker) quanto o wrap legado.
    const wrap = this.pickerRoot || this.root.querySelector(".oficio-viatura-busca__wrap");
    if (!wrap || !this.dropdown) return;
    if (!wrap.contains(event.target)) {
      if (this.runViaturaSearchDebounced && this.runViaturaSearchDebounced.cancel) {
        this.runViaturaSearchDebounced.cancel();
      }
      this.closeViaturaDropdown();
    }
  };

  OficioTransporte.prototype.closeViaturaDropdown = function () {
    if (this.viaturaFloatingMenu) {
      this.viaturaFloatingMenu.close();
    }
    if (this.dropdown) {
      this.dropdown.hidden = true;
      this.dropdown.setAttribute("hidden", "hidden");
    }
    if (this.resultsEl) {
      this.resultsEl.innerHTML = "";
    }
    if (this.emptyEl) {
      this.emptyEl.hidden = true;
      this.emptyEl.setAttribute("hidden", "hidden");
    }
    if (this.buscaInput) {
      this.buscaInput.setAttribute("aria-expanded", "false");
    }
  };

  OficioTransporte.prototype.bindViaturaBusca = function () {
    const self = this;
    if (!this.buscaInput || !this.apiUrl) return;

    this.runViaturaSearchDebounced = window.CV.util.debounce(function () {
      self.runViaturaSearch();
    }, 380);

    this.buscaInput.addEventListener("input", function () {
      if (self._suppressViaturaBuscaInput) {
        self._suppressViaturaBuscaInput = false;
        return;
      }
      const term = (self.buscaInput.value || "").trim();
      const selLabel = self.buscaInput.dataset.selectedLabel || "";
      if (self.selectedViaturaId && selLabel && term !== selLabel) {
        if (self.viaturaInput) {
          self.viaturaInput.value = "";
          dispatchFieldEvents(self.viaturaInput);
        }
        if (self.placaHidden) {
          self.placaHidden.value = "";
          dispatchFieldEvents(self.placaHidden);
        }
        self.selectedViaturaId = "";
        self.setViaturaLocked(false);
        delete self.buscaInput.dataset.selectedLabel;
      }
      self.runViaturaSearchDebounced();
    });

    this.buscaInput.addEventListener("change", function () {
      self.syncPlacaHiddenFromBusca();
    });

    this.buscaInput.addEventListener("focus", function () {
      const term = (self.buscaInput.value || "").trim();
      if (!term && self.equipeServidorIds.length) {
        self.runViaturaSearch();
      }
    });
  };

  OficioTransporte.prototype.syncPlacaHiddenFromBusca = function () {
    const norm = normalizePlate(this.buscaInput.value);
    if (norm.length === 7 && !(this.viaturaInput && this.viaturaInput.value)) {
      if (this.placaHidden) {
        this.placaHidden.value = norm;
        dispatchFieldEvents(this.placaHidden);
      }
    }
  };

  OficioTransporte.prototype.getMotoristaIdFromTeam = function () {
    const sel = this.motoristaSelect;
    if (!sel || !sel.value) return "";
    const id = parseInt(sel.value, 10);
    if (!id) return "";
    const ids = (this.root.dataset.equipeServidorIds || "")
      .split(",")
      .map(function (x) { return parseInt(x, 10) || 0; })
      .filter(Boolean);
    return ids.indexOf(id) !== -1 ? String(id) : "";
  };

  OficioTransporte.prototype.runViaturaSearch = function () {
    const self = this;
    const term = (this.buscaInput.value || "").trim();
    if (!this.dropdown || !this.resultsEl) return;

    const motoristaId = this.getMotoristaIdFromTeam();

    if (term.length < 2 && !this.equipeServidorIds.length && !motoristaId) {
      this.closeViaturaDropdown();
      return;
    }

    const params = ["q=" + encodeURIComponent(term)];
    if (motoristaId) params.push("motorista_id=" + encodeURIComponent(motoristaId));
    const url = this.apiUrl + "?" + params.join("&");
    window.CV.http
      .fetchJson(url, { headers: { Accept: "application/json" } })
      .then(function (result) {
        var data = result.data || {};
        if (!result.ok) throw new Error(data.error || "Falha ao buscar viaturas.");
        const results = (data && data.results) || [];
        self.resultsEl.innerHTML = "";
        if (!results.length) {
          self.dropdown.hidden = false;
          self.dropdown.removeAttribute("hidden");
          if (self.emptyEl) {
            self.emptyEl.hidden = false;
            self.emptyEl.removeAttribute("hidden");
          }
          if (self.viaturaFloatingMenu) {
            self.viaturaFloatingMenu.open();
          }
          if (self.buscaInput) {
            self.buscaInput.setAttribute("aria-expanded", "true");
          }
          return;
        }
        if (self.emptyEl) {
          self.emptyEl.hidden = true;
          self.emptyEl.setAttribute("hidden", "hidden");
        }
        results.forEach(function (item) {
          self.resultsEl.appendChild(self.buildResultButton(item));
        });
        self.dropdown.hidden = false;
        self.dropdown.removeAttribute("hidden");
        if (self.viaturaFloatingMenu) {
          self.viaturaFloatingMenu.open();
        }
        if (self.buscaInput) {
          self.buscaInput.setAttribute("aria-expanded", "true");
        }
      })
      .catch(function () {
        self.closeViaturaDropdown();
      });
  };

  OficioTransporte.prototype.buildResultButton = function (item) {
    const self = this;
    const placaLabel = item.placa_formatada || "Viatura";
    const modeloLabel = item.modelo || "";
    const metaParts = [
      item.unidade_resumo,
      item.combustivel,
      item.tipo,
    ].filter(function (p) { return p && p !== "—"; });
    const hasReason = item.suggestion_reason === "motorista"
      || item.suggestion_reason === "unidade";
    const button = window.CV.pickerParts.createOption({
      chip: hasReason ? {
        className: "search-picker__driver-chip oficio-viatura-reason oficio-viatura-reason--" + item.suggestion_reason,
        label: item.suggestion_reason === "motorista" ? "Motorista" : "Unidade",
      } : null,
      meta: metaParts.length ? metaParts.join("  •  ") : "Dados complementares não informados",
      selected: false,
      suggestionReason: item.suggestion_reason,
      title: modeloLabel ? placaLabel + "  •  " + modeloLabel : placaLabel,
      value: item.id,
    });
    button.addEventListener("click", function () { self.applyViaturaFromResult(item); });
    return button;
  };

  OficioTransporte.prototype.applyViaturaFromResult = function (item) {
    if (this.runViaturaSearchDebounced && this.runViaturaSearchDebounced.cancel) {
      this.runViaturaSearchDebounced.cancel();
    }
    this.closeViaturaDropdown();
    this._suppressViaturaBuscaInput = true;
    if (this.viaturaInput) {
      this.viaturaInput.value = String(item.id);
      dispatchFieldEvents(this.viaturaInput);
    }
    if (this.placaHidden) {
      const plateNorm = item.placa ? String(item.placa) : normalizePlate(item.placa_formatada || "");
      this.placaHidden.value = plateNorm.length === 7 ? plateNorm : "";
      dispatchFieldEvents(this.placaHidden);
    }
    if (this.buscaInput) {
      this.buscaInput.value = item.placa_formatada || "";
      this.buscaInput.dataset.selectedLabel = item.placa_formatada || "";
      dispatchFieldEvents(this.buscaInput);
    }
    if (this.modeloInput) {
      this.modeloInput.value = item.modelo || "";
      dispatchFieldEvents(this.modeloInput);
    }
    if (this.combustivelSelect && item.combustivel_id) {
      this.combustivelSelect.value = String(item.combustivel_id);
      dispatchFieldEvents(this.combustivelSelect);
    }
    if (this.tipoSelect && item.tipo) {
      this.tipoSelect.value = item.tipo;
      dispatchFieldEvents(this.tipoSelect);
    }
    this.selectedViaturaId = String(item.id);
    this.renderSelectedCard(item);
    this.setViaturaLocked(true);
  };

  OficioTransporte.prototype.renderSelectedCard = function (item) {
    if (!this.selectedList) return;
    this.selectedList.innerHTML = "";
    const placaLabel = item.placa_formatada || "—";
    const modeloLabel = item.modelo || "";
    const metaParts = [
      item.unidade_resumo,
      item.combustivel,
      item.tipo,
    ].filter(function (p) { return p && p !== "—"; });
    const self = this;
    const hasReason = item.suggestion_reason === "motorista"
      || item.suggestion_reason === "unidade";
    const card = window.CV.pickerParts.createSelectedCard({
      chip: hasReason ? {
        className: "search-picker__driver-chip oficio-viatura-reason oficio-viatura-reason--" + item.suggestion_reason,
        label: item.suggestion_reason === "motorista" ? "Motorista" : "Unidade",
      } : null,
      editAriaLabel: "Editar viatura selecionada",
      editLabel: "Editar viatura",
      editUrl: item.edit_url,
      extraClass: "oficio-viatura-selected-card",
      meta: metaParts.length ? metaParts.join("  •  ") : "Dados complementares não informados",
      onRemove: function () { self.clearViaturaSelection(); },
      removeAriaLabel: "Remover viatura selecionada",
      title: modeloLabel ? placaLabel + "  •  " + modeloLabel : placaLabel,
      value: item.id,
    });
    this.selectedList.appendChild(card);
    if (this.selectedEmpty) {
      this.selectedEmpty.hidden = true;
      this.selectedEmpty.setAttribute("hidden", "hidden");
    }
  };

  OficioTransporte.prototype.clearSelectedCard = function () {
    if (this.selectedList) this.selectedList.innerHTML = "";
    if (this.selectedEmpty) {
      this.selectedEmpty.hidden = false;
      this.selectedEmpty.removeAttribute("hidden");
    }
  };

  OficioTransporte.prototype.clearViaturaSelection = function () {
    // Limpa todos os campos vinculados à viatura cadastrada e
    // libera o painel manual.
    if (this.viaturaInput) {
      this.viaturaInput.value = "";
      dispatchFieldEvents(this.viaturaInput);
    }
    if (this.placaHidden) {
      this.placaHidden.value = "";
      dispatchFieldEvents(this.placaHidden);
    }
    if (this.buscaInput) {
      this.buscaInput.value = "";
      delete this.buscaInput.dataset.selectedLabel;
      dispatchFieldEvents(this.buscaInput);
    }
    this.selectedViaturaId = "";
    this.setViaturaLocked(false);
  };

  OficioTransporte.prototype.bindViaturaClear = function () {
    const self = this;
    if (!this.clearBtn) return;
    this.clearBtn.addEventListener("click", function (event) {
      event.preventDefault();
      self.clearViaturaSelection();
      if (self.buscaInput) self.buscaInput.focus();
    });
  };

  OficioTransporte.prototype.bindMotoristaToggle = function () {
    const self = this;
    if (!this.toggleBtn || !this.modHidden) return;
    this.toggleBtn.addEventListener("click", function () {
      const cur = (self.modHidden.value || "SERVIDOR").trim();
      const next = cur === "MANUAL" ? "SERVIDOR" : "MANUAL";
      self.modHidden.value = next;
      dispatchFieldEvents(self.modHidden);
      self.toggleMotoristaModo(next, false);
      self.updateToggleButtonLabel();
      self.updateMotoristaExtrasVisibility();
    });
  };

  OficioTransporte.prototype.bindMotoristaSelectWatch = function () {
    const self = this;
    if (!this.motoristaSelect) return;
    this.motoristaSelect.addEventListener("change", function () {
      self.updateMotoristaExtrasVisibility();
    });
  };

  OficioTransporte.prototype.updateToggleButtonLabel = function () {
    if (!this.toggleBtn || !this.modHidden) return;
    const manual = (this.modHidden.value || "").trim() === "MANUAL";
    this.toggleBtn.textContent = manual ? "Usar motorista cadastrado" : "Usar motorista manual";
  };

  OficioTransporte.prototype.updateMotoristaExtrasVisibility = function () {
    const modo = (this.modHidden && this.modHidden.value) || "SERVIDOR";
    const manual = modo === "MANUAL";
    const rawIds = (this.root.dataset.equipeServidorIds || "").split(",").filter(Boolean);
    const equipeIds = rawIds.map(function (id) {
      return parseInt(id, 10);
    });
    let motoristaId = 0;
    const sel = this.root.querySelector("select[name='motorista']");
    if (sel && sel.value) {
      motoristaId = parseInt(sel.value, 10) || 0;
    }
    let showExtras = manual;
    if (!manual && motoristaId && equipeIds.indexOf(motoristaId) === -1) {
      showExtras = true;
    }
    if (this.extrasPanel) {
      /* `hidden`, e não a classe `form-field--hidden`: aquela utilidade mora nas
       * folhas de página do sistema antigo, que saíram do wizard na migração
       * para o v2 — o painel ficaria preso escondido, sem erro nenhum. O
       * invólucro é uma `<div>` nua justamente para o `hidden` do HTML bastar. */
      this.extrasPanel.hidden = !showExtras;
      this.extrasPanel.setAttribute("aria-hidden", showExtras ? "false" : "true");
    }
    const showIn = !manual && Boolean(motoristaId) && equipeIds.indexOf(motoristaId) !== -1;
    const showOut = !manual && Boolean(motoristaId) && equipeIds.indexOf(motoristaId) === -1;
    const showMan = manual;
    [this.helperIn, this.helperOut, this.helperManual].forEach(function (el) {
      if (!el) return;
      el.hidden = true;
    });
    if (showIn && this.helperIn) this.helperIn.hidden = false;
    if (showOut && this.helperOut) this.helperOut.hidden = false;
    if (showMan && this.helperManual) this.helperManual.hidden = false;
  };

  OficioTransporte.prototype.applyInitialMotoristaModo = function () {
    const initial = this.root.dataset.oficioMotoristaModInicial || "SERVIDOR";
    const current = (this.modHidden && this.modHidden.value) || initial;
    if (this.modHidden && !this.modHidden.value) {
      this.modHidden.value = current;
    }
    this.toggleMotoristaModo(current, true);
    this.updateToggleButtonLabel();
  };

  OficioTransporte.prototype.toggleMotoristaModo = function (modo, isInitial) {
    const manual = modo === "MANUAL";
    const motoristaSelect = this.root.querySelector("select[name='motorista']");
    if (!isInitial) {
      if (manual) {
        if (motoristaSelect) {
          motoristaSelect.value = "";
          dispatchFieldEvents(motoristaSelect);
        }
      } else if (this.manualPanel) {
        this.manualPanel.querySelectorAll("[data-oficio-motorista-manual]").forEach(function (field) {
          if (field.type === "hidden") return;
          field.value = "";
          dispatchFieldEvents(field);
        });
      }
    }
    if (this.servidorPanel) {
      this.servidorPanel.hidden = manual;
      this.servidorPanel.setAttribute("aria-hidden", manual ? "true" : "false");
    }
    if (this.manualPanel) {
      this.manualPanel.hidden = !manual;
      this.manualPanel.setAttribute("aria-hidden", !manual ? "true" : "false");
    }
    if (motoristaSelect) {
      motoristaSelect.disabled = manual;
    }
  };

  OficioTransporte.prototype.setViaturaLocked = function (locked) {
    [this.modeloInput, this.combustivelSelect, this.tipoSelect].forEach(function (el) {
      if (!el) return;
      el.readOnly = !!(locked && el.tagName === "INPUT");
      el.disabled = !!(locked && el.tagName === "SELECT");
      el.classList.toggle("is-viatura-cadastro", !!locked);
    });
    if (this.foundBanner) {
      this.foundBanner.hidden = !locked;
      this.foundBanner.hidden = !locked;
    }
    // Mostra/esconde painel de campos manuais com base no estado.
    if (this.manualPanelVeic) {
      this.manualPanelVeic.hidden = !!locked;
      this.manualPanelVeic.setAttribute("aria-hidden", locked ? "true" : "false");
    }
    if (!locked) {
      this.clearSelectedCard();
    }
    if (this.pickerRoot) {
      this.pickerRoot.classList.toggle("oficio-viatura-picker--has-selection", !!locked);
    }
  };

  OficioTransporte.prototype.syncViaturaLockFromDom = function () {
    const id = this.viaturaInput && this.viaturaInput.value;
    if (id) {
      this.selectedViaturaId = String(id);
      // Reidrata o card a partir do contexto SSR.
      const placa = (this.buscaInput && this.buscaInput.value) || "";
      const modeloSaved = this.root.dataset.viaturaModeloSaved || "";
      const tipoLabel =
        this.root.dataset.viaturaTipoLabel ||
        (function (sel) {
          if (!sel || !sel.value) return "";
          const opt = sel.options[sel.selectedIndex];
          return (opt && opt.text) || "";
        })(this.tipoSelect);
      const combLabel =
        this.root.dataset.viaturaCombustivelLabel ||
        (function (sel) {
          if (!sel || !sel.value) return "";
          const opt = sel.options[sel.selectedIndex];
          return (opt && opt.text) || "";
        })(this.combustivelSelect);
      this.renderSelectedCard({
        id: id,
        placa_formatada: placa,
        modelo: modeloSaved || ((this.modeloInput && this.modeloInput.value) || ""),
        unidade_resumo: this.root.dataset.viaturaUnidadeResumo || "—",
        combustivel: combLabel,
        tipo: tipoLabel,
        edit_url: this.root.dataset.viaturaEditUrl || "",
      });
      this.setViaturaLocked(true);
    } else {
      this.setViaturaLocked(false);
    }
  };

  function boot() {
    const root = document.getElementById("oficio-transporte-root");
    if (!root) return;
    new OficioTransporte(root);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
