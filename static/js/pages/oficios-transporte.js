(function () {
  function normalizePlate(value) {
    return String(value || "")
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, "");
  }

  function debounce(fn, ms) {
    let handle = null;
    function debounced() {
      const args = arguments;
      window.clearTimeout(handle);
      handle = window.setTimeout(function () {
        handle = null;
        fn.apply(null, args);
      }, ms);
    }
    debounced.cancel = function () {
      window.clearTimeout(handle);
      handle = null;
    };
    return debounced;
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
    this.viaturaBuscaWrap = root.querySelector(".oficio-viatura-busca__wrap");
    this.viaturaFloatingMenu =
      window.CvFloatingDropdown &&
      window.CvFloatingDropdown.attach &&
      this.dropdown &&
      this.buscaInput
        ? window.CvFloatingDropdown.attach(this.dropdown, this.buscaInput)
        : null;
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
    this.bindMotoristaToggle();
    this.bindMotoristaSelectWatch();
    this.applyInitialMotoristaModo();
    this.updateMotoristaExtrasVisibility();
    this.syncViaturaLockFromDom();
    document.addEventListener("click", this.handleDocClick.bind(this));
  }

  OficioTransporte.prototype.handleDocClick = function (event) {
    const wrap = this.root.querySelector(".oficio-viatura-busca__wrap");
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

    this.runViaturaSearchDebounced = debounce(function () {
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

  OficioTransporte.prototype.runViaturaSearch = function () {
    const self = this;
    const term = (this.buscaInput.value || "").trim();
    if (!this.dropdown || !this.resultsEl) return;

    if (term.length < 2 && !this.equipeServidorIds.length) {
      this.closeViaturaDropdown();
      return;
    }

    const url = `${this.apiUrl}?q=${encodeURIComponent(term)}`;
    window
      .fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
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
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "oficio-viatura-busca__result";
    btn.setAttribute("role", "option");
    const main = document.createElement("span");
    main.className = "oficio-viatura-busca__result-main";
    main.textContent = [item.placa_formatada, item.modelo].filter(Boolean).join(" • ") || "Viatura";
    const sub = document.createElement("span");
    sub.className = "oficio-viatura-busca__result-meta";
    sub.textContent =
      "Unidade: " +
      (item.unidade_resumo || "—") +
      " • Motorista: " +
      (item.motoristas_resumo || "—");
    btn.appendChild(main);
    btn.appendChild(sub);
    btn.addEventListener("mousedown", function (event) {
      event.preventDefault();
    });
    btn.addEventListener("click", function () {
      self.applyViaturaFromResult(item);
    });
    return btn;
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
    this.setViaturaLocked(true);
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
      this.extrasPanel.classList.toggle("form-field--hidden", !showExtras);
      this.extrasPanel.setAttribute("aria-hidden", showExtras ? "false" : "true");
    }
    const showIn = !manual && Boolean(motoristaId) && equipeIds.indexOf(motoristaId) !== -1;
    const showOut = !manual && Boolean(motoristaId) && equipeIds.indexOf(motoristaId) === -1;
    const showMan = manual;
    [this.helperIn, this.helperOut, this.helperManual].forEach(function (el) {
      if (!el) return;
      el.classList.add("form-field--hidden");
    });
    if (showIn && this.helperIn) this.helperIn.classList.remove("form-field--hidden");
    if (showOut && this.helperOut) this.helperOut.classList.remove("form-field--hidden");
    if (showMan && this.helperManual) this.helperManual.classList.remove("form-field--hidden");
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
      this.servidorPanel.classList.toggle("form-field--hidden", manual);
      this.servidorPanel.setAttribute("aria-hidden", manual ? "true" : "false");
    }
    if (this.manualPanel) {
      this.manualPanel.classList.toggle("form-field--hidden", !manual);
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
      this.foundBanner.classList.toggle("form-field--hidden", !locked);
    }
  };

  OficioTransporte.prototype.syncViaturaLockFromDom = function () {
    const id = this.viaturaInput && this.viaturaInput.value;
    if (id) {
      this.selectedViaturaId = String(id);
      this.setViaturaLocked(true);
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
