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

    var dialog = modal.querySelector(".delete-confirm-modal__dialog");
    var form = modal.querySelector("[data-attach-signed-form]");
    var label = modal.querySelector("[data-attach-signed-label]");
    var nextInput = modal.querySelector("[data-attach-signed-next]");
    var currentBlock = modal.querySelector("[data-attach-signed-current]");
    var currentName = modal.querySelector("[data-attach-signed-current-name]");
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

    function clearSelectedFile() {
      if (!form) return;
      var input = form.querySelector('input[type="file"]');
      if (!input || !input.value) return;
      input.value = "";
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    /* Tipos do gatilho ativo, já sem os que não têm URL de upload — um documento
     * sem `anexar_url` não é anexável e nunca deve virar botão. */
    var kindsAtivos = [];

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

    function selectDocument(kind, clearFile) {
      var data = documentData(kind);
      if (!data || !data.url || !form) return;
      if (clearFile) clearSelectedFile();

      form.setAttribute("action", data.url);
      if (label) label.textContent = data.label;
      currentRemoveUrl = data.currentRemoveUrl;
      if (currentBlock) currentBlock.hidden = !data.currentName;
      if (currentName) currentName.textContent = data.currentName;
      if (currentOpen) currentOpen.setAttribute("href", data.currentViewUrl || "#");
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
    }

    /* Os botões de tipo são montados a partir do payload do gatilho, não escritos
     * no template: era ali que o número de documentos anexáveis ficava fixo em 5. */
    function montarBotoesDeTipo() {
      if (!kindOptions) return;
      var ehToggle = kindOptions.hasAttribute("data-attach-signed-kind-toggle");
      kindOptions.innerHTML = "";
      kindsAtivos.forEach(function (item) {
        var button = document.createElement("button");
        button.type = "button";
        /* A classe do segmento vem do GRUPO, não daqui: no v2 o grupo é o
         * `toggle` do sistema e os itens são `toggle__item`; nas telas legadas
         * segue a classe antiga, que as folhas de lá esperam. O sinalizador é
         * SEM VALOR de propósito — atributo com valor dentro do `hook` do
         * componente sai escapado e o seletor nunca casa. */
        button.className = ehToggle
          ? "toggle__item"
          : "attach-signed-modal__kind-option";
        button.setAttribute("aria-pressed", "false");
        button.setAttribute("data-attach-signed-kind", item.key);
        var rotulo = document.createElement("span");
        rotulo.textContent = item.option_label || "";
        button.appendChild(rotulo);
        kindOptions.appendChild(button);
      });
    }

    function closeModal() {
      window.CV.overlay.closeDialog(modal);
      activeTrigger = null;
      currentRemoveUrl = "";
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
    document.addEventListener("click", onDocumentClick);
    instancias.push({
      root: modal,
      desmontar: function () {
        document.removeEventListener("click", onDocumentClick);
        modal.removeAttribute(BOUND);
      },
    });

    if (form) {
      form.addEventListener("submit", function () {
        if (window.CV && window.CV.documentProgress) {
          window.CV.documentProgress.begin(uploadButton, {
            title: "Anexando documento…",
            detail: "O arquivo será salvo; você pode continuar navegando.",
          });
        }
      });
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
