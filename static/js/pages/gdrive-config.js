(function () {
  "use strict";

  const FOLDER_ICON_SVG =
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" ' +
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>';

  const SHARED_DRIVE_ICON_SVG =
    '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" ' +
    'fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path>' +
    '<circle cx="12" cy="13" r="2.4" fill="none" stroke="currentColor" stroke-width="1.6"></circle></svg>';

  function initFolderBrowser(container) {
    const urlListar = container.dataset.urlListar;
    const urlCriar = container.dataset.urlCriar;
    const urlDrives = container.dataset.urlDrives;
    const urlCompartilhadosComigo = container.dataset.urlCompartilhadosComigo;
    const btnMeuDrive = container.querySelector("#gdrive-btn-meu-drive");
    const btnDrivesCompartilhados = container.querySelector("#gdrive-btn-drives-compartilhados");
    const btnCompartilhadosComigo = container.querySelector("#gdrive-btn-compartilhados-comigo");
    const btnVoltar = container.querySelector("#gdrive-btn-voltar");
    const browserBody = container.querySelector("#gdrive-browser-body");
    const folderList = container.querySelector("#gdrive-folder-list");
    const folderEmpty = container.querySelector("#gdrive-folder-empty");
    const loading = container.querySelector("#gdrive-loading");
    const browserActions = container.querySelector("#gdrive-browser-actions");
    const btnSelecionar = container.querySelector("#gdrive-btn-selecionar");
    const btnToggleCriar = container.querySelector("#gdrive-btn-toggle-criar");
    const newFolderPanel = container.querySelector("#gdrive-new-folder");
    const novaPastaNome = container.querySelector("#gdrive-nova-pasta-nome");
    const btnCriar = container.querySelector("#gdrive-btn-criar");
    const breadcrumbEl = container.querySelector("#gdrive-breadcrumb");
    const formSalvar = container.querySelector("#gdrive-form-salvar");
    const inputPastaId = container.querySelector("#gdrive-input-pasta-id");
    const inputPastaNome = container.querySelector("#gdrive-input-pasta-nome");

    // Navegação: pilha de { id, nome }
    const navStack = [];
    let selectedFolder = null; // { id, name }
    let rootMode = "meu_drive"; // "meu_drive" | "compartilhados" | "compartilhados_comigo"

    function currentPaiId() {
      return navStack.length > 0 ? navStack[navStack.length - 1].id : null;
    }

    function updateTabs() {
      if (btnMeuDrive) btnMeuDrive.classList.toggle("is-active", rootMode === "meu_drive");
      if (btnMeuDrive) btnMeuDrive.setAttribute("aria-selected", String(rootMode === "meu_drive"));
      if (btnDrivesCompartilhados) btnDrivesCompartilhados.classList.toggle("is-active", rootMode === "compartilhados");
      if (btnDrivesCompartilhados) btnDrivesCompartilhados.setAttribute("aria-selected", String(rootMode === "compartilhados"));
      if (btnCompartilhadosComigo) btnCompartilhadosComigo.classList.toggle("is-active", rootMode === "compartilhados_comigo");
      if (btnCompartilhadosComigo) btnCompartilhadosComigo.setAttribute("aria-selected", String(rootMode === "compartilhados_comigo"));
    }

    function baseLabel() {
      if (rootMode === "compartilhados") return "Drives compartilhados";
      if (rootMode === "compartilhados_comigo") return "Compartilhados comigo";
      return "Meu Drive";
    }

    function updateBreadcrumb() {
      if (!breadcrumbEl) return;
      const base = baseLabel();
      if (navStack.length === 0) {
        breadcrumbEl.textContent = base;
        return;
      }
      breadcrumbEl.textContent = base + " › " + navStack.map((n) => n.nome).join(" › ");
    }

    function setLoading(on) {
      loading.hidden = !on;
      folderList.hidden = on;
      folderEmpty.hidden = true;
    }

    function clearSelection() {
      selectedFolder = null;
      btnSelecionar.disabled = true;
      btnSelecionar.textContent = "Usar esta pasta como destino";
      folderList.querySelectorAll(".gdrive-folder-item").forEach((el) => {
        el.classList.remove("is-selected");
        el.setAttribute("aria-pressed", "false");
      });
    }

    function renderFolders(pastas, options) {
      const icon = (options && options.sharedDriveIcon) ? SHARED_DRIVE_ICON_SVG : FOLDER_ICON_SVG;
      folderList.innerHTML = "";
      clearSelection();

      if (pastas.length === 0) {
        folderEmpty.hidden = false;
        folderList.hidden = true;
        return;
      }

      folderEmpty.hidden = true;
      folderList.hidden = false;

      pastas.forEach((pasta) => {
        const item = document.createElement("div");
        item.className = "gdrive-folder-item";
        item.role = "listitem";
        item.dataset.id = pasta.id;
        item.dataset.nome = pasta.name;
        item.setAttribute("aria-pressed", "false");

        // JS-01/NOVO-15: o nome vem do Drive e pode conter marcação. APIs de DOM
        // mantêm o valor como texto/atributo, sem reinterpretá-lo como HTML.
        const btnSelect = document.createElement("button");
        btnSelect.type = "button";
        btnSelect.className = "gdrive-folder-item__select";
        btnSelect.setAttribute("aria-label", `Selecionar pasta ${pasta.name}`);
        const iconWrap = document.createElement("span");
        iconWrap.className = "gdrive-folder-item__icon";
        iconWrap.setAttribute("aria-hidden", "true");
        const parsedIcon = new DOMParser().parseFromString(icon, "image/svg+xml");
        iconWrap.appendChild(document.importNode(parsedIcon.documentElement, true));
        const name = document.createElement("span");
        name.className = "gdrive-folder-item__name";
        name.textContent = pasta.name;
        btnSelect.append(iconWrap, name);

        const btnEnter = document.createElement("button");
        btnEnter.type = "button";
        btnEnter.className = "gdrive-folder-item__enter button button--ghost button--xs";
        btnEnter.setAttribute("aria-label", `Abrir pasta ${pasta.name}`);
        btnEnter.textContent = "Abrir →";
        item.append(btnSelect, btnEnter);


        btnSelect.addEventListener("click", () => {
          clearSelection();
          selectedFolder = { id: pasta.id, name: pasta.name };
          item.classList.add("is-selected");
          item.setAttribute("aria-pressed", "true");
          btnSelecionar.disabled = false;
          btnSelecionar.textContent = `Usar "${pasta.name}" como destino`;
        });

        btnEnter.addEventListener("click", () => {
          navStack.push({ id: pasta.id, nome: pasta.name });
          loadPastas(pasta.id);
        });

        folderList.appendChild(item);
      });
    }

    function updateCriarVisibilidade() {
      // Não faz sentido "criar pasta" enquanto só se está listando os Drives
      // compartilhados disponíveis, ou os itens de nível superior compartilhados
      // comigo (ainda não se entrou em nenhum deles).
      const listandoRaizSemContexto =
        (rootMode === "compartilhados" || rootMode === "compartilhados_comigo") && navStack.length === 0;
      const podeCriar = !listandoRaizSemContexto;
      btnToggleCriar.hidden = !podeCriar;
      if (!podeCriar) {
        newFolderPanel.hidden = true;
        btnToggleCriar.textContent = "+ Criar nova pasta aqui";
      }
    }

    async function loadPastas(paiId) {
      setLoading(true);
      browserBody.hidden = false;
      browserActions.hidden = false;
      btnVoltar.hidden = navStack.length === 0;
      updateCriarVisibilidade();
      updateBreadcrumb();

      try {
        const url = paiId ? `${urlListar}?pai_id=${encodeURIComponent(paiId)}` : urlListar;
        const result = await window.CV.http.fetchJson(url);
        const data = result.data || {};
        if (!result.ok) throw new Error(data.erro || "Erro ao carregar pastas");
        renderFolders(data.pastas || []);
      } catch (err) {
        folderList.innerHTML = `<p class="gdrive-error">Erro: ${window.CV.util.escapeHtml(String(err.message))}</p>`;
        folderList.hidden = false;
        folderEmpty.hidden = true;
      } finally {
        setLoading(false);
      }
    }

    async function loadDrives() {
      setLoading(true);
      browserBody.hidden = false;
      browserActions.hidden = false;
      btnVoltar.hidden = true;
      updateCriarVisibilidade();
      updateBreadcrumb();

      try {
        const result = await window.CV.http.fetchJson(urlDrives);
        const data = result.data || {};
        if (!result.ok) throw new Error(data.erro || "Erro ao carregar Drives compartilhados");
        renderFolders(data.pastas || [], { sharedDriveIcon: true });
      } catch (err) {
        folderList.innerHTML = `<p class="gdrive-error">Erro: ${window.CV.util.escapeHtml(String(err.message))}</p>`;
        folderList.hidden = false;
        folderEmpty.hidden = true;
      } finally {
        setLoading(false);
      }
    }

    async function loadCompartilhadosComigo() {
      setLoading(true);
      browserBody.hidden = false;
      browserActions.hidden = false;
      btnVoltar.hidden = true;
      updateCriarVisibilidade();
      updateBreadcrumb();

      try {
        const result = await window.CV.http.fetchJson(urlCompartilhadosComigo);
        const data = result.data || {};
        if (!result.ok) throw new Error(data.erro || "Erro ao carregar pastas compartilhadas comigo");
        renderFolders(data.pastas || []);
      } catch (err) {
        folderList.innerHTML = `<p class="gdrive-error">Erro: ${window.CV.util.escapeHtml(String(err.message))}</p>`;
        folderList.hidden = false;
        folderEmpty.hidden = true;
      } finally {
        setLoading(false);
      }
    }

    function loadRoot(mode) {
      rootMode = mode;
      navStack.length = 0;
      updateTabs();
      if (mode === "compartilhados") {
        loadDrives();
      } else if (mode === "compartilhados_comigo") {
        loadCompartilhadosComigo();
      } else {
        loadPastas(null);
      }
    }

    btnMeuDrive.addEventListener("click", () => loadRoot("meu_drive"));
    btnDrivesCompartilhados.addEventListener("click", () => loadRoot("compartilhados"));
    if (btnCompartilhadosComigo) {
      btnCompartilhadosComigo.addEventListener("click", () => loadRoot("compartilhados_comigo"));
    }

    btnVoltar.addEventListener("click", () => {
      navStack.pop();
      if (navStack.length === 0 && rootMode === "compartilhados") {
        loadDrives();
      } else if (navStack.length === 0 && rootMode === "compartilhados_comigo") {
        loadCompartilhadosComigo();
      } else {
        loadPastas(currentPaiId());
      }
    });

    btnToggleCriar.addEventListener("click", () => {
      const open = !newFolderPanel.hidden;
      newFolderPanel.hidden = open;
      btnToggleCriar.textContent = open ? "+ Criar nova pasta aqui" : "× Cancelar";
      if (!open) novaPastaNome.focus();
    });

    function selecionarPastaCriada(pasta) {
      // Roda depois da recarga, quando a pasta JÁ existe no servidor. Nada aqui
      // pode virar "não foi possível criar a pasta": se a seleção não acontecer,
      // a pasta nova continua visível na lista recarregada, só não vem marcada.
      const id = pasta && pasta.id;
      if (!id) return;
      // `CSS.escape` porque o id entra num seletor de atributo: no modo mock o id
      // é "mock-nova-" + o nome digitado (`services.py:200`), e uma aspa no nome
      // fazia o `querySelector` estourar `SyntaxError`.
      const item = folderList.querySelector(`[data-id="${CSS.escape(String(id))}"]`);
      if (item) item.querySelector(".gdrive-folder-item__select")?.click();
    }

    btnCriar.addEventListener("click", async () => {
      const nome = (novaPastaNome.value || "").trim();
      if (!nome) {
        novaPastaNome.focus();
        return;
      }
      btnCriar.disabled = true;
      btnCriar.textContent = "Criando…";

      try {
        const result = await window.CV.http.fetchJson(urlCriar, {
          method: "POST",
          body: { nome, pai_id: currentPaiId() || "" },
        });
        const data = result.data || {};
        if (!result.ok) throw new Error(data.erro || "Erro ao criar pasta");

        novaPastaNome.value = "";
        newFolderPanel.hidden = true;
        btnToggleCriar.textContent = "+ Criar nova pasta aqui";
        // NOVO-24: este `await` era um `.then` solto. Sem ele o callback ficava
        // FORA do `try` — um erro ali (id ausente, seletor inválido) não chegava
        // ao `catch` de baixo e sumia no console — e o `finally` reabilitava o
        // botão por cima da recarga, deixando "Criar pasta" clicável com a lista
        // ainda em "Carregando…".
        await loadPastas(currentPaiId());
        selecionarPastaCriada(data.pasta);
      } catch (err) {
        await window.CV.feedback.alert("Não foi possível criar a pasta: " + err.message);
      } finally {
        btnCriar.disabled = false;
        btnCriar.textContent = "Criar pasta";
      }
    });

    novaPastaNome.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        btnCriar.click();
      }
    });

    btnSelecionar.addEventListener("click", () => {
      if (!selectedFolder) return;
      inputPastaId.value = selectedFolder.id;
      inputPastaNome.value = selectedFolder.name;
      formSalvar.submit();
    });
  }

  function initPreviaMassa(container) {
    const urlPrevia = container.dataset.urlPrevia;
    const btnPrevia = document.getElementById("gdrive-btn-previa");
    const previaBox = document.getElementById("gdrive-previa");
    const previaLista = document.getElementById("gdrive-previa-lista");
    const previaAviso = document.getElementById("gdrive-previa-aviso");
    if (!btnPrevia || !urlPrevia) return;

    const TEXTO_VER = "Ver prévia";
    const TEXTO_OCULTAR = "Ocultar prévia";

    async function abrirPrevia() {
      btnPrevia.disabled = true;
      btnPrevia.textContent = "Carregando…";
      try {
        const result = await window.CV.http.fetchJson(urlPrevia);
        const data = result.data || {};
        if (!result.ok) throw new Error(data.erro || "Falha ao carregar a prévia.");
        previaLista.innerHTML = "";
        if (data.erro) {
          previaAviso.hidden = false;
          previaAviso.textContent = "Erro ao gerar prévia: " + data.erro;
        } else {
          const linhas = data.linhas || [];
          if (linhas.length === 0) {
            const li = document.createElement("li");
            li.textContent = "Nenhum arquivo a organizar.";
            previaLista.appendChild(li);
          } else {
            linhas.forEach((linha) => {
              const li = document.createElement("li");
              li.textContent = linha;
              previaLista.appendChild(li);
            });
          }
          const avisos = [];
          if (data.truncado) {
            avisos.push("Mostrando as primeiras " + linhas.length + " linhas (há mais).");
          }
          if (data.itens_com_erro) {
            avisos.push(
              data.itens_com_erro +
                " evento(s)/ofício(s) não puderam ser incluídos na prévia (erro ao planejar). " +
                "Os demais itens continuam listados normalmente."
            );
          }
          previaAviso.hidden = avisos.length === 0;
          previaAviso.textContent = avisos.join(" ");
        }
        previaBox.hidden = false;
        btnPrevia.textContent = TEXTO_OCULTAR;
      } catch (e) {
        previaAviso.hidden = false;
        previaAviso.textContent = "Falha ao carregar a prévia.";
        previaBox.hidden = false;
        btnPrevia.textContent = TEXTO_OCULTAR;
      } finally {
        btnPrevia.disabled = false;
      }
    }

    function fecharPrevia() {
      previaBox.hidden = true;
      btnPrevia.textContent = TEXTO_VER;
    }

    btnPrevia.addEventListener("click", () => {
      if (!previaBox.hidden) {
        fecharPrevia();
      } else {
        abrirPrevia();
      }
    });
  }

  function initStatusMassa(container) {
    const urlStatus = container.dataset.urlStatus;
    const box = document.getElementById("gdrive-status");
    const texto = document.getElementById("gdrive-status-texto");
    const percentEl = document.getElementById("gdrive-status-percent");
    const progressEl = document.getElementById("gdrive-progress");
    const progressFill = document.getElementById("gdrive-progress-fill");
    if (!urlStatus || !box || !texto) return;

    let timer = null;

    function setProgress(pct) {
      if (progressFill) progressFill.style.width = pct + "%";
      if (progressEl) progressEl.setAttribute("aria-valuenow", String(pct));
      if (percentEl) percentEl.textContent = pct + "%";
    }

    function render(data) {
      if (!data || !data.existe) {
        box.hidden = true;
        return;
      }
      box.hidden = false;
      box.classList.remove("is-running", "is-done", "is-error");

      const total = data.total_eventos || 0;
      const feitos = data.eventos_processados || 0;
      const pct = total > 0 ? Math.round((feitos / total) * 100) : data.em_andamento ? 0 : 100;

      if (data.em_andamento) {
        box.classList.add("is-running");
        setProgress(pct);
        const sufixo = total ? ` (${feitos}/${total} eventos)` : "";
        texto.textContent = "Em andamento…" + sufixo;
      } else if (data.status === "concluida") {
        box.classList.add("is-done");
        setProgress(100);
        const erros = data.erros ? `, ${data.erros} erro(s)` : "";
        texto.textContent =
          `Concluída: ${data.total_eventos} evento(s) e ${data.avulsos} avulso(s)${erros}.`;
      } else if (data.status === "erro") {
        box.classList.add("is-error");
        if (percentEl) percentEl.textContent = "";
        texto.textContent = "Erro: " + (data.mensagem || "falha na reorganização.");
      }
    }

    async function poll() {
      try {
        const result = await window.CV.http.fetchJson(urlStatus);
        const data = result.data || {};
        if (!result.ok) throw new Error(data.erro || "Falha ao consultar o status.");
        render(data);
        if (data && data.existe && data.em_andamento) {
          timer = setTimeout(poll, 3000);
        } else if (timer) {
          clearTimeout(timer);
          timer = null;
        }
      } catch (e) {
        if (timer) clearTimeout(timer);
        timer = null;
      }
    }

    poll();
  }

  function init() {
    const container = document.getElementById("gdrive-folder-browser");
    if (container) initFolderBrowser(container);
    const massa = document.getElementById("gdrive-massa");
    if (massa) {
      initPreviaMassa(massa);
      initStatusMassa(massa);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
