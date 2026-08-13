# Mapa funcional do Ofício no Legacy 2.0

## 1. Visão geral

No Legacy 2.0, o Ofício não era um CRUD isolado. Ele operava como parte de um fluxo maior em `eventos`, com:
- fluxo guiado por etapas históricas;
- wizard próprio do ofício em 4 telas;
- acoplamento com `Evento`, `RoteiroEvento`, viajantes, viatura, motorista e trechos;
- documentos derivados (Ofício, Justificativa, Termo, Plano de Trabalho, Ordem de Serviço) com DOCX/PDF;
- validações documentais e de completude distribuídas em model, form, views e JS.

Arquiteturalmente, o legado tinha avanços (services documentais e context builders), mas com concentração excessiva em `eventos/views.py` e forte acoplamento entre telas, modelo e geração documental.

## 2. Arquivos envolvidos

| Área | Arquivo | Responsabilidade | Observações |
|---|---|---|---|
| Modelos de domínio | `legacy/central de viagens 2.0/eventos/models.py` | Define `Oficio`, `OficioTrecho`, `Justificativa`, `TermoAutorizacao`, `PlanoTrabalho`, `OrdemServico`, `RoteiroEvento` e vínculos | Núcleo funcional real do legado |
| Formulários | `legacy/central de viagens 2.0/eventos/forms.py` | Forms do wizard do ofício e formulários de documentos derivados | Arquivo monolítico |
| Views principais | `legacy/central de viagens 2.0/eventos/views.py` | Fluxo guiado + wizard do ofício + downloads documentais | Muito acoplado e extenso |
| Views globais | `legacy/central de viagens 2.0/eventos/views_global.py` | Listagens globais e CRUD de PT/OS/Termos/Justificativas | Interdependência com Ofício |
| URLs | `legacy/central de viagens 2.0/eventos/urls.py` | Mapa de rotas guiadas, wizard e download de docs | Rotas históricas com nomenclatura cruzada |
| Admin | `legacy/central de viagens 2.0/eventos/admin.py` | Exposição administrativa de modelos documentais | Suporte operacional |
| Serviços docs | `legacy/central de viagens 2.0/eventos/services/documentos/*` | Tipos, validação, contexto, render DOCX/PDF, nomes de arquivo | Base mais próxima do núcleo 3.0 |
| Serviços de regra | `legacy/central de viagens 2.0/eventos/services/diarias.py`, `justificativa.py`, `oficio_schema.py` | Cálculo de diárias, prazo de justificativa, schema/estado | Regras chave para migração |
| Templates wizard | `legacy/central de viagens 2.0/templates/eventos/oficio/*` | Etapas do wizard e resumo | UI fortemente orientada a “steps” |
| Templates guiados | `legacy/central de viagens 2.0/templates/eventos/guiado/*` | Fluxo guiado do evento com etapa histórica de ofícios | Acoplamento com evento |
| Templates docs | `legacy/central de viagens 2.0/templates/eventos/documentos/*` | CRUD e telas de PT/OS/Termos/Justificativas | Dependência indireta de dados do ofício |
| Templates DOCX | `legacy/central de viagens 2.0/eventos/resources/documentos/*.docx` | Modelos versionados para Ofício/Termo/PT/OS/Justificativa | Placeholders e pós-processamento |
| JS ofício | `legacy/central de viagens 2.0/static/js/oficio_wizard.js` | Sticky header, painel de resumo, autosave, máscaras e sincronização UI | Reescrita obrigatória no 3.0 |
| JS listagem | `legacy/central de viagens 2.0/static/js/oficios_list.js` | Modo rich/basic e autosubmit de filtros | Pode inspirar UX, sem copiar |
| JS termos | `legacy/central de viagens 2.0/static/js/termos_autorizacao.js` | Autocomplete, preview contextual, inferência de modalidade | Regras úteis para fase de termos |
| Base institucional | `legacy/central de viagens 2.0/cadastros/models.py` | `ConfiguracaoSistema` e `AssinaturaConfiguracao` | Dependência documental transversal |
| Máscaras/protocolo | `legacy/central de viagens 2.0/core/utils/masks.py` | Normalização/formatação de protocolo, CPF, RG etc. | Protocolo central para regras |

## 3. Models envolvidos

Modelos identificados como essenciais ao fluxo legado de Ofícios:

