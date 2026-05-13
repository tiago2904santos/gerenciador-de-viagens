# Relatorio da Fase 1 - Saneamento do Nucleo Documental

## 1. Commit base
f1e4087f1e077c3d3dd22dfa38b1f6efdc5b3172

Observacao: a branch ja existia ao iniciar esta fase e o HEAD estava em `b5180cddb32fc3c492549855c9e2b887554811c9`, um commit acima do base. Havia alteracoes nao commitadas em `docs/ASSINATURA_ETIQUETA_2_COMPAT.md`, `oficios/presenters.py` e `oficios/views.py`.

## 2. Branch de trabalho
`fechamento/nucleo-documental-fase-1`

## 3. Comandos executados
- `git status`: branch correta, com alteracoes nao commitadas preexistentes.
- `git branch`: confirmou a branch `fechamento/nucleo-documental-fase-1`.
- `git log --oneline -5`: HEAD `b5180cd`, base `f1e4087` como commit anterior.
- `git rev-parse HEAD`: `b5180cddb32fc3c492549855c9e2b887554811c9`.
- `python manage.py check`: OK antes das alteracoes.
- `python manage.py makemigrations --check --dry-run`: OK, sem migracoes pendentes.
- `python manage.py migrate`: OK, nenhuma migracao pendente.
- `python manage.py test`: falhou antes das alteracoes com 5 failures e 8 errors em testes legados de `cadastros`.

Falhas iniciais relevantes:
- `cadastros.views` nao possui atributo `requests` esperado por testes antigos de CEP.
- `cadastros:index`, `cadastros:cidade_create`, `cadastros:cidades_index`, `cadastros:cidades_export_csv` e `cadastros:estado_delete` nao existem nos testes antigos.
- Testes de unidades esperavam acesso anonimo 200, mas as views redirecionam para login.

## 4. Estado geral do sistema
O nucleo documental real esta concentrado em Oficios, Termos, Justificativas, Roteiros, Cadastros, Documentos e Assinaturas. Ha apps instalados para Planos de Trabalho, Ordens de Servico, Prestacoes de Contas, Diario de Bordo, Eventos e Google Drive, mas suas telas principais sao placeholders ou dependem de implementacao futura.

Foram escondidos da navegacao principal e do dashboard os modulos falso-prontos/placeholder. As URLs continuam registradas para compatibilidade, mas nao sao mais anunciadas como fluxo pronto.

