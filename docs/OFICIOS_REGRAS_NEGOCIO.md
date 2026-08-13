# Regras de negócio de Ofícios

## REG-OF-001 — Numeração anual editável, com sugestão automática por lacuna liberada
- Descrição: ao criar um ofício, o sistema reserva automaticamente um número (sugestão), mas o campo N° do Ofício é editável na Etapa 1 (Dados dos viajantes) — alguns setores preenchem o número manualmente (numeração não sequencial). A sugestão automática usa a menor lacuna liberada por **exclusão** de um ofício já numerado (`OficioNumeroLacuna`); números apenas pulados manualmente (ex.: ir de 10 direto para 15) não são oferecidos como sugestão — só o maior número usado + 1. **Editar** o número de um ofício existente (ex.: corrigir 88 para 98) **não** libera o número antigo — só a **exclusão** de um ofício numerado libera um número para reaproveitamento; cancelar um ofício (sem excluir) também não libera o número.
- Origem no legacy: `eventos/models.py` (`Oficio.get_next_available_numero`, `Oficio.save`).
- Arquivos/funções: model `Oficio`, `OficioNumeroLacuna`; services `get_next_available_numero_oficio`, `reservar_numero_oficio`, `excluir_oficio`, `atualizar_oficio_dados_viajantes`; form `OficioDadosViajantesForm.clean_numero`.
- Estado no 3.0: implementado na Fase 12.2 para criação pelo wizard de Dados e viajantes; edição manual do número adicionada depois (sem liberar o número antigo — testado em produção e revertido após reportar comportamento indesejado).
- Adaptação correta: manter service transacional e constraint `(ano, numero)`; validar unicidade amigável no form antes do `IntegrityError`.
- Prioridade: Alta.
- Riscos: colisão de número em concorrência.
- Testes necessários: criação sequencial, reaproveitamento de lacuna após exclusão, números pulados manualmente não sugeridos, edição de número não libera o antigo, concorrência.

## REG-OF-002 — Protocolo canônico e visual
- Descrição: protocolo é persistido em dígitos e exibido em máscara `XX.XXX.XXX-X`.
- Origem no legacy: `core/utils/masks.py`, `eventos/models.py`.
- Arquivos/funções: `normalize_protocolo`, `format_protocolo`, `Oficio.clean`.
- Estado no 3.0: parcial.
- Adaptação correta: normalizador único + validação de tamanho + formatter em presenter.
- Prioridade: Alta.
- Riscos: inconsistência entre persistência e UI.
- Testes necessários: entrada mascarada, entrada sem máscara e exibição.

## REG-OF-003 — Custeio “outra instituição” exige detalhamento
- Descrição: quando custeio for externo, o nome da instituição é obrigatório.
- Origem no legacy: `eventos/models.py` (`Oficio.clean`).
- Arquivos/funções: `custeio_tipo`, `nome_instituicao_custeio`.
- Estado no 3.0: implementado no form mínimo.
- Adaptação correta: manter em form + service e refletir no payload documental.
- Prioridade: Alta.
- Riscos: documento incompleto juridicamente.
- Testes necessários: validação condicional no form e persistência.

## REG-OF-004 — Motorista carona exige protocolo específico
- Descrição: quando motorista for carona, protocolo do motorista torna-se obrigatório e validado.
- Origem no legacy: `eventos/models.py`.
- Arquivos/funções: `motorista_carona`, `motorista_protocolo`.
- Estado no 3.0: não implementado.
- Adaptação correta: regra explícita em fase de transporte.
- Prioridade: Média.
- Riscos: inconsistência documental de deslocamento.
- Testes necessários: cenário carona com/sem protocolo.

## REG-OF-005 — Assunto automático (autorização vs convalidação)
- Descrição: tipo de assunto é inferido por comparação entre data do ofício e primeira saída.
- Origem no legacy: `Oficio.compute_assunto_tipo`.
- Arquivos/funções: método de domínio.
- Estado no 3.0: não implementado.
- Adaptação correta: regra em service/presenter, sem lógica em template.
- Prioridade: Média.
- Riscos: emissão com assunto incorreto.
- Testes necessários: casos antes/depois da saída.