- `Oficio` (`eventos/models.py`)
  - Campos: número/ano/protocolo/data/status, tipo origem, custeio, assunto, motivo, dados de motorista/viatura, diárias, retorno, vínculo com `Evento` e `RoteiroEvento`.
  - Relacionamentos: M2M com viajantes, FK com veículo/motorista e autorreferência para carona.
  - Regras: `clean`/`save` normalizam protocolo, validam protocolo do motorista carona, validam custeio “outra instituição”, numeração anual com menor lacuna e retry transacional.
  - Uso: documento principal do módulo.

- `OficioTrecho` (`eventos/models.py`)
  - Campos: origem/destino, saída/chegada, distância, duração, tempo cru/adicional e fonte de rota.
  - Relacionamento: FK para `Oficio`.
  - Regras: ordenação e unicidade por `(oficio, ordem)`.
  - Uso: deslocamento de ida; retorno fica no próprio `Oficio`.

- `RoteiroEvento` e `RoteiroEventoTrecho` (`eventos/models.py`)
  - Servem de fonte para pré-preenchimento de trecho, período e destino.
  - Uso: `Oficio.roteiro_evento` quando modo “usar roteiro salvo”.

- `Evento` e `EventoParticipante` (`eventos/models.py`)
  - Ofício podia ser vinculado a evento e herdava contexto de período/destinos/equipe.
  - Uso: base do fluxo guiado histórico.

- `Justificativa` (`eventos/models.py`)
  - Relação 1:1 com ofício (nullable em fases finais do legado).
  - Uso: regra de prazo (< X dias) e documento derivado.

- `TermoAutorizacao` (`eventos/models.py`)
  - Suporta modo rápido e automático (com/sem viatura), snapshots de servidor/viatura e lote.
  - Uso: geração por participante e por contexto de ofícios/evento.

- `PlanoTrabalho` (`eventos/models.py`)
  - Documento independente, com vínculo opcional a evento/ofício(s)/roteiro.
  - Uso: documento derivado alimentado por contexto do ofício.

- `OrdemServico` (`eventos/models.py`)
  - Documento independente com vínculo opcional a evento/ofício e M2M de viajantes.
  - Uso: geração com equipe e deslocamento.

- `ConfiguracaoSistema` e `AssinaturaConfiguracao` (`cadastros/models.py`)
  - Fornecem contexto institucional e assinaturas por tipo documental.
  - Uso: obrigatório para renderização documental consistente.

## 4. Forms envolvidos

Forms relevantes no legado:

- `OficioStep1Form` (`eventos/forms.py`)
  - Dados gerais do ofício, equipe e regras iniciais de custeio/assunto/motivo.
  - Dependências de JS para preenchimento e visualização de resumo.

- `OficioStep2Form` e `LegacyOficioStep2Form` (`eventos/forms.py`)
  - Transporte, motorista, viatura, carona e protocolos relacionados.
  - Integração com buscas/autocomplete de viatura e motorista.

- Fluxo de etapas documentais
  - `OficioJustificativaForm`, `JustificativaForm`, `TermoAutorizacaoForm`, `PlanoTrabalhoForm`, `OrdemServicoForm`.
  - Forte uso de campos hidden (`destinos_payload`, `roteiro_json`, IDs serializados) e sincronização por JS.

Regras recorrentes:
- normalização (maiúsculas, máscaras, protocolo);
- filtros de queryset por contexto de evento/ofício;
- validações condicionais de completude documental.

## 5. Views e URLs

| URL/rota | View | O que faz | Entrada | Saída | Dependências |
|---|---|---|---|---|---|
| `eventos/oficio/novo/` | `oficio_novo` | Cria rascunho de ofício e redireciona para fluxo | form inicial | redirect wizard | `Oficio`, forms |
| `eventos/oficio/<pk>/step1/` | `oficio_step1` | Dados gerais + equipe | POST step1/autosave | render/redirect | `OficioStep1Form`, viajantes API |
| `eventos/oficio/<pk>/step2/` | `oficio_step2` | Transporte/motorista/viatura | POST step2/autosave | render/redirect | APIs de motorista/veículo |
| `eventos/oficio/<pk>/step3/` | `oficio_step3` | Trechos, retorno, diárias | POST trechos | render/redirect | cálculo de diárias e trechos |
| `eventos/oficio/<pk>/step4/` | `oficio_step4` | Resumo final do ofício | GET/POST finalização | render/redirect | validação de completude |
| `eventos/oficio/<pk>/justificativa/` | `oficio_justificativa` | CRUD contextual da justificativa | form | render/redirect | `Justificativa` |
| `eventos/oficio/<pk>/documentos/` | `oficio_documentos` | Painel de status de documentos | GET | render | validators + backends |
| `eventos/oficio/<pk>/documentos/<tipo>/<formato>/` | `oficio_documento_download` | Gera DOCX/PDF | parâmetros de tipo/formato | download/erro | renderer + template + validação |
| `eventos/<evento_id>/guiado/etapa-5/` | `guiado_etapa_3` (histórico) | Etapa de Ofícios dentro do fluxo guiado | contexto evento | render | evento + lista ofícios |
| `eventos/oficios/` | `oficio_global_lista` | Lista global de ofícios | filtros | listagem | card/meta documental |

