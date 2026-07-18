# Inventário do redesign global — tema escuro

## Linha de base

- Branch isolada: `codex/redesign-global-ui`.
- Base inicial: `main` em `6f5046c`, worktree limpo.
- Escopo encontrado: 337 templates, 55 folhas CSS e 67 arquivos JavaScript.
- Verificação Django inicial: sem problemas (`config.settings.test`).
- Auditoria inicial: 3.791 ocorrências suspeitas, incluindo 1.766 visuais hardcoded, 1.238 cores literais, 152 botões crus, 146 campos legados e 74 filtros legados.
- Problema crítico do shell: sidebar configurada como 15% da viewport, comprimindo textos e navegação antes do breakpoint móvel.

## Fonte de verdade

| Camada | Contrato canônico | Situação inicial | Estratégia |
| --- | --- | --- | --- |
| Tema | `tokens.css` + `theme.css` | aliases semânticos e valores de página misturados | camada escura final em `dark-redesign.css`, sem regras claras |
| Shell | `components/layout/*` | estrutura canônica, largura percentual frágil | manter HTML e corrigir tokens, densidade e breakpoints |
| Botões | `components/ui/buttons/*` + `.cv-btn` | várias taxonomias e botões crus | aparência unificada por variantes existentes; migração HTML incremental |
| Campos | `components/ui/forms/*` | componentes globais coexistem com `.form-control`/`.form-select` | contrato visual único via tokens; migrar consumidores sem alterar nomes Django |
| Pickers | `cv-custom-select`, `cv-search-picker`, `cv-date-picker` | JS global disponível, estilos fragmentados | preservar data-API e unificar superfícies, foco e dropdowns |
| Cards | `components/cards/*` e `components/ui/layouts/*` | equivalentes e aliases por domínio | unificar superfície, borda, elevação e ritmo; página só compõe |
| Listas | `components/lists/*` | estrutura canônica parcial | unificar linhas, filtros, tabelas, vazios e paginação |
| Feedback | `components/ui/feedback/*` | globais disponíveis, estados locais persistem | consolidar cores de estado e foco por tokens funcionais |
| Overlays | `components/modals/modal.html` + JS global | vários modais específicos | preservar contratos data-*; unificar painel, backdrop e foco |
| UI Lab | `templates/dev/ui_lab/*` e `templates/ui_lab2/*` | duas superfícies de demonstração | usar como matriz de paridade durante a migração |

## Decisões arquiteturais

1. O tema claro não recebe novos tokens nem regras visuais nesta meta.
2. A camada `dark-redesign.css` é carregada por último e só atua sob os seletores oficiais/legados de tema escuro.
3. Componentes continuam usando os contratos HTML e `data-*` atuais, preservando payloads, names e IDs de formulários Django.
4. Valores visuais específicos de páginas devem migrar gradualmente para tokens semânticos; a camada final garante consistência enquanto essa migração ocorre.
5. Implementações legadas só serão removidas depois da migração e da validação de todos os consumidores.

## DireÃ§Ã£o visual aprovada

- Base azul-marinho profunda, sem chegar ao preto azulado.
- SuperfÃ­cies sÃ³lidas em grafite e cinza-azulado, com profundidade por diferenÃ§a de luminÃ¢ncia.
- Dourado firme e controlado em detalhes, tÃ­tulos, seleÃ§Ã£o e linhas de destaque.
- AÃ§Ãµes primÃ¡rias em azul profundo; dourado nÃ£o Ã© preenchimento padrÃ£o de botÃ£o.
- Evitar azuis luminosos, ciano/neon, brilhos excessivos e grandes gradientes decorativos.
- A remodelaÃ§Ã£o deve reconstruir hierarquia, estrutura e interaÃ§Ãµes; troca de paleta isolada nÃ£o conta como migraÃ§Ã£o de uma pÃ¡gina.
- O seletor de anexos reconstruÃ­do Ã© referÃªncia de qualidade: a funÃ§Ã£o e o payload Django permanecem, mas a apresentaÃ§Ã£o vira um componente organizado e reutilizÃ¡vel.

## Fluxos protegidos

- Autenticação, perfil e administração.
- CV Picker single/multiple, selects customizados e calendários.
- Wizards de ofícios, roteiros, planos de trabalho, ordens de serviço e eventos.
- Documentos, assinatura, anexos e visualização PDF.
- Listas, filtros, buscas, paginação e ações assíncronas.
- Google Drive. O antigo mÃ³dulo de Protocolos foi retirado da aplicaÃ§Ã£o por decisÃ£o do usuÃ¡rio; seus dados histÃ³ricos nÃ£o sÃ£o apagados por esta remodelaÃ§Ã£o.

## Critério de migração por grupo

Inventariar consumidores → aplicar contrato canônico → demonstrar no UI Lab → validar tema escuro → validar funcionamento no tema claro → executar testes → só então remover legado.

## Rodada v2 — componentização global (2026-07-18, branch redesign/dark-components-v2)

Consolidações concluídas nesta rodada:

- **Ícones**: sistema único em `templates/components/ui/icons/icon.html` (grid 24, stroke 1.75,
  pdf/docx com glifos desenhados). `dev/ui_lab/partials/_cv_icon.html` apenas delega.