## 5. Telas analisadas
| App | URL | View | Template | Status |
| --- | --- | --- | --- | --- |
| core | `/` | `core.views.dashboard` | `templates/core/dashboard.html` | OK apos limpeza |
| oficios | `/oficios/` | `oficios.views.index` | `templates/oficios/index.html` | OK |
| oficios | `/oficios/novo/` | `oficios.views.novo` | redireciona para wizard | PARCIAL |
| oficios | `/oficios/<pk>/dados-viajantes/` | `dados_viajantes` | `templates/oficios/wizard_dados_viajantes.html` | OK/PARCIAL |
| oficios | `/oficios/<pk>/transporte/` | `transporte` | `templates/oficios/wizard_transporte.html` | OK/PARCIAL |
| oficios | `/oficios/<pk>/roteiro/` | `wizard_roteiro` | `templates/oficios/wizard_roteiro.html` | PARCIAL |
| oficios | `/oficios/<pk>/justificativa/` | `wizard_justificativa` | `templates/oficios/wizard_justificativa.html` | OK/PARCIAL |
| oficios | `/oficios/<pk>/documentos/` | `wizard_documentos` | `templates/oficios/wizard_documentos.html` | PARCIAL |
| oficios | `/oficios/<pk>/assinaturas/` | `wizard_assinaturas_documentos` | `templates/oficios/wizard_assinaturas.html` | PARCIAL, Central de Assinaturas |
| oficios | `/oficios/<pk>/documentos/<formato>/` | `baixar_documento` | service response | OK/PARCIAL |
| termos | `/termos/` | `termos.views.index` | `templates/termos/index.html` | PARCIAL |
| termos | `/termos/oficio/<pk>/preview/` | `preview_termo_oficio` | `templates/termos/preview.html` | OK/PARCIAL |
| termos | `/termos/oficio/<pk>/servidor/<servidor_pk>/<formato>/` | `baixar_termo_servidor` | service response | OK/PARCIAL |
| justificativas | `/justificativas/` | `modelos_index` | `templates/justificativas/modelos/index.html` | OK |
| roteiros | `/roteiros/` | `roteiros.views.index` | `templates/roteiros/index.html` | OK/PARCIAL |
| cadastros | `/cadastros/servidores/`, `/cargos/`, `/viaturas/`, `/combustiveis/`, `/unidades/`, `/configuracao/` | `cadastros.views.*` | `templates/cadastros/**` | OK/PARCIAL |
| planos_trabalho | `/planos-trabalho/` | `index` | `templates/planos_trabalho/index.html` | FALSO-PRONTO escondido |
| ordens_servico | `/ordens-servico/` | `index` | `templates/ordens_servico/index.html` | FALSO-PRONTO escondido |
| prestacoes_contas | `/prestacoes-contas/` | `index` | `templates/prestacoes_contas/index.html` | FALSO-PRONTO escondido |
| diario_bordo | `/diario-bordo/` | `index` | `templates/diario_bordo/index.html` | FALSO-PRONTO escondido |
| eventos | `/eventos/` | `index` | `templates/eventos/index.html` | FALSO-PRONTO escondido |
| integracoes.google_drive | `/integracoes/google-drive/` | `index` | `templates/integracoes/google_drive/index.html` | FALSO-PRONTO nao exposto |

## 6. Acoes funcionando
- Ofícios: abrir lista, criar rascunho, editar etapas, excluir, salvar rascunho, salvar e continuar.
- Ofícios/documentos: DOCX e PDF de ofício via `baixar_documento`, com validacao de pendencias.
- Justificativa: PDF/DOCX via `baixar_justificativa_documento`, com validacao de pendencias.
- Termos: preview, PDF inline por servidor, download PDF/DOCX por servidor e lote ZIP.
- Roteiros: CRUD, autosave, calculo de rota e calculo de diarias existem.
- Cadastros: servidores, cargos, combustiveis, unidades, viaturas e configuracao possuem CRUD real.
- Assinaturas: pagina publica por token existe; Central de Assinaturas em Ofícios lista status, hashes, destinatarios, pedidos e links quando artefatos persistidos estao ativos.

## 7. Acoes quebradas
- `python manage.py test` acusa testes de cadastros desatualizados contra a arquitetura atual.
- Acoes de PDF dependem do ambiente de PDF/DOCX. O teste inicial emitiu avisos repetidos de WeasyPrint indisponivel.
- Botao de envio automatico de link de assinatura era apenas visual/desabilitado e foi removido.
- Entradas de dashboard/menu para Planos, Ordens, Prestacoes, Diario, Eventos e Assinaturas levavam a placeholders e foram escondidas.

## 8. Funcionalidades falso-prontas
- Planos de Trabalho e Ordens de Servico aparecem como apps e possuem templates/resources, mas a tela de modulo e o fluxo completo nao estao prontos.
- Prestacao de Contas e Diario de Bordo existem como placeholders.
- Eventos ainda aparece como arquitetura antiga/legada e nao deve voltar a ser eixo obrigatorio.
- Google Drive existe como placeholder de integracao.
- Envio automatico de assinatura aparecia como botao desabilitado.
- Assinatura direta dentro de Oficios era sugerida por rotas/botoes legados; a etapa foi saneada para Central de Assinaturas.
- Dados demo `[DEMO]` existem em comando de seed e testes; a geracao documental possui limpeza em `oficios/documents.py` e nao deve exibir esses prefixos.

