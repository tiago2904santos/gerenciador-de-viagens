/* NOVO-07 — busca de documento sob demanda para os seletores de ofício.

   As três telas que escolhem ofício (justificativas, termos, ordens de serviço)
   têm cada uma o seu seletor artesanal em `js/pages/`: uma caixa de texto, uma
   lista de cartões e um `<select>` escondido que guarda a escolha. Nenhuma delas
   usa `components/picker.js`. O que era igual nas três é o que mora aqui.

   Antes, a lista de candidatos vinha inteira no `json_script` da página — todo
   ofício da área, ~680 bytes cada — e o `<select>` trazia um `<option>` por
   ofício. As duas coisas cresciam com a tabela. Agora o servidor manda só o que
   já está selecionado e o resto chega por `data-picker-source-url`.

   Duas coisas que este componente tem de fazer e não são óbvias:

   - **criar o `<option>` que falta.** Os três seletores marcam a escolha
     mexendo em `select.options` (`opt.selected = true`, ou `select.value = id`).
     Sem um `<option>` com aquele valor, `select.value` fica em branco sem erro
     nenhum e o formulário envia vazio.
   - **semear a lista na abertura.** Sem termo digitado o endpoint devolve os
     mais recentes até o teto do servidor. Antes a lista abria com a área
     inteira; agora abre com essa fatia, e digitar refina no servidor. */
(function () {
  "use strict";

  window.CV = window.CV || {};

  function garantirOption(select, item) {
    var valor = String(item.id);
    var existe = Array.from(select.options).some(function (opt) {
      return String(opt.value) === valor;
    });
    if (existe) return;
    var dados = item.option || {};
    var option = document.createElement("option");
    option.value = valor;
    /* O texto vem do servidor porque cada tela rotula à sua maneira — "Ofício"
       com acento na OS, "Oficio" sem acento no termo. Adivinhar aqui faria a
       opção criada pela busca sair diferente da renderizada pelo Django. */
    option.textContent = dados.texto || item.label || valor;
    if (dados.main) option.dataset.main = dados.main;
    if (dados.meta) option.dataset.meta = dados.meta;
    option.dataset.search = dados.search || item.search_text || "";
    select.appendChild(option);
  }

  /* `select`  — o `<select>` escondido que guarda a escolha
     `input`   — a caixa de texto da tela
     `onResults(itens)` — a tela funde os resumos no que ela já tinha e redesenha */
  function attach(config) {
    var select = config.select;
    var input = config.input;
    var onResults = config.onResults;
    if (!select || !input || typeof onResults !== "function") return;

    var url = (select.dataset.pickerSourceUrl || "").trim();
    /* Sem endpoint nada muda: a tela segue filtrando o que veio no HTML. */
    if (!url) return;
    if (select.dataset.documentSearchReady === "true") return;
    select.dataset.documentSearchReady = "true";

    var emVoo = null;

    function buscar(termo) {
      var alvo = url + "?q=" + encodeURIComponent(termo || "");
      emVoo = alvo;
      window.CV.http
        .fetchJson(alvo)
        .then(function (resposta) {
          /* Resposta atrasada de uma busca anterior não pode sobrescrever a
             lista de um termo mais novo. */
          if (emVoo !== alvo) return;
          /* `CV.http.fetchJson` devolve `{ok, status, data}` — o corpo do
             endpoint está em `.data`, não na raiz. */
          if (!resposta || !resposta.ok) return;
          var itens = (resposta.data && resposta.data.resultados) || [];
          itens.forEach(function (item) {
            if (item && item.id != null) garantirOption(select, item);
          });
          if (window.CV.documentSource && window.CV.documentSource.remember) {
            window.CV.documentSource.remember(itens);
          }
          onResults(itens);
        })
        /* Falha de rede não pode derrubar o campo: o que já está na tela
           continua clicável, e a próxima tecla tenta de novo. */
        .catch(function () {});
    }

    var buscarComPausa = window.CV.util.debounce(buscar, 250);

    input.addEventListener("input", function () {
      buscarComPausa(input.value);
    });

    buscar(input.value);
  }

  window.CV.documentSearch = { attach: attach };
})();