- **Destinos**: partials unificados em `templates/components/domain/destinos/` (prefix os|pt|termo).
- **Cabeçalho de filtros**: modo `advanced` no `components/ui/headers/header_stack_filters.html`;
  o clone `oficios_cloned_list_header.html` e o form inline de ofícios foram removidos.
- **Listas em cards**: `components/lists/list_page_cards.html` + casca `page-shell--cards`/`cv-card-grid`
  (CSS em `components/record-list.css`). As 5 index (ofícios, eventos, prestações, OS, PT) viraram 1 include.
- **Entity card**: `components/ui/lists/entity_card{,_header,_footer,_menu}.html` + builders em
  `core/entity_cards.py`; os 6 cards de lista agora são casca fina + `_<app>_card_body.html`.
- **JS extraído de templates**: `js/pages/eventos-detalhe.js` e `js/pages/prestacoes-diaria-wa.js`.
- **file_list**: lista de anexos global em `components/ui/lists/file_list.html`.
- **Botões**: refinamento dark (relevo/estados/foco) no fim de `dark-redesign.css`; fusão de
  `buttons.css`/`buttons-functional.css`/`cv-buttons.css` continua PENDENTE (baixo ganho, risco médio).

Órfãos removidos: regras de `app-page--main-card-list`/`oficios-list-page`/`list-grid--roteiros`
em `roteiros-list.css` e `eventos-list.css`. As classes `oficio-lc__*` seguem em uso pelos
miolos dos cards (remoção só depois de um redesign de miolo).

## Rodada v2 — anexos canônicos (2026-07-18)

- **File picker global**: `components/ui/forms/file_picker.html`, `components/file-picker.css` e
  `components/file-picker.js` agora formam um contrato único para vazio, seleção simples,
  seleção múltipla, revisão, remoção, preview, drag-and-drop e estado ocupado.
- **Conteúdo dinâmico**: o componente foi registrado no enhancer global e possui guarda
  idempotente, alcançando formulários inseridos depois do carregamento inicial.
- **Acessibilidade**: seleção anunciada por `role=status`, ajuda/erro ligados por
  `aria-describedby`, fechamento da lista por `Escape` e ações com nomes acessíveis.
- **Prestação de contas**: a cópia de renderização e manipulação de arquivos foi removida
  de `prestacoes-contas-documentos.js`; esse módulo conserva somente autosave, CSRF, payloads,
  exclusão remota e atualização do título.
- **Documento assinado**: o modal passou a usar `CV.dialogs` e o enhancer global, compartilhando
  trap de foco, fechamento por `Escape`, restauração do foco e suporte a DOM dinâmico.
- **UI Lab**: o seletor real está demonstrado em `dev/ui_lab/fields.html`.
- **Validação visual**: conferidos vazio, dois arquivos, expansão, remoção individual,
  desktop, 810 px, 600 px e tema claro. O modal real foi conferido em Prestações de Contas,
  inclusive abertura por gatilho, foco inicial, `Escape` e restauração do foco.

## Rodada v2 — wizard guiado de eventos (2026-07-18)

- **Identidade corrigida**: o fluxo real não usa mais o rótulo incorreto “Cadastro de ofício”;
  o cabeçalho passa a apresentar Eventos, título de fallback, etapa atual e período.
- **Hierarquia por tarefa**: os blocos internos da etapa 1 agora são “Identificação do evento”,
  “Quando e onde” e “Documentos vinculados”, sem numeração concorrente com o stepper global.
- **Seções mais leves**: os modificadores globais `--compact` e `--described` reduzem a altura
  do cabeçalho e permitem instruções curtas; ambos estão demonstrados no UI Lab Structures.
- **Direção azul**: o filete dos cards de wizard no tema escuro usa o azul primário, deixando
  o dourado fora da estrutura dominante dos formulários.
- **Abas acessíveis**: documentos vinculados usam relação tab/tabpanel completa, roving
  `tabindex`, setas esquerda/direita, `Home`, `End` e registro no enhancer global.
- **Contratos preservados**: o formulário continua enviando os mesmos campos de tipos, motivo,
  datas, destinos e cinco `ModelMultipleChoiceField`; URLs e transições do wizard não mudaram.
## Família visual de cards — formulários e listas

- Cards de formulário e cards de lista passam a consumir os mesmos tokens escuros de superfície, cabeçalho, borda, sombra e acento.
- A família cobre tanto seções de wizard (`cv-wizard-section-card`) quanto formulários CRUD compactos (`main-form-panel`).
- O cabeçalho canônico de formulário usa a mesma superfície azul-marinho profunda e o mesmo banho dourado lateral dos cards de lista.
- O filete dourado compartilha cor, espessura e acabamento; sua geometria continua acompanhando o conteúdo do formulário.
- A diferença de comportamento é intencional: cards de lista podem elevar no hover; cards com campos permanecem estáveis durante o preenchimento.

## Coleções em fluxos guiados

- Cabeçalhos autônomos de coleção reutilizam o cabeçalho canônico dos cards sem criar uma superfície externa em torno de cards de lista.
- Os cabeçalhos organizam e explicam cada coleção; as ações de criação permanecem em FABs, conforme preferência visual aprovada pelo usuário.
- As etapas 2 a 5 de Eventos foram organizadas em coleções nomeadas para roteiros, ofícios, planejamento e termos.
- `templates/eventos/wizard_novo.html` foi removido após comprovação de que nenhuma URL, view ou include o consumia; o fluxo ativo permanece em `templates/eventos/detalhe.html`.
