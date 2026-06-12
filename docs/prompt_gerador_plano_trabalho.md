# PROMPT — Gerador de Plano de Trabalho (wizard completo + DOCX/PDF)

> Cole esta prompt inteira numa sessão do Claude Code aberta na raiz do projeto
> `Gerenciador de Viagens`. Ela é autossuficiente: o modelo DOCX e os exemplos
> prontos estão versionados em `docs/modelos/`.

---

Implemente o módulo completo de **Plano de Trabalho** no app `planos_trabalho` (hoje é só um
placeholder com `index.html`). A regra de ouro: **nada é criado do zero** — todo formulário,
tela, service e padrão deve ser **clonado e remodelado** de código que já existe no sistema.
As fontes exatas de clone estão listadas em cada seção.

## 1. Contexto e artefatos de referência

- Projeto Django (PCPR / Assessoria de Comunicação Social). Apps relevantes: `oficios`
  (wizard de referência), `ordens_servico` (módulo documental independente de referência),
  `termos`, `roteiros` (motor de diárias), `cadastros`, `documentos` (núcleo de geração
  DOCX/PDF), `legacy/central de viagens 2.0` (sistema antigo, fonte de helpers para portar).
- **Modelo DOCX a usar**: `docs/modelos/plano_de_trabalho_modelo.docx` — placeholders
  **planos** estilo docxtpl (`{{numero_plano_trabalho}}`, `{{contextualizacao}}`, ...).
  Copie-o por cima do stub `documentos/resources/plano_trabalho.docx`.
- **Exemplos prontos do resultado esperado**: `docs/modelos/plano_trabalho_exemplo_maringa.pdf`
  (nº 20/2026) e `docs/modelos/plano_trabalho_exemplo_sarandi.pdf` (nº 18/2026). Leia os dois
  antes de começar — eles definem exatamente o texto final de cada seção.

## 2. Entidade `PlanoTrabalho` (novo model em `planos_trabalho/models.py`)

Clonar o estilo de `ordens_servico/models.py::OrdemServico` (TimeStampedModel, numero/ano,
`numero_formatado`, `periodo_display`, `destinos_display`).

Campos:
- `numero`, `ano` — numeração automática sequencial por ano usando os campos **que já
  existem** em `cadastros.models.ConfiguracaoSistema`: `pt_ultimo_numero` e `pt_ano`
  (incrementa atômico via `select_for_update`/`F()`; se `pt_ano` ≠ ano corrente, zera o
  contador). Número editável manualmente depois (constraint unique `(ano, numero)` como em
  `Oficio`).
- `numero_formatado` → `"20/2026/ASCOM"`. O sufixo (`ASCOM`) vem de um novo campo
  `pt_sufixo_numero` na `ConfiguracaoSistema` (CharField, default `"ASCOM"`, editável na tela
  de configuração existente em `cadastros`).
- `status` RASCUNHO/GERADO (clone do padrão `Oficio.STATUS_CHOICES`, sem os legados).
- Etapa 1: `contextualizacao` (TextField), `programa` (FK para novo cadastro
  `ProgramaSolicitante`, ver §7) + `programa_outros` (CharField), `destino_estado`/
  `destino_cidade` (FKs **clonadas de `termos/models.py::TermoAutorizacao`**),
  `data_evento_inicio`/`data_evento_fim` (DateFields, idem termos),
  `horario_atendimento` (CharField, default `"09:00 até 17:00"`),
  `consideracao_final` (TextField), coordenadores (ver §4).
- Etapa 2: `saida_sede_data`, `saida_sede_hora`, `chegada_sede_data`, `chegada_sede_hora`
  (DateField/TimeField separados — 4 inputs simples) + snapshot do cálculo:
  `diarias_composicao` (ex. `"4 x 100% + 1 x 15%"`), `diarias_valor_unitario` (Decimal, por
  servidor), `diarias_valor_total` (Decimal), extensos NÃO se persistem (gerar na hora).
- Etapa 3 (placeholder, ver §5): `metas`, `atividades`, `recursos_necessarios`,
  `unidade_movel_texto` (TextFields blank — ficam vazios por enquanto, mas o documento já
  renderiza os placeholders).
- Efetivo por cargo: model filho `EfetivoPlano(plano FK, cargo FK cadastros.Cargo,
  quantidade PositiveInteger)` com unique `(plano, cargo)` — clone direto do legado
  `legacy/central de viagens 2.0/eventos/models.py::EfetivoPlanoTrabalhoDocumento`.

## 3. Wizard de 4 etapas (clone do wizard de ofícios)