## 9. Funcionalidades removidas ou escondidas
- Removidos do menu lateral: Eventos, Planos de Trabalho, Ordens de Servico, Prestacoes de Contas, Diario de Bordo e Assinaturas.
- Removidos do dashboard: cards de Planos de Trabalho, Ordens de Servico, Prestacoes de Contas e Diario de Bordo.
- Renomeado o acesso da etapa Documentos de `Assinar documentos` para `Central de assinaturas`.
- Removido o botao `Verificar assinatura` da etapa Documentos.
- Removido o botao desabilitado `Enviar` da Central de Assinaturas.

## 10. Problemas encontrados em Oficios
- `novo` cria rascunho imediatamente, o que pode poluir cadastro se o usuario abandona o fluxo.
- Numero e data ja sao preenchidos pelo rascunho persistido, mas isso reforca a criacao precoce.
- A etapa Documentos exibe pendencias de forma forte ao abrir quando dados incompletos existem.
- Persistencia de roteiro/diarias parece estar concentrada em `roteiros.services` e precisa de teste de regressao especifico na Fase 2.
- Termos usam selecao propria de servidores; se o usuario selecionar varios, o backend gera por servidor/lote, mas o UX ainda precisa deixar claro que cada termo e individual.

## 11. Problemas encontrados em Assinaturas
- A assinatura real deve continuar fora do wizard, em pagina publica por token.
- A etapa de Ofícios foi tratada como Central de Assinaturas, mas ainda depende de `DOCUMENTOS_PERSIST_ARTEFATOS=true`.
- O backend de assinatura com etiqueta existe, mas o escopo de Fase 1 nao valida assinatura completa.
- Envio automatico de link nao existe e foi removido da UI.
- A Fase 3 deve implementar o fluxo completo de assinatura publica, regras de destinatarios, auditoria, ordem de assinatura e experiencia final.

## 12. Problemas encontrados em DOCX/PDF
- Tipos registrados: Ofício, Termo de Autorizacao, Justificativa, Plano de Trabalho e Ordem de Servico.
- Templates DOCX existem em `documentos/resources/`.
- Templates PDF HTML/CSS existem em `templates/documentos/pdf/`.
- Endpoints de Ofícios:
  - Ofício: `/oficios/<pk>/documentos/<formato>/`, `/oficios/<pk>/documentos/oficio-pdf-inline/`.
  - Justificativa: `/oficios/<pk>/documentos/justificativa/<formato>/`, inline PDF.
  - Plano: `/oficios/<pk>/documentos/plano-trabalho/<formato>/`, inline PDF.
  - Ordem: `/oficios/<pk>/documentos/ordem-servico/<formato>/`, inline PDF.
  - Termos: endpoints do app `termos`.
- Armazenamento existe via `DocumentoArtefato` e `documentos.services.persistence`, condicionado ao ambiente.
- Validacao de placeholders existe em `documentos.services.placeholders`.
- A geracao bloqueia documento incompleto por `validar_oficio_para_documento`, redirecionando para correcao.
- Nao foi reescrito gerador nesta fase.

## 13. Problemas encontrados em Termos
- `templates/termos/index.html` e informativo, nao lista documentos reais.
- Preview e downloads funcionam apenas a partir de Oficio completo e servidores selecionados.
- O backend trata termo por servidor e lote ZIP; a UX da selecao multipla precisa explicacao melhor na Fase 2.

## 14. Problemas encontrados em Justificativas
- Modelos de justificativa possuem CRUD real.
- Justificativa por oficio e integrada ao wizard.
- A obrigatoriedade depende da regra de antecedencia e da primeira saida do roteiro.
- Precisa de regressao focada para garantir que texto/modelo nao some entre edicoes.

## 15. Problemas encontrados em Roteiros
- Ha referencias legadas a `evento`, `roteiro_evento`, `guiado` e compatibilidade com fluxo antigo em `roteiros/roteiro_logic.py`.
- O fluxo atual de Ofícios usa roteiro document-centric sem tornar Evento obrigatorio.
- Roteiro/diarias devem ser alvo principal da Fase 2 para persistencia e UX.