## 6. Services e funções auxiliares

Principais serviços auditados:

- `eventos/services/documentos/types.py`
  - Catálogo de tipos/formato documental (`DocumentoOficioTipo`, `DocumentoFormato`).
  - Migrar: sim.
  - Destino 3.0: `documentos/services/types.py` (já iniciado).

- `eventos/services/documentos/validators.py`
  - Verifica prontidão documental por tipo (status available/pending/unavailable), assinatura/configuração e consistência de dados.
  - Migrar: sim.
  - Destino 3.0: `documentos/services/validators.py` + validações por domínio (`oficios/services.py`).

- `eventos/services/documentos/context.py`
  - Constrói payload rico para Ofício/Justificativa/Termo/PT/OS, incluindo institucional, trechos, retorno e diárias.
  - Migrar: sim (com desacoplamento).
  - Destino 3.0: service de montagem de payload por app + contratos no núcleo.

- `eventos/services/documentos/renderer.py`
  - Resolve template DOCX, substitui placeholders, converte para PDF e trata disponibilidade de backend.
  - Migrar: parcialmente (conceitos).
  - Destino 3.0: `documentos/services/renderers`, `templates`, `placeholders`, `responses`.

- `eventos/services/documentos/filenames.py`
  - Padrão de nome de arquivo por tipo e identificador do ofício.
  - Migrar: sim.
  - Destino 3.0: `documentos/services/filenames.py` (já existe).

- `eventos/services/diarias.py`, `justificativa.py`, `oficio_schema.py`
  - Regras de negócio funcionais (período, destino, prazo de justificativa e schema de prontidão).
  - Migrar: sim.
  - Destino 3.0: `oficios/services.py` + apps documentais derivados.

## 7. Templates e UI

Telas mapeadas no legado:
- listagem global de ofícios (`templates/eventos/global/oficios_lista.html`);
- wizard ofício (`templates/eventos/oficio/wizard_step1.html` ... `wizard_step4.html`);
- justificativa contextual (`templates/eventos/oficio/justificativa.html`);
- painel documental e ações de download;
- fluxo guiado histórico de evento (`templates/eventos/guiado/etapa_5.html`) com ofícios;
- listas e CRUD de documentos derivados (termos, justificativas, plano de trabalho, ordem de serviço).

Padrão observado:
- muitos blocos de resumo e preview;
- acoplamento de estado de tela com scripts;
- dependência de sequência guiada para operação completa.

## 8. JS

Scripts relevantes:

- `static/js/oficio_wizard.js`
  - Funções: autosave por debounce + beacon, atualização de resumo lateral, máscara de protocolo, controle de painel.
  - Eventos: `input`, `change`, `submit`, `pagehide`, `visibilitychange`, clique em links com autosave.
  - Reescrever no 3.0: sim (por página/componente, sem acoplamento legado).

- `static/js/oficios_list.js`
  - Funções: alternância de modo de listagem (rich/basic), persistência em `localStorage`, filtros com autosubmit.
  - Reescrever no 3.0: opcional, como melhoria de UX.

- `static/js/termos_autorizacao.js`
  - Funções: autocomplete de viajantes/viaturas, inferência de modalidade, preview por evento/ofícios, chips de seleção, destinos dinâmicos.
  - Reescrever no 3.0: sim, quando fase de termos for iniciada.

## 9. Documentos DOCX/PDF

Mapeamento documental legado:

- Templates DOCX:
  - `oficio_model.docx`
  - `modelo_justificativa.docx`
  - `termo_autorizacao.docx`
  - `termo_autorizacao_automatico.docx`
  - `termo_autorizacao_automatico_sem_viatura.docx`
  - `modelo_plano_de_trabalho.docx`
  - `modelo_ordem_servico.docx`

