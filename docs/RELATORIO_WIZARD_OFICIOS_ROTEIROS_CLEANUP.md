# Relatório Wizard Cleanup — Ofícios e Roteiros

## 1. Resumo executivo

**Corrigido:** estrutura visual do wizard de ofícios (header, chip, stepper, cards da etapa 1, footer mínimo), paridade parcial de shell no roteiro, JS condicional do Card 4 (motorista externo/carona), salvamento opcional de transporte na etapa 1 via `transporte_embed`, testes alinhados ao novo markup.

**Não mexido:** `static/js/pages/roteiros/editor/index.js`, `static/js/roteiros-map.js`, cálculo de rota, trechos, diárias, endpoints, payloads, models, migrations, URLs, regras de negócio fora da reorganização visual da etapa 1.

**Divergência residual com UI Lab:** roteiro permanece fluxo de página única (sem stepper de 6 etapas); etapa 2 de ofícios ainda existe no backend e pode repetir viatura até remoção funcional planejada; toggle “Carona” é apenas indicador visual (sem campo no model).

## 2. Problemas visuais corrigidos

| Problema | Antes | Depois | Arquivos alterados |
|----------|-------|--------|-------------------|
| Chip de status desalinhado/incorreto | Chip fora do padrão ou texto errado | `page-header-status-chip` na faixa azul com variantes `draft` / `pending` / `active` | `oficios/presenters.py`, `header_stack_back_action.html` |
| Stepper quebrado | Linhas/círculos sobre texto | `page_stepper.html` com track e conteúdo separados; flex/grid em `page-shell.css` | `page_stepper.html`, `page-shell.css` |
| Camadas/cards em excesso | card > card > panel | `page-shell--wizard` → header → stepper → `cv-wizard-section-stack` → até 4 cards | `wizard_base.html`, `wizard_dados_viajantes.html` |
| Footer etapa 1 poluído | DOCX, PDF, Termos, etc. | Apenas “Avançar →” (`wizard_footer_mode=step1_minimal`) | `wizard_actions.html`, `views.py` |
| Etapa 1 desorganizada | Blocos legados | 4 cards: Dados principais, Equipe+motorista, Viatura, Motorista externo | `wizard_dados_viajantes.html`, partials novos |

## 3. Header

- **Chip/status:** componente global `page-header-status-chip`; rótulos via presenter (`Rascunho`, `Pendente`, etc.).
- **Título/contexto:** eyebrow `OFÍCIOS`, título `Cadastro de ofício`.
- **Subheader:** marcador `OF`, módulo `OFÍCIOS`, subtítulo dinâmico `Etapa N de 6 — …`, botão `Voltar à lista` (`cv-btn--back-list`).
- **Botão voltar:** no rail direito, não no footer da etapa 1.

## 4. Stepper

- **Correção:** card isolado (`page-stepper`), marcador e labels em colunas flex com `flex: 1 1 0`, linha de conexão no track.
- **Estados:** classes `is-complete`, `is-current`, `is-upcoming`, `is-locked` (via presenter).
- **Responsividade:** quebra em grid em breakpoints em `page-shell.css`.
- **Pendências:** validar visualmente em 1440×900 e tema escuro no navegador.

## 5. Etapa 1 do Ofício

| Card | Conteúdo | Campos | Condição | Persistência | Observações |
|------|----------|--------|----------|--------------|-------------|
| 1 — Dados principais | Dados do ofício + Motivo | protocolo, custeio, custeio_observacao, modelo_motivo, motivo; número/data readonly | Sempre | `OficioDadosViajantesForm` | Seções `wizard-inner-section` |
| 2 — Equipe e motorista | Multiselect + motorista na equipe | servidores, termos (hidden), motorista | Sempre | Mesmo POST | Termos via `servidores_termo_autorizacao_present` |
| 3 — Viatura | Busca/preview viatura | campos `OficioTransporteForm` | Sempre | POST com `transporte_embed=1` | Reutiliza JS `oficios-transporte.js` |
| 4 — Motorista externo | Carona + refs | motorista_modo, manual, ofício ref, protocolo | Sem motorista na equipe | Campos existentes no model | Toggle carona só UI |