## 16. Problemas encontrados em Cadastros
- CRUD real existe para principais cadastros.
- Testes legados ainda esperam rotas antigas/anonimas.
- `cadastros.views` usa servico de CEP, mas testes mockam `cadastros.views.requests`, atributo que nao existe mais.
- Cidades/Estados aparecem no codigo e templates, mas nao estao no menu lateral atual.

## 17. Dividas tecnicas encontradas
- Codificacao/acentuacao aparece inconsistente em alguns arquivos e saidas.
- Ha `<script>` em varios templates, principalmente externos/static, e Leaflet via CDN em roteiros.
- Nao foram encontrados blocos `<style>` inline em templates auditados por `rg`.
- CSS/JS a centralizar futuramente:
  - `templates/oficios/wizard_roteiro.html`
  - `templates/roteiros/roteiro_form_page.html`
  - `templates/oficios/wizard_documentos.html`
  - `templates/oficios/wizard_assinaturas.html`
  - `templates/assinaturas/assinatura_token.html`
  - `templates/documentos/pdf_viewer.html`
- Arquitetura antiga de eventos/roteiro ainda aparece em codigo e testes; nao foi removida por risco.

## 18. Pendencias para a Fase 2
- Corrigir testes legados de cadastros ou readequar rotas esperadas.
- Revisar criacao de rascunho de Ofício para reduzir poluicao de cadastro.
- Testar persistencia de roteiro, trechos, retorno, diarias e valores por extenso no fluxo de Ofícios.
- Suavizar pendencias iniciais na etapa Documentos.
- Consolidar mapeamento de DOCX/PDF com testes por tipo documental.
- Melhorar UX de Termos por servidor/lote.
- Decidir se Planos/Ordens ficam apenas como documentos derivados do Oficio ou ganham CRUD proprio futuramente.
- Centralizar JS/CSS ainda soltos.

## 19. Criterio para avancar para a Fase 2
- Menu e dashboard nao devem anunciar modulos placeholder como prontos.
- A etapa de Ofícios deve mostrar Central de Assinaturas, nao assinatura direta.
- `python manage.py check` deve continuar sem erros.
- Falhas de teste existentes devem estar registradas e priorizadas.
- A Fase 2 deve focar em persistencia/consistencia de Ofícios, roteiro, diarias e documentos, sem implementar e-Protocolo, WhatsApp ou Prestacao de Contas.

## Correções manuais do cadastro de Ofícios

Esta secção consolida o saneamento da Fase 1 aplicado ao fluxo de Ofícios, roteiros, documentos e assinaturas (ordem de implementação 1 a 8), com foco no que o utilizador vê e no que foi coberto por testes automatizados.

### Problema e solução (resumo)

| Problema | Solução |
| --- | --- |
| Etapa 3 (roteiro) não refletia sede resolvida por CEP/config quando o roteiro ainda não tinha origem gravada | No GET do wizard de roteiro, o estado da sede passa a alimentar o `initial` do formulário e os querysets de cidade antes da renderização; aviso de origem da sede em texto discreto. |
| Mapa/rota com mensagem genérica ou sem município | Garantida mensagem amigável nos fluxos de routing e testes no JSON de preview. |
| Tempos em HH:mm pouco consistentes no editor | Máscara em tempo real nos trechos e no retorno, com passo ±15 alinhado. |
| Cabeçalhos/rodapés documentais com capitalização incorreta | Reforço via formatadores/contextos e testes em `documentos` e `oficios`. |
| Rodapé do wizard (voltar, rascunho, finalizar) e lista | Rótulos alinhados; ao voltar em documentos persiste artefacto em cache quando aplicável; justificativa permite voltar/guardar rascunho sem bloquear por texto obrigatório nessas ações; cartão de lista mostra estado final unificado com assinatura quando existir PDF assinado. |
| Página pública de assinatura com texto cortado e preview pouco nítido | CSS com menos `overflow: hidden` nos painéis, texto com quebra de linha, DPR até 3 no canvas PDF.js, link para abrir o PDF noutro separador; URL absoluta de verificação no dataset quando já existe código. |
| Etiqueta no PDF assinado com hash/cargo visíveis | Carimbo ReportLab deixa de desenhar cargo e linha “Hash: …”; última linha usa texto de validação (`verifique em …`) com a URL; pré-visualização JS da etiqueta alinhada (sem linha de código). |

