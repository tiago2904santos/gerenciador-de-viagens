# Regras de Negocio

## Cadastros

O app `cadastros` centraliza dados-base reutilizados por documentos e fluxos futuros.

Entidades ativas do modulo:

- `Unidade`: nome e sigla.
- `Estado`: cadastro de UF (nome, sigla 2 caracteres, `codigo_ibge` opcional). Ver seção **Base geográfica** e `docs/IMPORTACAO_BASE_GEOGRAFICA.md`.
- `Cidade`: pertence a um `Estado`; combinação **nome + estado** é única; `uf` espelha a sigla do estado; pode ser **capital**; `codigo_ibge` e coordenadas opcionais. Carga em lote: `docs/IMPORTACAO_BASE_GEOGRAFICA.md` (comando `importar_base_geografica`). O guia `docs/IMPORTACAO_CIDADES.md` permanece como referência do fluxo somente cidades, quando aplicável.
- `Cargo`: nome unico e em maiusculo; opcionalmente um registro pode ser marcado como **padrao** (`is_padrao`), garantindo um unico padrao por vez no banco.
- `Combustivel`: nome unico e em maiusculo; opcionalmente um registro pode ser **combustivel padrao** (`is_padrao`), garantindo um unico padrao por vez.
- `Servidor`: nome unico e em maiusculo; cargo obrigatorio no form; **CPF obrigatorio**, validado por digitos verificadores, armazenado so digitos; **RG opcional** ou marcacao **sem RG** (valor canonico interno, espelhando o legacy); **telefone opcional** (10 ou 11 digitos); unicidade condicional de CPF, RG (exceto “nao possui”) e telefone quando preenchidos; unidade opcional.
- `Viatura`: placa unica (AAA1234 ou AAA1A23), modelo obrigatorio normalizado em maiusculo, combustivel FK e tipo (`CARACTERIZADA`/`DESCARACTERIZADA`); placa persistida sem hifen e em maiusculo; **motoristas** opcionais via relacionamento N:N com `Servidor` (sem entidade Motorista).
- `ConfiguracaoSistema`: **singleton** institucional (orgao, cabecalho, endereco, contato, chefia, prazo de justificativa, cidade sede padrao, coordenador administrativo de PT e numeracao auxiliar de PT); usada para documentos futuros.
- `AssinaturaConfiguracao`: assinante preferencial por **tipo de documento** (oficio, justificativa, plano de trabalho, ordem de servico, termo), apontando para `Servidor`, com ordem por tipo e `ativo` tecnico; nao e assinatura digital, apenas configuracao.

## Regras obrigatorias

- Nao existe cadastro de `Motorista`; motoristas de viatura sao apenas `Servidor` selecionados no relacionamento da viatura.
- `Servidor` nao possui matricula.
- `Viatura` nao possui marca nem unidade.
- Cadastros nao possuem ativo/inativo.
- Exclusao e fisica.
- Quando existir vinculo relevante, exclusao deve ser bloqueada com mensagem clara.

Mensagem padrao de bloqueio:

```text
Não foi possível excluir este cadastro porque ele está vinculado a outros registros.
```

## Mascaras visuais

- CPF: `000.000.000-00` (armazenado em digitos; banco limpo).
- RG: `00.000.000-0` ou exibicao de “nao possui” quando `sem_rg` (armazenado normalizado / valor canonico).
- Telefone: `(00) 00000-0000` na tela; armazenado em digitos.
- CEP: `00000-000` na configuracao; armazenado em digitos.
- Placa: `AAA-1234` ou `AAA1A23` na tela; armazenada sem hifen e em maiusculo.

Logica central em `core/utils/masks.py`; JS em `static/js/components/masks.js` via `data-mask` (sem JS inline).

## Configuracoes e documentos

- A tela `/cadastros/configuracao/` e a fonte funcional de dados institucionais para geradores documentais futuros.
- `cidade_sede_padrao` nao deve ser digitada como texto livre: e resolvida por UF + cidade do endereco contra a base geografica interna.
- A consulta de CEP passa pela API interna autenticada `/cadastros/api/cep/<cep>/`; o front nao chama ViaCEP diretamente.
- Assinaturas configuradas sao apenas politica de assinantes por tipo documental. Assinatura digital, token publico, hash e validacao ficam para etapa futura.

## Cadastros publicos vs base interna

- **Estados e Cidades** permanecem como **base interna** (importacao/admin quando aplicavel); **nao** ha CRUD publico nem entradas no menu lateral para esses cadastros.

## Roteiros

`Roteiro` e uma entidade reutilizavel e avulsa. Ele pode existir sozinho e nao depende de Evento, Oficio, Plano de Trabalho nem Ordem de Servico.