## 6. Motorista externo / carona

- **Funcionamento:** `oficios-wizard-driver-state.js` oculta Card 4 quando motorista ∈ equipe; exibe quando motorista fora da equipe ou modo manual.
- **Padrão:** toggle Carona = Sim (`data-cv-state-default="sim"`).
- **Campos:** `motorista_manual_nome`, `motorista_oficio_referencia`, `motorista_protocolo_ref`, `motorista_modo`.
- **Persistência carona:** pendente — não há campo `carona` no model; documentado para fase posterior.

## 7. Footer

- **Removidos da etapa 1:** Voltar, DOCX, PDF, Justificativa PDF, Plano DOCX, Ordem serviço DOCX, Termos, Salvar rascunho.
- **Onde ficam:** etapas documentos/assinaturas (`wizard_show_document_actions=True` em `documentos` e etapas finais).
- **Mantido etapa 1:** `Avançar →` (`action=wizard_next`).

## 8. Roteiro

- **Alterações:** `page-shell--wizard`, header global, remoção de wrappers `app-page-shell__inner` redundantes em `_roteiro_editor.html`.
- **Contratos preservados:** `#roteiro-editor-form`, `data-api-*`, mapa, trechos.
- **Pendências:** stepper multi-etapa não aplicável ao editor único; validar screenshot manual.

## 9. CSS/tokens

| Arquivo | Uso |
|---------|-----|
| `page-shell.css` | stepper, `wizard-inner-section`, `footer-actions--primary-only`, `field__static-value` |
| `oficios.css` | estilos de domínio existentes (viatura busca) |
| Tokens | variáveis `--layout-*`, cores de chip/status globais |

**Hardcoded removidos:** evitados em novos blocos; classes genéricas `wizard-inner-section`, não `oficio-card-bonito`.

## 10. Contrato DOM/JS preservado

| ID / data attribute | Arquivo | Preservado? | Observação |
|---------------------|---------|-------------|------------|
| `data-oficio-wizard-shell` | wizard_base | Sim | Shell |
| `data-oficio-wizard-step1` | wizard_dados_viajantes | Sim | Driver state |
| `data-oficio-driver-external-card` | card motorista | Sim | Card 4 |
| `data-oficio-viatura-*` | card viatura | Sim | Transporte JS |
| `data-app-multiselect` | servidores | Sim | Multiselect |
| `data-custeio-observacao-wrapper` | card 1 | Sim | Custeio JS |
| `#oficio-transporte-root` | viatura | Sim | API placa |
| `#roteiro-editor-form` | roteiro | Sim | Não alterado |

## 11. Testes

| Comando | Resultado |
|---------|-----------|
| `python manage.py check` | OK (0 issues) |
| `python manage.py test oficios.tests.test_wizard_dados_viajantes` | OK (22 tests) |
| `python manage.py test oficios.tests.test_views` (+ transporte, justificativa) | OK após ajuste de asserts legados |
| Smoke manual | Pendente no navegador |

## 12. Screenshots

Pasta: `screenshots/wizard-parity-clean/` — ver `README.md` na pasta para captura manual (Playwright/autenticação não executado nesta sessão).

## 13. Pendências

**Obrigatório antes de rotas/trechos:**
- Remover ou tornar pass-through a etapa 2 transporte (viatura já na etapa 1).
- Paridade visual steps 2–6 do ofício.

**Visual para depois:**
- Screenshots automatizados; tema escuro validado em produção.

**Funcional para depois:**
- Campo persistido `carona` no model + migration.
- Consolidar viatura só na etapa 1 no fluxo de navegação.

## 14. Decisão

**A. Liberado para continuar paridade de steps 2–6**

A etapa 1 está estruturalmente alinhada ao UI Lab Wizard, testes de dados/viajantes passam, contratos DOM/JS preservados e footer limpo. Ressalvas: carona só UI, transporte duplicado na etapa 2, screenshots manuais pendentes.