## REG-OF-006 — Modo de roteiro (salvo vs próprio)
- Descrição: ofício pode usar roteiro existente do evento ou roteiro próprio no ofício.
- Origem no legacy: `Oficio.roteiro_modo`, `views.py` step3.
- Arquivos/funções: model + views/forms.
- Estado no 3.0: parcial (apenas vínculo de roteiro).
- Adaptação correta: manter roteiro opcional com fonte explícita e sync seguro.
- Prioridade: Alta.
- Riscos: perda de coerência entre rota exibida e documento.
- Testes necessários: ambos modos e troca de modo.

## REG-OF-007 — Trechos de ida e retorno com semânticas distintas
- Descrição: ida fica em coleção de trechos; retorno em campos dedicados.
- Origem no legacy: `OficioTrecho` + campos `retorno_*` em `Oficio`.
- Arquivos/funções: model e lógica de resumo.
- Estado no 3.0: não implementado.
- Adaptação correta: estruturar entidades de trecho e retorno sem duplicidade.
- Prioridade: Alta.
- Riscos: cálculo incorreto de período/diárias.
- Testes necessários: múltiplos trechos, retorno ausente/presente.

## REG-OF-008 — Diárias calculadas por período e destino
- Descrição: quantidade/valor/extenso dependem de datas, trecho e tipo de destino.
- Origem no legacy: `eventos/services/diarias.py`, `views.py`.
- Arquivos/funções: cálculo de diárias e endpoints.
- Estado no 3.0: não implementado.
- Adaptação correta: service puro no domínio com saída para payload documental.
- Prioridade: Alta.
- Riscos: impacto financeiro e retrabalho manual.
- Testes necessários: cenários PR/fora PR, ida/volta e períodos distintos.

## REG-OF-009 — Justificativa por prazo mínimo
- Descrição: ofício exige justificativa quando antecedência é menor que o prazo configurado.
- Origem no legacy: `eventos/services/justificativa.py`, `ConfiguracaoSistema.prazo_justificativa_dias`.
- **Implementação no 3.0 (implementado):**
  - Regra de prazo e primeira saída: `justificativas/services.py` (`get_prazo_justificativa_dias`, `get_primeira_saida_oficio`, `avaliar_justificativa_oficio`, `oficio_exige_justificativa`).
  - Prazo configurável via `cadastros.ConfiguracaoSistema.prazo_justificativa_dias` (fallback 10 dias).
  - Antecedência: `(primeira_saida.date() - oficio.data_criacao).days` usando **`data_criacao`** (campo de domínio), não `created_at`.
  - Persistência e wizard: modelos `Justificativa` / `ModeloJustificativa`, etapa 4 `/oficios/<pk>/justificativa/`, integração ao stepper.
  - Bloqueio de DOCX/PDF e finalização: `oficios/services.validar_oficio_para_documento`, `redirect_para_corrigir_documento_oficio`; downloads via `oficios.views.baixar_documento`.
  - Testes: `justificativas/tests/test_services.py`, `justificativas/tests/test_models.py`, `justificativas/tests/test_forms_services_layer.py`, `oficios/tests/test_wizard_justificativa.py`, `oficios/tests/test_services.py`.
- Prioridade: Alta.
- Riscos: descumprimento normativo (mitigado por validação central).

## REG-OF-010 — Geração de Termo por modalidade
- Descrição: termo pode ser rápido, automático com viatura ou automático sem viatura.
- Origem no legacy: `TermoAutorizacao`, `services/documentos/termo_autorizacao.py`.
- Arquivos/funções: inferência de modo e template variant.
- Estado no 3.0: não implementado.
- Adaptação correta: app `termos` desacoplado, consumindo núcleo documental.
- Prioridade: Alta.
- Riscos: lote documental inconsistente.
- Testes necessários: cada modalidade e seleção por servidor.

## REG-OF-011 — PT e OS reutilizam contexto do Ofício
- Descrição: plano de trabalho e ordem de serviço derivam parte do contexto de ofício/evento/roteiro.
- Origem no legacy: `PlanoTrabalho`, `OrdemServico`, `views_global.py`, services documentais.
- Arquivos/funções: resolução de contexto e downloads.
- Estado no 3.0: não implementado.
- Adaptação correta: entidades independentes com vínculo opcional.
- Prioridade: Média.
- Riscos: acoplamento excessivo ou duplicação de dados.
- Testes necessários: geração com e sem vínculo de ofício.

## REG-OF-012 — Geração documental condicionada a status de prontidão
- Descrição: documento só é gerado se tipo, formato, template, backend e validações estiverem OK.
- Origem no legacy: `eventos/services/documentos/validators.py`.
- Arquivos/funções: `get_document_generation_status`.
- Estado no 3.0: parcial via núcleo V1.1.
- Adaptação correta: manter status preditivo e erros explícitos.
- Prioridade: Alta.
- Riscos: download de documento inválido.
- Testes necessários: estados available/pending/unavailable.