Regras da base:

- roteiros poderao ser reutilizados futuramente por documentos e fluxos;
- Evento, quando existir, sera apenas agrupador opcional;
- nao existe ativo/inativo;
- exclusao futura sera fisica;
- se houver vinculo futuro com documentos, a exclusao devera ser bloqueada;
- origem e destino usam `Cidade` do app `cadastros`;
- cada `Cidade` pertence a um `Estado`;
- trechos pertencem ao roteiro;
- o roteiro **calcula diarias**; a regra esta na secao **Diarias** abaixo
  (a versao anterior deste documento dizia que nao havia calculo — ficou
  desatualizada e a correcao entrou com o `N-13`).

## Base geografica

- `Estado` e um cadastro proprio (nao e apenas texto solto de UF).
- Toda `Cidade` referencia um `Estado` (exclusao de estado com cidades vinculadas e bloqueada).
- Uma cidade pode ser marcada como `capital` (usado em regras futuras; capitais sao identificadas na importacao por mapa UF -> nome, com comparacao normalizada de texto).
- Roteiros usarao `Cidade` para origem e destino.
- Nao existe ativo/inativo para estado nem cidade.

## Diarias

O calculo de diarias e a regra financeira central do sistema: ele decide quanto o
servidor recebe, e o numero vai para documento assinado. A referencia e o
**sistema oficial de solicitacao de diarias** — o que este sistema calcula tem de
bater com o demonstrativo dele, ao centavo. Tres demonstrativos reais estao
travados como teste em `roteiros/tests/test_diarias_limites_periodo.py`.

### Grupos tarifarios

Todo destino cai em um de tres grupos, por `classify()`:

- `INTERIOR` — demais municipios;
- `CAPITAL` — capitais de estado;
- `BRASILIA` — Brasilia/DF, com valor proprio.

### Valores e vigencia

- Os valores ficam em `cadastros.TabelaDiaria`, **nao no codigo**. Cada linha e
  uma faixa com data de inicio de vigencia (`N-01`).
- So o **valor de 24 horas** e digitado. Os de **15%** e **30%** sao derivados no
  `save()` do modelo, com `ROUND_HALF_UP` em duas casas. O formulario nao os
  expoe, e um POST que tente grava-los e ignorado.
- A vigencia que vale para um roteiro e decidida pela **saida mais antiga** dele,
  uma vez por calculo. Resolver por trecho faria um roteiro que atravessa a
  virada de vigencia cobrar dois valores na mesma viagem.
- Mudar a tabela **nao recalcula o passado**: roteiro anterior a uma vigencia
  nova continua com o valor da epoca.
- Sem vigencia cadastrada para a data, o calculo cai na tabela historica
  (`TABELA_DIARIAS_HISTORICA`) em vez de falhar. Roteiro anterior a primeira
  vigencia e situacao de dados, nao de codigo.

### Onde cada periodo comeca e termina

O periodo de um destino vai da **chegada nele** ate a **chegada no destino
seguinte** — nao de uma saida a outra (`NOVO-11`). Duas excecoes:

- o **primeiro** periodo comeca na saida da sede, porque a ida ja e faturada no
  destino para onde se vai;
- o trecho final de **volta a sede** nao gera periodo proprio: a chegada dele
  apenas fecha o periodo anterior. Sem isso, o dia da volta seria faturado na
  tarifa da propria sede.

Consequencia pratica: o tempo de estrada entre dois destinos e faturado na tarifa
de **onde o servidor estava**. Com limites por saida esse tempo caia no trecho de
retorno e sumia da conta — o sistema pagava a menor.

### Trecho tarifario

**Periodos consecutivos do mesmo grupo formam um trecho so** (`N-05`). Tres
capitais seguidas viram um trecho unico; um interior no meio quebra a sequencia e
abre trecho novo.

Cada trecho e faturado como:

```
dias inteiros (por duracao) x valor de 24h  +  no maximo UM complemento
```

O complemento sai da sobra do trecho, nao da viagem inteira nem de cada destino:

| sobra do trecho | complemento |
|---|---|
| ate 6 horas | nenhum |
| mais de 6 ate 8 horas | 15% |
| mais de 8 horas | 30% |

Isso importa porque sobras pequenas **somam dentro do trecho**: tres permanencias
com 6h, 2h e 0h de sobra nao gerariam complemento isoladas, mas fundidas dao 8h e
valem 15%.

### Uma pendencia conhecida

`_segment_breakdown` conta dias por **duracao**, com uma excecao por calendario:
um periodo que cruza a meia-noite e dura menos de 24h vira diaria inteira. Dois
minutos entre 23:59 e 00:01 rendem uma diaria; quatorze horas dentro do mesmo dia
rendem 30%. Esta caracterizada por teste e **nao corrigida** (`N-08` / `N-10`):
depende do demonstrativo oficial de um roteiro que atravesse a madrugada.

