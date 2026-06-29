(function () {
  "use strict";

  function initFolderBrowser(container) {
    const urlListar = container.dataset.urlListar;
    const urlCriar = container.dataset.urlCriar;
    const csrf = container.dataset.csrf;

    const btnCarregar = container.querySelector("#gdrive-btn-carregar");
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

    function currentPaiId() {
      return navStack.length > 0 ? navStack[navStack.length - 1].id : null;
    }

    function updateBreadcrumb() {
      if (!breadcrumbEl) return;
      if (navStack.length === 0) {
        breadcrumbEl.textContent = "Raiz do Drive";
        return;
      }
      breadcrumbEl.textContent = navStack.map((n) => n.nome).join(" › ");
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

    function renderFolders(pastas) {
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

        item.innerHTML = `
          <button type="button" class="gdrive-folder-item__select" aria-label="Selecionar pasta ${pasta.name}">
            <span class="gdrive-folder-item__icon" aria-hidden="true">📁</span>
            <span class="gdrive-folder-item__name">${escapeHtml(pasta.name)}</span>
          </button>
          <button type="button" class="gdrive-folder-item__enter cv-btn cv-btn--ghost cv-btn--xs"
                  aria-label="Abrir pasta ${pasta.name}">
            Abrir →
          </button>
        `;

        const btnSelect = item.querySelector(".gdrive-folder-item__select");
        const btnEnter = item.querySelector(".gdrive-folder-item__enter");

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

    async function loadPastas(paiId) {
      setLoading(true);
      browserBody.hidden = false;
      browserActions.hidden = false;
      btnVoltar.hidden = navStack.length === 0;
      updateBreadcrumb();

      try {
        const url = paiId ? `${urlListar}?pai_id=${encodeURIComponent(paiId)}` : urlListar;
        const resp = await fetch(url, {
          credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.erro || "Erro ao carregar pastas");
        renderFolders(data.pastas || []);
      } catch (err) {
        folderList.innerHTML = `<p class="gdrive-error">Erro: ${escapeHtml(String(err.message))}</p>`;
        folderList.hidden = false;
        folderEmpty.hidden = true;
      } finally {
        setLoading(false);
      }
    }

    btnCarregar.addEventListener("click", () => {
      navStack.length = 0;
      loadPastas(null);
    });

    btnVoltar.addEventListener("click", () => {
      navStack.pop();
      loadPastas(currentPaiId());
    });

    btnToggleCriar.addEventListener("click", () => {
      const open = !newFolderPanel.hidden;
      newFolderPanel.hidden = open;
      btnToggleCriar.textContent = open ? "+ Criar nova pasta aqui" : "× Cancelar";
      if (!open) novaPastaNome.focus();
    });

    btnCriar.addEventListener("click", async () => {
      const nome = (novaPastaNome.value || "").trim();
      if (!nome) {
        novaPastaNome.focus();
        return;
      }
      btnCriar.disabled = true;
      btnCriar.textContent = "Criando…";

      try {
        const resp = await fetch(urlCriar, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrf,
            "X-Requested-With": "XMLHttpRequest",
          },
          body: JSON.stringify({ nome, pai_id: currentPaiId() || "" }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.erro || "Erro ao criar pasta");

        novaPastaNome.value = "";
        newFolderPanel.hidden = true;
        btnToggleCriar.textContent = "+ Criar nova pasta aqui";
        // Selecionar automaticamente a pasta criada e recarregar a lista
        loadPastas(currentPaiId()).then(() => {
          // Tentar selecionar a pasta recém-criada
          const item = folderList.querySelector(`[data-id="${data.pasta.id}"]`);
          if (item) item.querySelector(".gdrive-folder-item__select")?.click();
        });
      } catch (err) {
        alert("Não foi possível criar a pasta: " + err.message);
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

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function initPreviaMassa(container) {
    const urlPrevia = container.dataset.urlPrevia;
    const btnPrevia = document.getElementById("gdrive-btn-previa");
    const previaBox = document.getElementById("gdrive-previa");
    const previaLista = document.getElementById("gdrive-previa-lista");
    const previaAviso = document.getElementById("gdrive-previa-aviso");
    if (!btnPrevia || !urlPrevia) return;

    btnPrevia.addEventListener("click", async () => {
      const original = btnPrevia.textContent;
      btnPrevia.disabled = true;
      btnPrevia.textContent = "Carregando…";
      try {
        const resp = await fetch(urlPrevia, { headers: { "X-Requested-With": "XMLHttpRequest" } });
        const data = await resp.json();
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
          previaAviso.hidden = !data.truncado;
          if (data.truncado) {
            previaAviso.textContent = "Mostrando as primeiras " + linhas.length + " linhas (há mais).";
          }
        }
        previaBox.hidden = false;
      } catch (e) {
        previaAviso.hidden = false;
        previaAviso.textContent = "Falha ao carregar a prévia.";
        previaBox.hidden = false;
      } finally {
        btnPrevia.disabled = false;
        btnPrevia.textContent = original;
      }
    });
  }

  function init() {
    const container = document.getElementById("gdrive-folder-browser");
    if (container) initFolderBrowser(container);
    const massa = document.getElementById("gdrive-massa");
    if (massa) initPreviaMassa(massa);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