## REG-OF-013 — Placeholders obrigatórios e não resolvidos
- Descrição: placeholders necessários devem existir e nenhum placeholder pode escapar sem substituição.
- Origem no legacy: `renderer.py` + template mapping.
- Arquivos/funções: extração/substituição placeholder.
- Estado no 3.0: implementado no núcleo documental.
- Adaptação correta: manter contrato no núcleo e reforçar nos tipos documentais.
- Prioridade: Alta.
- Riscos: documento com marcadores visíveis.
- Testes necessários: missing placeholder e unresolved placeholder.

## REG-OF-014 — Assinaturas e contexto institucional por tipo documental
- Descrição: cada documento usa assinatura/configuração específica.
- Origem no legacy: `ConfiguracaoSistema`, `AssinaturaConfiguracao`, `context.py`.
- Arquivos/funções: builders institucionais e assinatura por tipo.
- Estado no 3.0: base existente em `cadastros`.
- Adaptação correta: selector central institucional + consumo por payload.
- Prioridade: Alta.
- Riscos: assinatura incorreta em documento oficial.
- Testes necessários: fallback, ausência de assinatura e troca de tipo.

## REG-OF-015 — PDF depende de ambiente e fallback
- Descrição: geração PDF depende de backend e pode falhar por ambiente; erro deve ser explícito.
- Origem no legacy: `eventos/services/documentos/backends.py`, `renderer.py`.
- Arquivos/funções: disponibilidade DOCX/PDF e fallback COM.
- Estado no 3.0: contrato parcialmente previsto.
- Adaptação correta: manter check de disponibilidade e mensagens claras.
- Prioridade: Média.
- Riscos: produção sem PDF operacional.
- Testes necessários: backend indisponível e fallback.

## REG-OF-016 — Autosave em formulários longos
- Descrição: alterações em wizard são salvas automaticamente com debounce e beacon.
- Origem no legacy: `static/js/oficio_wizard.js`, `views.py`.
- Arquivos/funções: `createAutosave`.
- Estado no 3.0: não implementado.
- Adaptação correta: autosave opcional por página, sem acoplamento global.
- Prioridade: Média.
- Riscos: perda de dados em formulários extensos.
- Testes necessários: autosave por input, navegação e abandono de página.

## REG-OF-017 — Etapa 1 usa somente Motivo
- Descrição: a Etapa 1 do wizard de Ofícios não exibe mais "Assunto e motivo"; o bloco oficial é somente "Motivo".
- Origem no legacy: regra de simplificação funcional com manutenção do texto de motivo.
- Estado no 3.0: implementado.

## REG-OF-018 — Data de criação automática e não editável
- Descrição: `data_criacao` é preenchida automaticamente com a data local no salvamento e não pode ser editada na Etapa 1.
- Estado no 3.0: implementado.

## REG-OF-019 — Status automático RASCUNHO/GERADO
- Descrição: status é calculado por completude da Etapa 1 e pela ação do usuário (`save_draft` ou `save_continue`).
- Estado no 3.0: implementado.

## REG-OF-020 — Modelo de motivo para preenchimento assistido
- Descrição: usuário pode selecionar um modelo ativo para preencher o campo `motivo`, com edição manual livre.
- Estado no 3.0: implementado com backend obrigatório e JS progressivo opcional.

## REG-OF-021 — Resumo informativo no GET inicial
- Descrição: no GET de `/oficios/novo/`, a Etapa 1 deve sempre exibir Data criação e Status em modo informativo antes de qualquer salvamento. N° do Ofício também aparece pré-preenchido com a sugestão automática, mas é editável (ver REG-OF-001).
- Estado no 3.0: implementado; campo N° do Ofício passou de somente leitura para editável.

## REG-OF-022 — Custeio observação condicional
- Descrição: `custeio_observacao` só é exibido quando `custeio=Outra instituição`; validação backend continua obrigatória nesse cenário.
- Estado no 3.0: implementado.

## REG-OF-023 — Gerenciador de modelos de motivo
- Descrição: a Etapa 1 deve oferecer acesso direto ao CRUD de modelos de motivo com listagem, criação, edição e exclusão.
- Estado no 3.0: implementado.