### Valor efetivamente recebido

O valor calculado e o **liberado**. O que o servidor recebe pode ser menor — no
saque o caixa nao entrega centavos, entao de R$ 87,17 liberados ele saca R$ 87,00.

- `PrestacaoServidor.diaria_valor_override` guarda o valor recebido, como
  `DecimalField`, e vale para o relatorio tecnico daquele servidor.
- A regra dura: **nunca maior que o liberado** (`NOVO-10`). Menor, sim.
- A anotacao que explica a diferenca ("(saque)") tem campo proprio; no documento
  os dois voltam a ser uma string so.
- A validacao vale nos **dois** caminhos de gravacao (autosave e POST sem JS),
  pelo mesmo servico.

### O que nao existe

- A decomposicao **hospedagem 70% / alimentacao 30%** do sistema oficial nao e
  implementada: la ela existe para permitir declarar "Sem Hospedagem" e reduzir o
  valor, e o oficio nunca pede menos do que o servidor tem direito. Com as
  condicoes padrao o total bate igual (`NOVO-12`, escopo fechado por decisao).
- Nao ha congelamento do valor no documento emitido. O historico e preservado
  porque a vigencia e resolvida pela data de saida, nao porque o valor esteja
  gravado. Enquanto a tabela so crescer com vigencias novas o efeito e o mesmo;
  editar uma vigencia ja usada recalcularia o passado.

## Numeracao de documentos

Cada documento numera de um jeito diferente. Isto e descricao do que existe, nao
recomendacao — unificar e trabalho futuro.

| Documento | Estrategia | Unicidade |
|---|---|---|
| Oficio | reaproveita a **menor lacuna** liberada por exclusao; sem lacuna, maior numero + 1 | `area + ano + numero` |
| Plano de Trabalho | contador em `ConfiguracaoSistema` (`pt_ultimo_numero`, `pt_ano`), reconciliado com o maior numero do banco, sob `select_for_update` | `area + ano + numero` |
| Ordem de Servico | maior numero + 1 | `area + ano + numero` |
| Justificativa, Termo | **nao numeram**: herdam o numero do oficio de origem | — |

Pontos que valem atencao:

- o numero e reservado **na criacao**, inclusive para rascunho — nao espera o
  documento ser gerado. A unicidade e condicional a `numero` e `ano`
  preenchidos, entao `numero` nulo existe apenas de forma transitoria;
- a reserva do numero do oficio roda em **laco de ate 3 tentativas** com
  savepoint proprio: duas requisicoes simultaneas podem escolher o mesmo numero,
  e quem perde a corrida recalcula em vez de derrubar a transacao externa;
- numeros **pulados manualmente** (nunca ocupados) nao voltam como sugestao — so
  numeros que chegaram a ser usados e foram liberados por exclusao, via
  `OficioNumeroLacuna`;
- o contador do Plano de Trabalho **zera na virada do ano** e aceita um sufixo
  configuravel (`pt_sufixo_numero`);
- toda numeracao e **por area de trabalho**: duas areas tem sequencias
  independentes.

## Status por documento

Nao existe um vocabulario unico de status. Cada fluxo tem o seu:

| Entidade | Status |
|---|---|
| `Oficio` | Rascunho · Gerado · Finalizado *(legado)* · Arquivado |
| `Roteiro` | Rascunho · Finalizado |
| `Roteiro` (rota calculada) | Pendente · Calculada · Manual · Erro · Desatualizada |
| `Justificativa` | Rascunho · Finalizada |
| `PlanoTrabalho` | Rascunho · Gerado |
| `Evento` | Rascunho · Em preparacao · Documentos gerados · Em execucao · Finalizado · Cancelado |
| `PrestacaoContas` / `PrestacaoServidor` | Pendente · Em preenchimento · Enviada · Aprovada · Reprovada |
| `AssinaturaDocumento` | Pendente · Assinada · Cancelada |

Observacoes:

- `Oficio.STATUS_FINALIZADO` esta marcado como **legado** no proprio codigo;
- em Prestacoes, `arquivada` e `finalizada` sao **flags separadas** do campo
  `status`, e os endpoints que as alteram sao **alternadores**: o mesmo POST
  arquiva e desarquiva. Um duplo envio desfaz a acao;
- finalizar uma prestacao **nao exige pre-condicao** — nao pede comprovante,
  relatorio tecnico nem numero de solicitacao. E decisao do operador, e esta
  travado por teste para que mudar isso seja escolha explicita.
