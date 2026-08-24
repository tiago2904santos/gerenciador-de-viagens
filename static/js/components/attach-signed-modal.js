(function () {
  "use strict";

  var activeTrigger = null;
  var currentRemoveUrl = "";
  var BOUND = "data-attach-signed-bound";
  /* JS-02 — uma entrada por modal vivo: { root, desmontar }. */
  var instancias = [];

  /* H-03: aqui havia `KINDS`, uma lista fixa de cinco ordinais latinos, e
   * `kindPrefix`, que traduzia cada ordinal no prefixo dos seus 6 atributos
   * `data-*`. O gatilho agora declara seus tipos num payload JSON, então o
   * número de documentos anexáveis não é mais constante em lugar nenhum.
   *
   * Duas formas de gatilho continuam valendo, porque são dois casos de uso:
   *  - multi-tipo (`data-attach-signed-kinds`): o modal mostra os botões de
   *    seleção — etapa Documentos e menu do card de prestação;
   *  - tipo único (atributos planos no próprio botão): o menu de ações do
   *    entity card, onde o botão JÁ é o documento. Sem ordinal nenhum. */
  function kindsDoGatilho(trigger) {
    if (!trigger) return [];
    var payload = trigger.getAttribute("data-attach-signed-kinds");
    if (payload) {
      try {
        var lista = JSON.parse(payload);
        return Array.isArray(lista) ? lista : [];
      } catch (error) {
        window.CV.log.error("attachSigned", "payload de tipos inválido", error);
        return [];
      }
    }
    var url = trigger.getAttribute("data-attach-signed-url");
    if (!url) return [];
    return [{
      key: "",
      option_label: "",
      doc_label: trigger.getAttribute("data-attach-signed-doc-label") || "",
      url: url,
      current_name: trigger.getAttribute("data-attach-signed-current-name") || "",
      current_view_url: trigger.getAttribute("data-attach-signed-current-view-url") || "",
      current_remove_url: trigger.getAttribute("data-attach-signed-current-remove-url") || "",
    }];
  }

  function init(root) {
    var scope = root && root.querySelector ? root : document;
    var modal = scope.matches && scope.matches("[data-attach-signed-modal]")
      ? scope
      : scope.querySelector("[data-attach-signed-modal]");
    if (!modal || modal.getAttribute(BOUND) === "true") return false;
    modal.setAttribute(BOUND, "true");

    /* A casca do `<dialog>` do v2. Era `.delete-confirm-modal__dialog`, do
       desenho antigo — o seletor não casava com nada desde que o diálogo virou
       `c-v2.modal`, e o foco inicial caía no `<dialog>` por acaso. */
    var dialog = modal.querySelector(".modal__shell");
    var form = modal.querySelector("[data-attach-signed-form]");
    var label = modal.querySelector("[data-attach-signed-label]");
    var nextInput = modal.querySelector("[data-attach-signed-next]");
    var currentBlock = modal.querySelector("[data-attach-signed-current]");
    var currentName = modal.querySelector("[data-attach-signed-current-name]");
    var currentMeta = modal.querySelector("[data-attach-signed-current-meta]");
    var currentOpen = modal.querySelector("[data-attach-signed-current-open]");
    var kindSelector = modal.querySelector("[data-attach-signed-kind-selector]");
    var kindOptions = modal.querySelector("[data-attach-signed-kind-options]");
    var fileDescription = modal.querySelector("[data-attach-signed-file-description]");
    var fileHelp = modal.querySelector("[data-attach-signed-file-help]");
    var fileInput = modal.querySelector('input[type="file"]');
    var chooseLabel = modal.querySelector("[data-file-picker-action-label]");
    var uploadButton = modal.querySelector("[data-file-upload-button]");
    var fileDefaults = {
      accept: fileInput ? fileInput.getAttribute("accept") || "" : "",
      multiple: fileInput ? fileInput.multiple : false,
      description: fileDescription ? fileDescription.textContent : "",
      help: fileHelp ? fileHelp.textContent : "",
      choose: chooseLabel ? chooseLabel.textContent : "",
      upload: uploadButton ? uploadButton.textContent : "",
    };

    /* NOVO-23 — remover o assinado é a única ação AJAX deste modal. Faixa
       inline, no idioma da casa para erro assíncrono: não dá para abrir um
       CV.feedback por cima, porque já estamos dentro de um diálogo. */
    var erroBox = modal.querySelector("[data-attach-signed-error]");

    function limparErro() {
      if (!erroBox) return;
      erroBox.textContent = "";
      erroBox.hidden = true;
    }

    function mostrarErro(mensagem) {
      if (!erroBox) return;
      erroBox.textContent = mensagem;
      erroBox.hidden = false;
    }

    /* Tipos do gatilho ativo, já sem os que não têm URL de upload — um documento
     * sem `anexar_url` não é anexável e nunca deve virar botão. */
    var kindsAtivos = [];
    var documentoAtual = null;
    var kindAtual = "";
    var arquivosSelecionados = Object.create(null);
    var trocaProgramatica = false;

    function arquivosPendentes() {
      return kindsAtivos.filter(function (item) {
        return !!arquivosSelecionados[item.key];
      });
    }

    function atualizarAcaoDeUpload() {
      if (!uploadButton) return;
      uploadButton.disabled = kindsAtivos.length > 1
        ? arquivosPendentes().length === 0
        : !(fileInput && fileInput.files && fileInput.files.length);
    }

    function atualizarBotoesDeTipo() {
      if (!kindOptions) return;
      Array.prototype.forEach.call(
        kindOptions.querySelectorAll("[data-attach-signed-kind]"),
        function (button) {
          var kind = button.getAttribute("data-attach-signed-kind");
          var temArquivo = !!arquivosSelecionados[kind];
          var status = button.querySelector("[data-attach-signed-kind-status]");
          button.classList.toggle("has-file", temArquivo);
          if (status) status.hidden = !temArquivo;
        }
      );
    }

    function substituirArquivoDoPicker(file) {
      if (!fileInput) return;
      trocaProgramatica = true;
      if (window.CV.filePicker && window.CV.filePicker.replaceFiles) {
        window.CV.filePicker.replaceFiles(fileInput, file ? [file] : [], true);
      } else {
        fileInput.value = "";
        fileInput.dispatchEvent(new Event("change", { bubbles: true }));
      }
      trocaProgramatica = false;
    }

    function clearSelectedFile() {
      substituirArquivoDoPicker(null);
    }

    function guardarSelecaoAtual() {
      if (!kindAtual || !fileInput) return;
      var arquivo = fileInput.files && fileInput.files.length
        ? fileInput.files[0]
        : null;
      if (arquivo) arquivosSelecionados[kindAtual] = arquivo;
      else delete arquivosSelecionados[kindAtual];
      atualizarBotoesDeTipo();
      atualizarAcaoDeUpload();
    }

    function documentData(kind) {
      var achado = kindsAtivos.filter(function (item) {
        return item.key === kind;
      })[0];
      if (!achado) return null;
      return {
        url: achado.url || "",
        label: achado.doc_label || "este documento",
        currentName: achado.current_name || "",
        currentViewUrl: achado.current_view_url || "",
        currentRemoveUrl: achado.current_remove_url || "",
      };
    }

    function updateReturnUrl(kind) {
      if (!nextInput) return;
      var base = window.location.pathname + window.location.search;
      var reopenKey = activeTrigger
        ? activeTrigger.getAttribute("data-attach-signed-reopen-key") || ""
        : "";
      nextInput.value = reopenKey
        ? base + "#attach-signed=" + encodeURIComponent(reopenKey) + "&kind=" + encodeURIComponent(kind)
        : base + window.location.hash;
    }

    /* O arquivo persistido ocupa a própria linha de resultado do picker. Ao
       escolher uma substituição, o `file-picker.js` passa a controlar o nome e
       estas ações somem; ao limpar a seleção, o anexo atual volta para a mesma
       linha, sem criar um segundo card abaixo do campo. */
    function sincronizarDocumentoAtual() {
      if (!currentName) return;
      var temSelecao = !!(
        fileInput && fileInput.files && fileInput.files.length
      );
      var temAtual = !!(documentoAtual && documentoAtual.currentName);
      var mostrarAtual = temAtual && !temSelecao;

      if (!temSelecao) {
        currentName.textContent = temAtual
          ? documentoAtual.currentName
          : currentName.getAttribute("data-default-label") || "Nenhum arquivo selecionado";
        currentName.classList.toggle(
          "prestacao-file-picker__value--selected",
          temAtual
        );
      }
      if (currentBlock) currentBlock.hidden = !mostrarAtual;
      if (currentMeta) currentMeta.hidden = !mostrarAtual;
    }

    function selectDocument(kind, preserveCurrentFile) {
      var data = documentData(kind);
      if (!data || !data.url || !form) return;
      if (preserveCurrentFile) guardarSelecaoAtual();

      form.setAttribute("action", data.url);
      if (label) label.textContent = data.label;
      kindAtual = kind;
      documentoAtual = data;
      currentRemoveUrl = data.currentRemoveUrl;
      if (currentOpen) currentOpen.setAttribute("href", data.currentViewUrl || "#");
      substituirArquivoDoPicker(arquivosSelecionados[kind] || null);
      sincronizarDocumentoAtual();
      updateReturnUrl(kind);

      if (!kindOptions) return;
      Array.prototype.forEach.call(
        kindOptions.querySelectorAll("[data-attach-signed-kind]"),
        function (button) {
          var active = button.getAttribute("data-attach-signed-kind") === kind;
          button.classList.toggle("is-active", active);
          button.setAttribute("aria-pressed", active ? "true" : "false");
        }
      );
      atualizarBotoesDeTipo();
      atualizarAcaoDeUpload();
    }

    /* Os botões de tipo são montados a partir do payload do gatilho, não escritos
     * no template: era ali que o número de documentos anexáveis ficava fixo em 5. */
    function montarBotoesDeTipo() {
      if (!kindOptions) return;

      kindOptions.innerHTML = "";
      kindsAtivos.forEach(function (item) {
        var button = document.createElement("button");
        button.type = "button";
        /* Segmento do `toggle` do sistema. Havia uma segunda classe aqui
         * (`attach-signed-modal__kind-option`, do desenho antigo) escolhida por
         * um sinalizador no grupo; ela saiu em 2026-08-20 junto com a folha que
         * a desenhava — o diálogo de anexar é `c-v2.modal` desde a migração, e
         * o grupo é sempre o `c-v2.toggle`. */
        button.className = "toggle__item";
        button.setAttribute("aria-pressed", "false");
        button.setAttribute("data-attach-signed-kind", item.key);
        var rotulo = document.createElement("span");
        rotulo.textContent = item.option_label || "";
        button.appendChild(rotulo);
        var status = document.createElement("span");
        status.className = "attach-signed__kind-status";
        status.setAttribute("data-attach-signed-kind-status", "");
        status.setAttribute("aria-label", "Arquivo selecionado");
        status.textContent = "✓";
        status.hidden = true;
        button.appendChild(status);
        kindOptions.appendChild(button);
      });
    }

    function closeModal() {
      window.CV.overlay.closeDialog(modal);
      activeTrigger = null;
      documentoAtual = null;
      currentRemoveUrl = "";
      kindAtual = "";
      arquivosSelecionados = Object.create(null);
      clearSelectedFile();
      limparErro();
      var hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
      if (hashParams.has("attach-signed")) {
        hashParams.delete("attach-signed");
        hashParams.delete("kind");
        var remainingHash = hashParams.toString();
        window.history.replaceState(
          null,
          "",
          window.location.pathname + window.location.search + (remainingHash ? "#" + remainingHash : "")
        );
      }
    }

    function openModal(trigger, initialKind) {
      if (!form) return;

      limparErro();
      activeTrigger = trigger;
      kindAtual = "";
      arquivosSelecionados = Object.create(null);
      clearSelectedFile();

      kindsAtivos = kindsDoGatilho(trigger).filter(function (item) {
        return item && item.url;
      });
      if (!kindsAtivos.length) {
        activeTrigger = null;
        return;
      }

      if (fileInput) {
        fileInput.setAttribute(
          "accept",
          trigger.getAttribute("data-attach-signed-accept") || fileDefaults.accept
        );
        fileInput.multiple = trigger.getAttribute("data-attach-signed-multiple") === "true"
          || fileDefaults.multiple;
      }
      if (fileDescription) {
        fileDescription.textContent =
          trigger.getAttribute("data-attach-signed-file-description") || fileDefaults.description;
      }
      if (fileHelp) {
        fileHelp.textContent =
          trigger.getAttribute("data-attach-signed-file-help") || fileDefaults.help;
      }
      if (chooseLabel) {
        chooseLabel.textContent =
          trigger.getAttribute("data-attach-signed-choose-label") || fileDefaults.choose;
      }
      if (uploadButton) {
        uploadButton.textContent =
          trigger.getAttribute("data-attach-signed-upload-label") || fileDefaults.upload;
      }

      if (kindSelector) kindSelector.hidden = kindsAtivos.length < 2;
      montarBotoesDeTipo();

      // O tipo inicial pode vir do hash (reabrir depois de salvar) ou do gatilho.
      // Antes o fallback era o literal "primary"; agora é o primeiro tipo que o
      // gatilho declarou — que é o que "primeiro" sempre quis dizer.
      var chaves = kindsAtivos.map(function (item) { return item.key; });
      var preferido =
        initialKind || trigger.getAttribute("data-attach-signed-initial-kind") || "";
      var escolhido = chaves.indexOf(preferido) !== -1 ? preferido : chaves[0];
      selectDocument(escolhido, false);

      window.CV.overlay.openDialog(modal, {
        opener: trigger,
        initialFocus: fileInput || dialog,
        onRequestClose: closeModal,
      });
    }

    function removeCurrentSigned() {
      if (!currentRemoveUrl || !form) return;
      limparErro();
      window.CV.http.request(currentRemoveUrl, {
        method: "POST",
        form: form,
      }).then(function (response) {
        /* NOVO-23 — `CV.http.request` devolve o `Response` cru, e status de
           erro NÃO rejeita a promise. Sem esta checagem, 403, 404 e 500 caíam
           no caminho de sucesso e recarregavam a página como se o documento
           tivesse sido removido — o usuário voltava, via o anexo ainda ali e
           não tinha como saber que a remoção falhou.

           A view responde com redirect e `messages.success`, então `ok` só é
           falso quando algo deu errado de verdade. */
        if (!response.ok) {
          var recusa = new Error(
            "O servidor recusou a remoção (HTTP " + response.status + ")."
            + " O documento assinado continua anexado."
          );
          /* Marca o que é texto escrito para o usuário. Sem isso, a falha de
             rede cai no mesmo `.catch` e a faixa mostra o "Failed to fetch"
             cru do navegador — que é o que `calculateDiarias` faz hoje no
             editor de roteiros, e não vale copiar. */
          recusa.paraUsuario = true;
          throw recusa;
        }
        window.location.reload();
      }).catch(function (error) {
        /* E sem `.catch` a falha de rede não removia, não recarregava e não
           avisava: o clique simplesmente não fazia nada. */
        mostrarErro(
          error && error.paraUsuario
            ? error.message
            : "Não foi possível falar com o servidor. O documento assinado"
              + " continua anexado — tente de novo."
        );
        window.CV.log.error("attachSigned", "falha ao remover assinado", error);
      });
    }

    /* JS-02 — este listener é registrado por modal, dentro do `init`, e o
       guard `BOUND` é por elemento: cada painel novo trazido por AJAX
       (CV.collection troca o painel inteiro) instala mais um handler em
       `document`, todos vivos ao mesmo tempo e cada um segurando o modal
       antigo. Nomeado e registrado para o `destroy` poder removê-lo. */
    function onDocumentClick(event) {
      var trigger = event.target.closest("[data-attach-signed-trigger]");
      if (trigger) {
        event.preventDefault();
        openModal(
          trigger,
          trigger.getAttribute("data-attach-signed-initial-kind") || ""
        );
        return;
      }

      if (!modal.hidden && event.target.closest("[data-attach-signed-cancel]")) {
        event.preventDefault();
        closeModal();
        return;
      }

      if (!modal.hidden && event.target.closest("[data-attach-signed-remove]")) {
        event.preventDefault();
        removeCurrentSigned();
        return;
      }

      var kindButton = event.target.closest("[data-attach-signed-kind]");
      if (!modal.hidden && kindButton) {
        event.preventDefault();
        selectDocument(kindButton.getAttribute("data-attach-signed-kind"), true);
      }
    }
    function onFilePickerChange(event) {
      if (event.target && event.target.closest("[data-file-picker]")) {
        if (!trocaProgramatica) guardarSelecaoAtual();
        sincronizarDocumentoAtual();
        atualizarAcaoDeUpload();
      }
    }
    document.addEventListener("click", onDocumentClick);
    modal.addEventListener("cv:file-picker:change", onFilePickerChange);
    instancias.push({
      root: modal,
      desmontar: function () {
        document.removeEventListener("click", onDocumentClick);
        modal.removeEventListener("cv:file-picker:change", onFilePickerChange);
        if (form) form.removeEventListener("submit", anexarArquivosSelecionados);
        modal.removeAttribute(BOUND);
      },
    });

    function anexarArquivosSelecionados(event) {
      if (kindsAtivos.length < 2) {
        if (window.CV && window.CV.documentProgress) {
          window.CV.documentProgress.begin(uploadButton, {
            title: "Anexando documento…",
            detail: "O arquivo será salvo; você pode continuar navegando.",
          });
        }
        return;
      }

      event.preventDefault();
      guardarSelecaoAtual();
      limparErro();
      var pendentes = arquivosPendentes();
      if (!pendentes.length) {
        mostrarErro("Selecione ao menos um arquivo para anexar.");
        atualizarAcaoDeUpload();
        return;
      }

      if (uploadButton) uploadButton.disabled = true;
      if (window.CV && window.CV.documentProgress) {
        window.CV.documentProgress.begin(uploadButton, {
          title: "Anexando arquivos…",
          detail: "Os arquivos selecionados serão salvos em sequência.",
        });
      }

      var enviados = 0;

      /* O motivo da recusa vem do servidor, não do número do status.
         `NOVO-20260824-133423-35fbd4d59a84`: a view agora responde
         `{ok:false, error}` com 400 para o XHR, porque o 302 que ela devolvia
         era seguido pelo `fetch` e a mensagem de erro morria na página que
         ninguém via. "PDF corrompido" é acionável; "HTTP 400" não é. */
      function recusaDoServidor(response, item) {
        var corpo = typeof response.json === "function"
          ? response.json().catch(function () { return {}; })
          : Promise.resolve({});
        return corpo.then(function (dados) {
          var erro = new Error(
            (dados && dados.error)
            || "O servidor recusou " + (item.option_label || item.doc_label || "um arquivo")
               + " (HTTP " + response.status + ")."
          );
          erro.paraUsuario = true;
          throw erro;
        });
      }

      pendentes.reduce(function (promessa, item) {
        return promessa.then(function () {
          var payload = new FormData();
          payload.append("arquivo", arquivosSelecionados[item.key]);
          if (nextInput && nextInput.value) payload.append("next", nextInput.value);
          return window.CV.http.request(item.url, {
            method: "POST",
            form: form,
            body: payload,
          }).then(function (response) {
            if (!response.ok) return recusaDoServidor(response, item);
            enviados += 1;
            delete arquivosSelecionados[item.key];
            if (item.key === kindAtual) substituirArquivoDoPicker(null);
            atualizarBotoesDeTipo();
          });
        });
      }, Promise.resolve()).then(function () {
        window.location.reload();
      }).catch(function (error) {
        if (
          window.CV && window.CV.documentProgress
          && typeof window.CV.documentProgress.error === "function"
        ) {
          window.CV.documentProgress.error(
            uploadButton,
            "Revise os arquivos que não puderam ser anexados."
          );
        }
        var prefixo = enviados
          ? enviados + " de " + pendentes.length + " arquivo(s) foram anexados. "
          : "";
        mostrarErro(
          prefixo + (error && error.paraUsuario
            ? error.message
            : "Não foi possível concluir os anexos. Tente novamente.")
        );
        atualizarAcaoDeUpload();
        window.CV.log.error("attachSigned", "falha ao anexar arquivos", error);
      });
    }

    if (form) {
      form.addEventListener("submit", anexarArquivosSelecionados);
    }

    var reopenParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    var reopenKey = reopenParams.get("attach-signed");
    if (reopenKey) {
      var reopenTrigger = Array.prototype.find.call(
        document.querySelectorAll("[data-attach-signed-reopen-key]"),
        function (trigger) {
          return trigger.getAttribute("data-attach-signed-reopen-key") === reopenKey;
        }
      );
      if (reopenTrigger) {
        openModal(reopenTrigger, reopenParams.get("kind") || reopenTrigger.getAttribute("data-attach-signed-initial-kind") || "");
      }
    }
    return true;
  }

  /* JS-02 — desmonta só os modais que viviam dentro do nó removido. */
  function destroy(scope) {
    if (!scope || (scope.nodeType !== 1 && scope.nodeType !== 9)) return;
    for (var i = instancias.length - 1; i >= 0; i -= 1) {
      var entrada = instancias[i];
      if (scope === entrada.root || (scope.contains && scope.contains(entrada.root))) {
        entrada.desmontar();
        instancias.splice(i, 1);
      }
    }
  }

  window.CV = window.CV || {};
  if (typeof window.CV.registerEnhancer === "function") {
    window.CV.registerEnhancer("attachSignedModal", init, destroy);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(document); });
  } else {
    init(document);
  }
})();