Clonar o **shell inteiro** do wizard de ofícios: helpers `_wizard_shell_ctx`,
`_wizard_steps_ctx`, `_wizard_footer_ctx`, `_wizard_normalizar_acao` em `oficios/views.py`;
templates `templates/oficios/wizard_base.html`, `partials/wizard_stepper.html`,
`partials/wizard_actions.html`, `partials/wizard_summary.html`; padrão de **autosave** por
etapa (`dados_viajantes_autosave`, `transporte_autosave`, `justificativa_autosave` +
`_autosave_form_errors`, versionamento `_oficio_autosave_version`); padrão de URLs de
`oficios/urls.py`. Criar os equivalentes em `planos_trabalho/` com `app_name="planos_trabalho"`.

**Etapa 1 — Identificação & Atuação**
- Contextualização: textarea **pré-preenchido** com o texto padrão (hardcoded em
  `planos_trabalho/services.py` ou módulo de textos), com `{municipio}` e `{programa}`
  já substituídos ao criar o plano (re-sugerir se destino/programa mudarem e o usuário não
  tiver editado — comportamento análogo ao prefill da justificativa do ofício):

  > A Assessoria de Comunicação Social da Polícia Civil do Paraná (PCPR), no âmbito do
  > programa "PCPR na Comunidade", promoverá ação itinerante no município de {municipio}.
  >
  > A iniciativa visa atender à solicitação formulada pelo {programa} (Ofício em anexo),
  > levando serviços essenciais de polícia judiciária às populações urbanas, rurais e
  > ribeirinhas, especialmente em localidades de difícil acesso.
  >
  > A ação tem como foco principal garantir o acesso à documentação básica e prestar
  > orientações de polícia judiciária, promovendo cidadania e fortalecendo a aproximação
  > institucional com a comunidade.

- Programa solicitante: select do cadastro `ProgramaSolicitante` (§7) + campo "outros".
- Destino: UF + Cidade — **clonar o form/template do cadastro de termos**
  (`termos/forms.py` + `templates/termos/form.html`: selects encadeados estado→cidade).
- Data inicial/final do evento: clonar os DateFields do mesmo form de termos.
- Horário de atendimento: input texto, default `09:00 até 17:00`.
- Coordenadores (§4).
- Considerações finais: textarea pré-preenchido (mesma mecânica da contextualização):

  > A realização da ação no município de {municipio} reforça o compromisso institucional da
  > Polícia Civil do Paraná com a promoção da cidadania e com a ampliação do acesso a
  > serviços públicos essenciais, especialmente em regiões com limitações de deslocamento e
  > maior vulnerabilidade social.

**Etapa 2 — Efetivo & Diárias**
- Efetivo por cargo: linhas dinâmicas Cargo (FK `cadastros.Cargo`) × Quantidade (formset,
  adicionar/remover linha — reaproveitar o padrão de linhas dinâmicas que já existe no
  wizard de ofícios/roteiro). Total de servidores = soma das quantidades.
- Diárias — **apenas 4 inputs**: data de saída da sede, hora de saída, data de chegada na
  sede, hora de chegada. O cálculo usa o **motor que já existe**
  `roteiros/services/diarias.py`:
  - `calculate_periodized_diarias(markers, chegada_final_sede, quantidade_servidores=total_efetivo, sede_cidade=..., sede_uf=...)`
    com **um único** `PeriodMarker(saida=datetime(saida_data+hora), destino_cidade=<cidade
    etapa 1>, destino_uf=<UF etapa 1>)` e `chegada_final_sede=datetime(chegada_data+hora)`.
  - Sede: `ConfiguracaoSistema.cidade_sede_padrao`.
  - Do retorno usar: `totais.diarias_por_servidor` (composição "N x 100% + M x 15/30%"),
    `totais.valor_por_servidor_decimal` (valor unitário por servidor),
    `totais.total_valor_decimal` (total), `valor_por_extenso_ptbr` para os extensos.
  - Validação contra os exemplos: destino interior, 4 pernoites + parcial 15% →
    R$ 1.205,78/servidor × 6 = R$ 7.234,68 (Maringá); 5 pernoites + 30% →
    R$ 1.539,92 × 18 = R$ 27.718,56 (Sarandi).
  - Exibir o resultado em card de resumo na própria etapa (recalcular via autosave/endpoint
    ao mudar inputs — clone do padrão `api_viatura_por_placa`/autosave do ofício) e
    persistir o snapshot nos campos do model.

**Etapa 3 — Atividades, Metas & Recursos (PLACEHOLDER)**
- NÃO implementar a lógica agora (atividades/metas/recursos são interligados e terão um
  trabalho dedicado depois). Entregar apenas a página da etapa no shell do wizard com **um
  card com footer** marcando o espaço ("Atividades, Metas e Recursos — em desenvolvimento"),
  usando os componentes de card existentes em `templates/components/cards/`. A navegação
  (voltar/continuar) deve funcionar normalmente.
