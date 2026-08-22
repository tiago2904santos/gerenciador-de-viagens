/* Fila de download do seletor de documentos (`c-v2.download_picker`).
 *
 * Um termo vira vários documentos: o genérico, o da viatura e um por servidor.
 * Aqui se escolhe QUAIS baixar, em que formato, e se saem como arquivos
 * separados ou fundidos num só.
 *
 * A fila é SEQUENCIAL de propósito. Cada arquivo é gerado no servidor (fila do
 * `documentos.async_generation`) e disparar cinco pedidos de uma vez põe cinco
 * conversões DOCX→PDF para competir pelos mesmos núcleos — o último chega mais
 * tarde do que se tivessem ido em ordem. E o navegador trata uma rajada de
 * downloads simultâneos como comportamento suspeito.
 *
 * Cada item repete o caminho que a tela de espera já usava
 * (`document-generation-wait.js`): pedir com `X-Requested-With` → receber `202`
 * com o job → consultar `status_url` até `complete` → baixar `result_url`.
 * Quando o documento já está em cache, a primeira resposta já é o arquivo.
 */
(function () {
  "use strict";

  var MAX_ESPERA_MS = 120000;

  function pedir(url) {
    return window.CV.http.request(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
  }

  function nomeDoArquivo(response, alternativo) {
    var disposicao = response.headers.get("Content-Disposition") || "";
    var casou = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposicao);
    if (!casou) return alternativo;
    try {
      return decodeURIComponent(casou[1]);
    } catch (erro) {
      return casou[1];
    }
  }

  /* O arquivo é salvo a partir do BLOB, e não navegando para a URL: é assim que
     se sabe que este terminou antes de começar o próximo. Navegar dispara o
     download e devolve o controle na mesma hora — a fila deixaria de ser fila. */
  function salvar(blob, nome) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = nome || "documento";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 60000);
  }

  function esperarJob(statusUrl, inicio) {
    return pedir(statusUrl).then(function (response) {
      return response.json().then(function (dados) {
        if (dados.status === "complete" && dados.result_url) return dados.result_url;
        if (dados.status === "error") throw new Error(dados.error || "Falha ao gerar o documento.");
        if (Date.now() - inicio > MAX_ESPERA_MS) throw new Error("A geração demorou demais.");
        return new Promise(function (resolve) {
          window.setTimeout(resolve, dados.retry_after_ms || 1000);
        }).then(function () {
          return esperarJob(statusUrl, inicio);
        });
      });
    });
  }

  function baixarUm(url, nomeAlternativo) {
    return pedir(url).then(function (response) {
      var tipo = response.headers.get("Content-Type") || "";
      if (response.ok && tipo.indexOf("application/json") === -1) {
        return response.blob().then(function (blob) {
          salvar(blob, nomeDoArquivo(response, nomeAlternativo));
        });
      }
      return response.json().then(function (dados) {
        if (!dados.status_url) throw new Error(dados.error || "Não foi possível gerar o documento.");
        return esperarJob(dados.status_url, Date.now()).then(function (resultUrl) {
          return pedir(resultUrl).then(function (final) {
            if (!final.ok) throw new Error("Não foi possível baixar o documento.");
            return final.blob().then(function (blob) {
              salvar(blob, nomeDoArquivo(final, nomeAlternativo));
            });
          });
        });
      });
    });
  }

  function criarLinhaDeFila(lista, titulo) {
    var item = document.createElement("li");
    item.className = "download-picker__queue-item";
    item.setAttribute("data-state", "waiting");
    var nome = document.createElement("span");
    nome.className = "download-picker__queue-name";
    nome.textContent = titulo;
    var estado = document.createElement("span");
    estado.className = "download-picker__queue-state";
    estado.textContent = "Na fila";
    item.appendChild(nome);
    item.appendChild(estado);
    lista.appendChild(item);
    return {
      andamento: function () {
        item.setAttribute("data-state", "running");
        estado.textContent = "Gerando…";
      },
      pronto: function () {
        item.setAttribute("data-state", "done");
        estado.textContent = "Baixado";
      },
      falhou: function () {
        item.setAttribute("data-state", "error");
        estado.textContent = "Falhou";
      },
    };
  }

  function selecionado(raiz, nome) {
    var marcado = raiz.querySelector('input[name$="-' + nome + '"]:checked');
    return marcado ? marcado.value : "";
  }

  function montarLista(raiz, dados) {
    var lista = raiz.querySelector("[data-download-picker-list]");
    lista.textContent = "";
    dados.itens.forEach(function (item, indice) {
      var li = document.createElement("li");
      li.className = "download-picker__item";
      var rotulo = document.createElement("label");
      rotulo.className = "download-picker__check";
      var caixa = document.createElement("input");
      caixa.type = "checkbox";
      caixa.checked = true;
      caixa.value = item.id;
      caixa.setAttribute("data-download-picker-item", String(indice));
      var texto = document.createElement("span");
      texto.className = "download-picker__item-copy";
      var titulo = document.createElement("strong");
      titulo.className = "download-picker__item-title";
      titulo.textContent = item.titulo;
      texto.appendChild(titulo);
      if (item.subtitulo) {
        var sub = document.createElement("small");
        sub.className = "download-picker__item-meta";
        sub.textContent = item.subtitulo;
        texto.appendChild(sub);
      }
      rotulo.appendChild(caixa);
      rotulo.appendChild(texto);
      li.appendChild(rotulo);
      lista.appendChild(li);
    });
  }

  function urlsDoItem(item, origem) {
    if (item.versoes) return item.versoes[origem] || {};
    return item.urls || {};
  }

  function atualizarDisponibilidade(raiz, dados) {
    var origem = selecionado(raiz, "origem") || "original";
    var formatos = raiz.querySelectorAll('input[name$="-formato"]');
    formatos.forEach(function (radio) {
      radio.disabled = !dados.itens.some(function (item) {
        return Boolean(urlsDoItem(item, origem)[radio.value]);
      });
    });
    var formatoAtual = raiz.querySelector('input[name$="-formato"]:checked');
    if (formatoAtual && formatoAtual.disabled) {
      var primeiro = raiz.querySelector('input[name$="-formato"]:not(:disabled)');
      if (primeiro) primeiro.checked = true;
    }
    var formato = selecionado(raiz, "formato") || "pdf";
    raiz.querySelectorAll("[data-download-picker-item]").forEach(function (caixa) {
      var item = dados.itens[Number(caixa.getAttribute("data-download-picker-item"))];
      var disponivel = Boolean(urlsDoItem(item, origem)[formato]);
      if (caixa.disabled && disponivel) caixa.checked = true;
      caixa.disabled = !disponivel;
      if (!disponivel) caixa.checked = false;
      var linha = caixa.closest(".download-picker__item");
      if (linha) linha.setAttribute("data-disabled", disponivel ? "false" : "true");
    });
  }

  function urlCompilado(dados, formato, origem, escolhidos) {
    var base = dados.compilado;
    if (typeof base !== "string") {
      base = base[origem] ? base[origem][formato] : base[formato];
    }
    if (!base) return "";
    if (!dados.compilado_aceita_itens) return base;
    var separador = base.indexOf("?") === -1 ? "?" : "&";
    return base + separador
      + "formato=" + encodeURIComponent(formato)
      + "&origem=" + encodeURIComponent(origem)
      + "&itens=" + encodeURIComponent(escolhidos.map(function (item) { return item.id; }).join(","));
  }

  function mostrarErro(raiz, mensagem) {
    var alvo = raiz.querySelector("[data-download-picker-error]");
    if (!alvo) return;
    alvo.textContent = mensagem;
    alvo.hidden = !mensagem;
  }

  function processar(raiz, dados) {
    var formato = selecionado(raiz, "formato") || "pdf";
    var saida = selecionado(raiz, "saida") || "separados";
    var origem = selecionado(raiz, "origem") || "original";
    var fila = raiz.querySelector("[data-download-picker-queue]");
    var confirmar = raiz.querySelector("[data-download-picker-confirm]")
      || raiz.closest("dialog").querySelector("[data-download-picker-confirm]");

    var escolhidos = [];
    raiz.querySelectorAll("[data-download-picker-item]").forEach(function (caixa) {
      if (caixa.checked) escolhidos.push(dados.itens[Number(caixa.getAttribute("data-download-picker-item"))]);
    });
    if (!escolhidos.length) {
      mostrarErro(raiz, "Marque pelo menos um documento.");
      return;
    }
    mostrarErro(raiz, "");

    /* "Um arquivo só" é UM item de fila: o servidor funde as páginas, e o
       navegador recebe um download só. Fundir aqui exigiria um motor de PDF no
       cliente para refazer o que o `modo=compilado` já faz. */
    var tarefas = saida === "compilado"
      ? [{ titulo: "Documento compilado", url: urlCompilado(dados, formato, origem, escolhidos) }]
      : escolhidos.map(function (item) {
        return { titulo: item.titulo, url: urlsDoItem(item, origem)[formato] };
      });

    if (tarefas.some(function (tarefa) { return !tarefa.url; })) {
      mostrarErro(raiz, "Esta combinação de origem e formato não está disponível.");
      return;
    }

    fila.textContent = "";
    fila.hidden = false;
    if (confirmar) confirmar.disabled = true;

    var linhas = tarefas.map(function (tarefa) {
      return criarLinhaDeFila(fila, tarefa.titulo);
    });

    tarefas.reduce(function (anterior, tarefa, indice) {
      return anterior.then(function () {
        linhas[indice].andamento();
        return baixarUm(tarefa.url, tarefa.titulo).then(function () {
          linhas[indice].pronto();
        }).catch(function (erro) {
          linhas[indice].falhou();
          mostrarErro(raiz, erro.message || "Não foi possível baixar um dos documentos.");
        });
      });
    }, Promise.resolve()).then(function () {
      if (confirmar) confirmar.disabled = false;
    });
  }

  function abrir(montagem) {
    var raiz = montagem.querySelector("[data-download-picker]");
    var dialogo = raiz.closest("dialog");
    var src = raiz.getAttribute("data-src");

    return pedir(src).then(function (response) {
      return response.json();
    }).then(function (dados) {
      /* Um documento só: não há o que escolher, e abrir o diálogo seria um
         clique a mais para marcar a única caixa disponível. */
      if (dados.unico && !dados.sempre_escolher) {
        var unico = dados.itens[0];
        return baixarUm(unico.urls.pdf, unico.titulo);
      }
      montarLista(raiz, dados);
      var origem = raiz.querySelector("[data-download-picker-origin]");
      if (origem) origem.hidden = !dados.origens;
      var assinado = raiz.querySelector('input[name$="-origem"][value="assinado"]');
      if (assinado) {
        assinado.disabled = !dados.itens.some(function (item) {
          return item.versoes && Object.keys(item.versoes.assinado || {}).length;
        });
      }
      raiz._downloadPickerDados = dados;
      atualizarDisponibilidade(raiz, dados);
      raiz.querySelector("[data-download-picker-queue]").hidden = true;
      mostrarErro(raiz, "");
      dialogo.showModal();
      var confirmar = dialogo.querySelector("[data-download-picker-confirm]");
      if (confirmar && !confirmar.hasAttribute("data-download-picker-bound")) {
        confirmar.setAttribute("data-download-picker-bound", "");
        confirmar.addEventListener("click", function () {
          processar(raiz, raiz._downloadPickerDados);
        });
      }
      if (!raiz.hasAttribute("data-download-picker-options-bound")) {
        raiz.setAttribute("data-download-picker-options-bound", "");
        raiz.addEventListener("change", function (evento) {
          if (!evento.target.matches('input[type="radio"]')) return;
          atualizarDisponibilidade(raiz, raiz._downloadPickerDados);
          mostrarErro(raiz, "");
        });
      }
      return null;
    }).catch(function () {
      mostrarErro(raiz, "Não foi possível consultar os documentos deste termo.");
      dialogo.showModal();
    });
  }

  /* Delegação no `document`: os cartões da lista são trocados pelo filtro AJAX,
     e um `addEventListener` preso ao botão morre junto com o HTML antigo. */
  document.addEventListener("click", function (evento) {
    var fechar = evento.target.closest("[data-download-picker-close]");
    if (fechar) {
      var dialogo = fechar.closest("dialog");
      if (!dialogo) return;
      evento.preventDefault();
      if (window.CV.overlay && typeof window.CV.overlay.closeDialog === "function") {
        window.CV.overlay.closeDialog(dialogo);
      } else if (dialogo.open) {
        dialogo.close();
      }
      return;
    }

    var gatilho = evento.target.closest("[data-download-picker-trigger]");
    if (!gatilho) return;
    var montagem = gatilho.closest(".download-picker-mount");
    if (!montagem) return;
    evento.preventDefault();
    abrir(montagem);
  });
}());