- Placeholders:
  - extração por regex `{% raw %}{{ ... }}{% endraw %}`;
  - substituição inclusive em runs fragmentados;
  - fallback para vazio quando chave ausente.

- Geração:
  - validação por tipo e disponibilidade de template/backend;
  - DOCX via `python-docx`/template;
  - PDF via `docx2pdf` com fallback COM/Word no Windows.

- Erros e fallback:
  - `DocumentValidationError`, `DocumentTemplateUnavailable`, `DocumentRendererUnavailable`;
  - PDF pode falhar por ambiente (Word/COM, bibliotecas), com mensagens explícitas.

## 10. Regras de negócio

| ID | Regra | Onde está no legacy | Como adaptar no 3.0 | Prioridade |
|---|---|---|---|---|
| R-OF-001 | Numeração anual automática com concorrência | `eventos/models.py` (`Oficio.save`) | service transacional no app `oficios` | Alta |
| R-OF-002 | Protocolo normalizado e formatado | `eventos/models.py`, `core/utils/masks.py` | normalizer + validação de form/model | Alta |
| R-OF-003 | Custeio “outra instituição” exige nome | `Oficio.clean` | manter em `OficioForm.clean` e service | Alta |
| R-OF-004 | Motorista carona exige protocolo específico | `Oficio.clean` | modelar regra em fase equipe/transporte | Média |
| R-OF-005 | Assunto autorização vs convalidação por data de saída | `Oficio.compute_assunto_tipo` | presenter/service de assunto derivado | Média |
| R-OF-006 | Ofício usa roteiro salvo ou próprio | `Oficio.roteiro_modo` + views/forms | manter roteiro opcional no 3.0 com modo explícito | Alta |
| R-OF-007 | Trechos de ida separados de retorno | `OficioTrecho` + campos retorno no `Oficio` | criar entidade de trecho no 3.0 + bloco retorno | Alta |
| R-OF-008 | Diárias derivadas de período/trechos | `services/diarias.py`, `views.py` | service dedicado no 3.0 (`oficios/services`) | Alta |
| R-OF-009 | Justificativa obrigatória por prazo | `services/justificativa.py` | app `justificativas` vinculado ao ofício | Alta |
| R-OF-010 | Geração de termo por servidor/modo | `TermoAutorizacao`, `services/documentos/termo_autorizacao.py` | app `termos` com payload por servidor | Alta |
| R-OF-011 | PT e OS derivados de contexto de ofício/evento | models + views_global + services docs | apps independentes com vínculos opcionais | Média |
| R-OF-012 | Documento só gera se validações estiverem OK | `validators.py` | manter no núcleo + validações de domínio | Alta |
| R-OF-013 | Placeholders não resolvidos não podem passar | `renderer.py` | manter contrato no núcleo 3.0 | Alta |
| R-OF-014 | Nome de arquivo padronizado por tipo/formato | `filenames.py` | manter builder único em `documentos/services` | Média |
| R-OF-015 | Exclusão bloqueada por vínculos | FKs e regras de exclusão | manter com mensagens consistentes | Média |
| R-OF-016 | Autosave em formulários longos | `static/js/oficio_wizard.js` | reimplementar de forma desacoplada | Média |

## 11. O que NÃO deve ser migrado igual

- acoplamento obrigatório de Ofício ao `Evento`;
- views gigantes em `eventos/views.py` e `views_global.py`;
- lógica de negócio em templates/JS sem camada de serviço clara;
- dependência estrutural de fluxo guiado como único caminho;
- nomenclatura histórica de etapas no novo sistema;
- regras documentais espalhadas em múltiplos pontos sem contrato único;
- qualquer import runtime de `legacy/`.

## 12. Adaptação document-centric para o 3.0

Diretriz de migração:

- Ofício como agregado principal e independente (com `Roteiro` opcional).
- Evento como vínculo opcional futuro (não obrigatório para operar o ofício).
- Documentos derivados (`Justificativa`, `Termo`, `Plano`, `OS`) como apps independentes com vínculo por FK/M2M ao ofício.
- Núcleo documental (`documentos/services`) como contrato único para:
  - tipo/formato;
  - template;
  - placeholders;
  - validação;
  - renderização;
  - resposta/download.
- Regras funcionais no domínio (`oficios/services.py`, selectors, presenters), sem empurrar regra para template.