- Os TextFields do model já existem (§2) para o documento renderizar; nos placeholders do
  DOCX eles saem vazios ("" — não usar "—" para não sujar o documento final).

**Etapa 4 — Resumo & Documentos**
- Clone de `oficios/views.py::wizard_documentos` + `templates/oficios/wizard_documentos.html`:
  resumo dos dados + **preview PDF inline** (clonar `_pdf_inline_response` /
  `plano_trabalho_pdf_inline` e o streaming de `documentos/services/pdf_streaming.py`) +
  botões de download DOCX e PDF.
- Ao gerar, status RASCUNHO → GERADO (padrão do ofício).

## 4. Coordenadores (etapa 1)

Dois blocos, ambos com o **modo dual servidor/manual clonado do motorista do ofício**
(`Oficio.motorista_modo` SERVIDOR/MANUAL + `templates/oficios/partials/_motorista_modo_toggle.html`
e `wizard_dados_card_motorista_externo.html`):

- **Coordenador administrativo** — sempre presente. Modo SERVIDOR: select de
  `cadastros.Servidor` com default `ConfiguracaoSistema.coordenador_adm_plano_trabalho`
  (campo já existe). Modo MANUAL: inputs nome + cargo.
- **Coordenador operacional** — opcional, mesmo padrão dual. Totalmente em branco = não
  existe (nenhum texto gerado).

Texto de `{{coordenacao}}` gerado no contexto do documento (não precisa ser editável):

> Fica designado(a) como Coordenador(a) Administrativo(a) do Plano o(a) {cargo} {nome}, o(a)
> qual ficará responsável pelo acompanhamento da execução administrativa do presente Plano
> de Trabalho, organização das escalas de servidores, controle de materiais e equipamentos,
> consolidação de dados estatísticos, elaboração de relatório final e demais providências
> necessárias ao regular cumprimento da ação.