### Ficheiros principais

- Ofícios / roteiros: `oficios/views.py`, `oficios/presenters.py`, `templates/oficios/partials/wizard_actions.html`, `templates/oficios/wizard_documentos.html`, `templates/oficios/wizard_roteiro.html`, `templates/roteiros/includes/_roteiro_editor.html`, `static/js/pages/roteiros/editor/index.js`, testes em `oficios/tests/` e `roteiros/tests/test_routing.py`.
- Documentos: `documentos/tests/test_formatters.py`, `oficios/tests/test_docxtpl_context_capitalizacao.py`, `documentos/services/signing/label_overlay.py` (comportamento de prefixo SHA-256 já coberto por testes).
- Assinaturas: `assinaturas/views.py`, `templates/assinaturas/assinatura_token.html`, `templates/assinaturas/base_publica_assinatura.html`, `static/css/signature-public.css`, `static/js/pages/assinatura-pdf.js`, `assinaturas/services/carimbo_pdf.py`, `assinaturas/tests/test_carimbo_pdf.py`, `oficios/tests/test_wizard_assinar_pdf.py` (resolução de marcador de merge no teste do template).

### Teste manual sugerido

1. Configurar sede em **Cadastros → Configuração** (CEP e/ou cidade padrão), abrir Ofício novo na etapa **Roteiro** e confirmar que origem/cidade aparecem coerentes e o aviso de origem é legível sem destaque excessivo.
2. Abrir mapa de rota com município sem coordenadas (dados de teste) e confirmar mensagem explícita na UI.
3. Editar tempos de trecho e de retorno com teclado e botões ±15.
4. Gerar DOCX/PDF de ofício, justificativa e termo e rever cabeçalhos/rodapés (maiúsculas institucionais e endereço sem `title()` cego).
5. No wizard, usar **Voltar**, **Salvar como rascunho** e **Finalizar**; na lista, verificar texto “Finalizado — …” quando aplicável.
6. Abrir link público de assinatura: conferir painel de detalhes, zoom, “Abrir PDF em nova aba” e, após assinatura com etiqueta, abrir o PDF e confirmar ausência de “Cargo:” e “Hash:” na etiqueta e presença da linha de validação/URL.

### Teste automatizado

- `python manage.py check` e `python manage.py makemigrations --check --dry-run` executados durante a fase sem pendências.
- Suítes relevantes: `oficios`, `roteiros`, `assinaturas`, `documentos` (nomeadamente `test_signature_label`, `test_carimbo_pdf`, `test_routing`).
- Execução segmentada de regressão da Fase 1: `python manage.py test oficios roteiros documentos assinaturas` — OK (335 testes, 1 ignorado).
- Nota: `python manage.py test` completo pode ainda falhar em testes legados de `cadastros` não relacionados a este saneamento (já registado na secção 3 e 16 deste relatório).

### Pendências

- Testes legados de `cadastros` continuam desalinhados com a arquitetura atual (URLs e mocks).
- WeasyPrint pode emitir avisos em ambiente sem bibliotecas nativas; não bloqueia os testes executados aqui.
- Assinatura pendente sem `AssinaturaDigital` ainda não tem URL absoluta de verificação no dataset da página pública (só após existir código).
- Fase 2: persistência fina de roteiro/diárias, UX de pendências na etapa Documentos e eventual limpeza de código legado de eventos em roteiros.
