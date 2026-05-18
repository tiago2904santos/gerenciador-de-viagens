# Backlog de migração funcional do Ofício

## Fase 12.2 - Wizard de Ofício: Dados e viajantes

Itens:
- substituir o formulário único de cadastro por wizard inicial;
- criar header "Cadastro de ofício" com subtítulo da etapa atual;
- implementar stepper visual com estados `not_started`, `current`, `incomplete`, `complete` e `locked`;
- posicionar o stepper acoplado ao header, seguindo o padrão visual de Eventos;
- implementar a etapa 1 "Dados e viajantes";
- remover resumo lateral do cadastro;
- ajustar o cadastro para estrutura `background > section > div interna`;
- aproximar cards de listagem do padrão visual de Roteiros;
- gerar `numero`/`ano` automaticamente, com formato `01/2026` e reaproveitamento da menor lacuna anual;
- exigir assunto, motivo, custeio válido e ao menos um servidor para considerar a etapa concluída;
- manter transporte, roteiro/diárias, resumo final e documentos como etapas futuras bloqueadas.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 12.2 | Wizard de Ofício: Dados e viajantes | `oficios/models.py`, `oficios/forms.py`, `oficios/services.py`, `oficios/presenters.py`, `oficios/views.py`, `oficios/tests/*`, `templates/oficios/*`, `static/css/forms.css`, `static/css/cards.css`, `static/css/lists.css` | Sim | Médio | Wizard substitui formulário único, stepper visual tem estados e fica acoplado ao header, Etapa 1 funciona, resumo lateral removido, cards da listagem evoluídos, numeração anual automatizada, etapas futuras ficam bloqueadas, sem `href="#"` e sem CSS/JS inline |

## Fase 13 — Ofício: modelo operacional completo

Itens:
- ampliar campos faltantes (assunto derivado, tipo origem, dados de retorno e metadados documentais);
- incluir regras de protocolo/numeração/retificação;
- revisar status e transições;
- preparar snapshots mínimos para estabilidade documental.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 13 | Completar modelo operacional do ofício | `oficios/models.py`, `oficios/forms.py`, `oficios/services.py`, `oficios/tests/*` | Sim | Alto | Ofício contempla campos e regras mínimas legadas sem quebrar arquitetura |

### Atualização da fase 12.3 (concluída)
- Etapa 1 ajustada para "Dados e viajantes" com:
  - data de criação automática;
  - protocolo canônico (9 dígitos) e máscara `XX.XXX.XXX-X`;
  - status automático `RASCUNHO/GERADO`;
  - remoção de "Assunto e motivo" e de "Contexto operacional";
  - inclusão de `ModeloMotivoOficio` e seleção de modelo no form;
  - viajantes com filtro progressivo sem quebrar fallback de `<select multiple>`.

### Hotfix 12.3.1 (concluído)
- renderização inicial do wizard em `/oficios/novo/` com:
  - `N° do Ofício: Gerado automaticamente ao salvar.`
  - `Data criação: será definida automaticamente ao salvar`
  - `Status: Rascunho`
- exibição condicional de `custeio_observacao` por valor de `custeio`.
- criação do CRUD de modelos de motivo em `/oficios/modelos-motivo/`.

## Fase 14 — Ofício: equipe/viajantes

Itens:
- adicionar/remover servidores com regras consistentes;
- motorista e viatura com validações de vínculo;
- autofill de viatura/motorista por contexto;
- integração limpa com `cadastros`.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 14 | Consolidar equipe, motorista e viatura | `oficios/forms.py`, `oficios/services.py`, `oficios/selectors.py`, `templates/oficios/*`, `static/js/pages/*` | Talvez | Médio | Edição de equipe e transporte estável com validações e testes |

## Fase 15 — Ofício: roteiro e diárias

Itens:
- vínculo opcional com roteiro reutilizável;
- copiar dados de roteiro para estrutura documental do ofício;
- gerenciar trechos de ida e retorno;
- calcular diárias e preparar payload.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 15 | Integrar roteiro, trechos, retorno e diárias | `oficios/models.py`, `oficios/services.py`, `roteiros/services/*`, `oficios/tests/*` | Sim | Alto | Cálculo de diárias reproduz regras previstas e fluxo permanece desacoplado |

## Fase 16 — Ofício: resumo executivo

Itens:
- detalhe rico por blocos;
- ações documentais por status;
- validações de completude com mensagens orientativas.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 16 | Criar resumo executivo e painéis de ação | `oficios/presenters.py`, `oficios/views.py`, `templates/oficios/detail.html` | Não | Médio | Usuário visualiza pendências e ações documentais sem ambiguidade |

## Fase 17 — Ofício: payload documental completo

Itens:
- placeholders completos por tipo;
- contexto institucional com assinaturas;
- custeio, destino, equipe, viatura, roteiro e diárias;
- contrato unificado entre domínio e núcleo documental.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 17 | Fechar payload documental completo | `oficios/services.py`, `documentos/services/validators.py`, `documentos/services/templates.py` | Não | Alto | Payload cobre campos necessários e validação identifica lacunas com precisão |

## Fase 18 — Ofício: DOCX inicial

Itens:
- template DOCX inicial do ofício;
- render via núcleo documental;
- validação de placeholders obrigatórios;
- download DOCX funcional.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 18 | Entregar geração DOCX de Ofício | `documentos/services/renderers/*`, `documentos/resources/*`, `oficios/views.py` | Não | Alto | DOCX baixa com placeholders resolvidos e erros previsíveis |

## Fase 19 — Ofício: PDF

Itens:
- backend de conversão PDF;
- fallback de indisponibilidade;
- mensagens claras de erro de ambiente;
- download PDF.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 19 | Habilitar PDF de Ofício | `documentos/services/backends.py`, `documentos/services/renderers/*`, `documentos/tests/*` | Não | Alto | PDF funciona com fallback e contrato de falha controlada |

## Fase 20 — Justificativa vinculada ao Ofício

Itens:
- model e CRUD de justificativa por ofício;
- regra de prazo e obrigatoriedade;
- geração documental vinculada.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 20 | Consolidar justificativa por ofício | `justificativas/*`, `oficios/services.py`, `documentos/services/*` | Sim | Médio | Regra de prazo e geração documental funcionando por vínculo |

## Fase 21 — Termos vinculados ao Ofício

Itens:
- geração por servidor;
- seleção múltipla;
- deduplicação;
- suporte viatura/motorista;
- DOCX/PDF.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 21 | Termos com vínculo ao ofício e lote | `termos/*`, `oficios/selectors.py`, `documentos/services/*` | Sim | Alto | Geração em lote por servidor com consistência de contexto |

## Fase 22 — Plano de Trabalho

Itens:
- vínculos opcionais com ofício/roteiro;
- datas, destinos, equipe e diárias;
- geração documental.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 22 | Consolidar Plano de Trabalho integrado | `planos_trabalho/*`, `documentos/services/*` | Sim | Alto | PT gera documento com contexto institucional e operacional válido |

## Fase 23 — Ordem de Serviço

Itens:
- equipe e deslocamento;
- destinos e motivo;
- geração documental.

| Fase | Objetivo | Arquivos prováveis | Migration? | Risco | Critério de aceite |
|---|---|---|---|---|---|
| 23 | Consolidar Ordem de Serviço integrada | `ordens_servico/*`, `documentos/services/*` | Sim | Médio | OS com dados consistentes e geração documental disponível |