Se houver coordenador operacional, acrescentar parágrafo análogo ("Coordenador(a)
Operacional do Evento ... responsável pela execução operacional da ação no local do
evento."). Cargo/nome vêm do Servidor selecionado ou dos campos manuais.

## 5. Geração DOCX/PDF

- Substituir `documentos/resources/plano_trabalho.docx` (stub) por
  `docs/modelos/plano_de_trabalho_modelo.docx`.
- O registro do tipo já existe: `DocumentoTipo.PLANO_TRABALHO` em
  `documentos/services/registry.py` — manter.
- Criar `planos_trabalho/docxtpl_context.py` (clone de `ordens_servico/docxtpl_context.py`):
  contexto **plano** com as chaves abaixo. Reescrever `planos_trabalho/services.py` no padrão
  de `ordens_servico/services.py::gerar_os_docx_response` (DOCX) e do atual
  `planos_trabalho/services.py` (PDF via `build_default_facade` + cache + `persist_geracao`),
  **mas recebendo `PlanoTrabalho`, não `Oficio`** (a persistência aceita
  `payload_snapshot`; adaptar `oficio_id` para nullable/genérico se necessário, seguindo o
  que `DocumentoArtefato` suportar).

Mapeamento placeholder → fonte (exemplos da versão Maringá):

| Placeholder | Fonte | Exemplo |
|---|---|---|
| `{{numero_plano_trabalho}}` | `numero_formatado` | `20/2026/ASCOM` |
| `{{unidade}}` | `ConfiguracaoSistema.unidade` (mesmo display do cabeçalho dos outros docs — ver `cadastros/selectors.py::build_configuracao_context`) | `ASSESSORIA DE COMUNICAÇÃO SOCIAL` |
| `{{contextualizacao}}` | textarea etapa 1 | texto padrão preenchido |
| `{{metas}}` | etapa 3 (vazio por enquanto) | — |
| `{{atividades}}` | etapa 3 (vazio por enquanto) | — |
| `{{data_evento}}` | período por extenso — **portar** `_format_periodo_evento_extenso` de `legacy/central de viagens 2.0/eventos/services/documentos/plano_trabalho.py` | `25 a 27 de junho de 2026` |
| `{{destinos}}` | `destino_cidade.nome/UF` | `Maringá/PR` |
| `{{horario_de_atendimento}}` | campo etapa 1 | `09:00 até 17:00` |
| `{{efetivos}}` | texto por cargo — **portar** `_build_efetivo_por_cargo_texto` do mesmo arquivo legado | `6 Policiais Civis` / `4 investigadores, 2 papiloscopistas` |
| `{{unidade_movel}}` | `unidade_movel_texto` (vazio por enquanto) | — |
| `{{valor_do_plano}}` | bloco montado com o motor de diárias: `Valor total: R$ {total} ({total extenso}). Valor correspondente a {composição}, por servidor, no valor unitário de R$ {unitário} ({unitário extenso}).` — extensos via `roteiros/services/valor_extenso.py::valor_por_extenso_ptbr`, formato moeda via `formatar_valor_diarias` | ver PDF exemplo §5 |
| `{{recursos_necessarios}}` | etapa 3 (vazio por enquanto) | — |
| `{{coordenacao}}` | texto(s) de designação (§4) | ver PDF exemplo §7 |
| `{{consideracao_final}}` | textarea etapa 1 | texto padrão preenchido |
| `{{sede}}` | `ConfiguracaoSistema.sede` | `Curitiba/PR` |
| `{{data_extenso}}` | data atual por extenso — reusar formatter existente (`documentos/services/formatters.py` ou portar `_format_data_extenso` do legado) | `25 de maio de 2026` |
| `{{nome_chefia}}` / `{{cargo_chefia}}` | `ConfiguracaoSistema.nome_chefia` / `cargo_chefia` (fallback `AssinaturaConfiguracao` tipo PLANO_TRABALHO, como o legado fazia) | `João Mário Nunes de Góes` / `Assessor de Comunicação Social` |

## 6. Remover o Plano de Trabalho do wizard de OFÍCIOS

O fluxo antigo (PT gerado a partir do `Oficio`) morre:
- Remover rotas em `oficios/urls.py`: `plano_trabalho_pdf_inline` e
  `baixar_plano_trabalho_documento`; remover as views correspondentes em `oficios/views.py`.
- Remover botões/cards de plano de trabalho em `templates/oficios/wizard_documentos.html`.
- Remover a função antiga `gerar_resposta_plano_trabalho_documento` baseada em `Oficio`
  (será substituída pela nova baseada em `PlanoTrabalho`).
- Ajustar/remover testes que referenciam essas rotas (procurar por `plano_trabalho` em
  `oficios/tests/` e `documentos/tests/`). O `em_elaboracao` de
  `oficios/documents.py::build_canonical_document_payload` deixa de tratar PLANO_TRABALHO.

## 7. Cadastro de Programas Solicitantes

CRUD pequeno clonado do CRUD de **modelos de motivo do ofício**
(`oficios/views.py::modelos_motivo_*`, `templates/oficios/modelos_motivo/*`,
`ModeloMotivoOficio`): model `ProgramaSolicitante(nome unique, ativo, ordem)`. Migration com
seed: `PROGRAMA PARANÁ EM AÇÃO`, `PROGRAMA JUSTIÇA NO BAIRRO`, `PCPR NA COMUNIDADE`.
Rotas dentro de `planos_trabalho/` (`/planos-trabalho/programas/...`).

## 8. Listagem (index)

Clonar `templates/oficios/index.html` + `templates/oficios/partials/oficio_list_card.html` →
`plano_list_card`: busca, filtro por status, card com número formatado, destino, período,
status badge e ações (continuar wizard, baixar DOCX/PDF quando GERADO, excluir com
confirmação — clonar `confirm_delete.html`). Substituir o `planos_trabalho/index.html`
placeholder. Manter o item de menu/navegação que já aponta para `planos_trabalho:index`.

## 9. Testes

Clonar os padrões de `oficios/tests/` (especialmente `test_wizard_dados_viajantes.py`,
`test_wizard_roteiro_diarias.py`, `test_views.py`) para:
- numeração sequencial com `pt_ultimo_numero`/`pt_ano` (inclusive virada de ano);
- cálculo de diárias da etapa 2 reproduzindo os dois exemplos reais
  (1.205,78×6=7.234,68 e 1.539,92×18=27.718,56, interior);
- coordenador dual servidor/manual e operacional em branco = sem texto;
- contexto docxtpl com todos os placeholders do §5 preenchidos;
- geração DOCX/PDF e preview inline;
- remoção das rotas antigas no ofício (404/ausência).

## 10. Ordem de execução sugerida

1. Model + migrations (PlanoTrabalho, EfetivoPlano, ProgramaSolicitante, campo
   `pt_sufixo_numero` na configuração) e numeração.
2. Shell do wizard (4 etapas navegáveis, etapa 3 só placeholder) + autosave.
3. Etapa 1 completa (forms clonados de termos + coordenadores duais + textos padrão).
4. Etapa 2 (efetivo por cargo + integração com motor de diárias + card de resultado).
5. Substituição do template DOCX + docxtpl_context + services de geração + etapa 4 com
   preview inline e downloads.
6. Remoção do PT do wizard de ofícios.
7. Index/listagem + CRUD de programas.
8. Testes + `python manage.py check` + rodar a suíte.

Valide o documento final gerando um plano com os dados do exemplo de Maringá e comparando
seção a seção com `docs/modelos/plano_trabalho_exemplo_maringa.pdf`.
