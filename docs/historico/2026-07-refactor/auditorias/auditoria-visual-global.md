# Auditoria visual global

Auditoria executada em 22/07/2026. O inventário estático cobriu 68 templates de página e seus parciais; 52 rotas autenticadas foram renderizadas em desktop. Uma amostra representativa de 13 fluxos foi validada em notebook (1280 × 800), tablet (768 × 1024) e celular (390 × 844), nos temas claro e escuro.

## Referências adotadas

- Listas simples: `list_page_standard.html` e a anatomia `simple_list`.
- Listas complexas: `list_page_cards.html`, com cabeçalho, filtros, abas, cards e estados globais.
- Cadastros auxiliares: `list_page_quick_add.html`.
- Formulários: estruturas Standard Simple, Standard e Wizard documentadas no UI Lab, usando `page_header.html`, `form_block.html`, `field.html` e os rodapés globais.
- Confirmações e estados vazios: `page-shell--standard-simple`, feedback e modal globais.

## Matriz de classificação e correção

| Página ou família | Tipo | Estrutura esperada | Situação encontrada | Correção / status |
| --- | --- | --- | --- | --- |
| Dashboard | Visão geral | Dashboard | Componentes globais de métricas e atalhos | Conforme |
| Perfil | Standard com seções | Standard | Header, cards, métricas, lista e responsividade exclusivos | Migrado integralmente para header, cards, métricas, lista, campos, badges e rodapés globais; CSS exclusivo removido |
| Administração de usuários | Formulário com seções | Standard | Marcado indevidamente como Wizard | Reclassificado como Standard |
| Hub de cadastros | Hub de navegação | Hub | Estrutura própria coerente com a finalidade | Conforme |
| Configuração | Formulário com seções | Standard | Marcado como Wizard, sem navegação sequencial | Reclassificado como Standard |
| Cargos, combustíveis, unidades e estados | Lista com Quick Add | Quick Add global | Componente global já utilizado | Conforme; cabeçalho global normalizado |
| Tipos de evento, modelos de motivo e justificativa | Lista com Quick Add | Quick Add global | Componente global já utilizado | Conforme; cabeçalho global normalizado |
| Atividades, horários, presets e programas de PT | Lista com Quick Add | Quick Add global | Componente global já utilizado | Conforme; cabeçalho global normalizado |
| Servidores | Lista simples | Standard list | Componente global já utilizado | Conforme |
| Cadastro/edição de servidor | Standard Simple | Standard Simple | Marcado como Wizard | Reclassificado como Standard Simple |
| Viaturas | Lista simples | Standard list | Componente global já utilizado | Conforme |
| Cadastro/edição de viatura | Formulário com seções | Standard | Marcado como Wizard | Reclassificado como Standard |
| Roteiros | Lista simples com abas | Standard list | Componente global já utilizado | Conforme |
| Cadastro/edição de roteiro | Wizard | Wizard | Stepper e seções globais | Conforme |
| Eventos | Lista complexa em cards | Cards + filtros avançados | Componente global já utilizado | Conforme; CSS duplicado deixou de ser recarregado |
| Cadastro/edição direta de evento | Formulário com seções | Standard | Marcado como Wizard sem etapas | Reclassificado como Standard |
| Painel guiado do evento | Wizard | Wizard | Etapas e cards globais | Conforme |
| Ofícios | Lista complexa em cards | Cards + filtros avançados | Componente global já utilizado | Conforme; CSS duplicado deixou de ser recarregado |
| Etapas de ofício: viajantes, transporte, roteiro, justificativa e documentos | Wizard | Wizard | Estrutura sequencial correta | Conforme; override inline redundante removido |
| Termos | Lista simples | Standard list | Componente global já utilizado | Conforme |
| Cadastro/edição de termo | Formulário com conteúdo relacionado e repetível | Standard | Marcado como Wizard sem stepper | Reclassificado como Standard; comportamento preservado |
| Pré-visualização de termo | Visualização | Standard Simple | Estrutura simples já utilizada | Conforme |
| Prévia antes do cadastro de termo | Visualização | Standard Simple | Marcada como Wizard | Reclassificada como Standard Simple |
| Ordens de Serviço | Lista complexa em cards | Cards + filtros avançados | Componente global já utilizado | Conforme; CSS duplicado deixou de ser recarregado |
| Cadastro/edição de OS | Formulário com conteúdo relacionado e repetível | Standard | Marcado como Wizard sem stepper | Reclassificado como Standard; comportamento preservado |
| Planos de Trabalho | Lista complexa em cards | Cards + filtros avançados | Componente global já utilizado | Conforme; CSS duplicado deixou de ser recarregado |
| Etapas de PT: identificação, atividades, efetivo/diárias e documentos | Wizard | Wizard | Estrutura sequencial correta | Conforme |
| Prestações de Contas | Lista complexa em cards | Cards + filtros avançados | Componente global já utilizado | Conforme |
| Relatório técnico, diários, documentos e consolidado | Wizard documental | Wizard | Stepper e seções compartilhadas | Conforme; CSS duplicado deixou de ser recarregado |
| Modelos de texto de prestação | Standard Simple / confirmação | Standard Simple | Estrutura global já utilizada | Conforme |
| Justificativas | Lista com Quick Add | Quick Add global | Componente global já utilizado | Conforme |
| Diário de bordo e documentos | Estado inicial | Standard Simple | Estrutura global já utilizada | Conforme |
| Visualizador de PDF | Visualização de documento | Viewer global | Componente global de visualização | Conforme |
| Confirmações de exclusão | Confirmação | Standard Simple / modal global | Estruturas equivalentes | Conforme |
| Estados vazios, mensagens e validações | Feedback | Componentes globais | Componentes compartilhados nas famílias auditadas | Conforme |
| Django Admin técnico | Administração técnica | Interface do Django | Identidade separada do produto | Mantido sem alteração para não substituir o admin nem criar uma segunda camada visual; a administração usada pelo sistema é `/usuarios/` |

## Divergências corrigidas na origem

- O cabeçalho global de listas passou a depender exclusivamente de tokens existentes para cores, bordas, sombras, tipografia, espaçamento, foco e transições.
- Os controles de busca, filtro, período e Quick Add usam a mesma altura global de 44 px em todas as famílias.
- Foram removidos os `!important` do cabeçalho de listas; a ordem canônica de carregamento é suficiente.
- O estado ativo do filtro de período passou a usar tokens sem paletas locais diferentes por tema.
- `page-shell.css` deixou de ser carregado duas vezes.
- `oficios.css`, já compartilhado pela folha principal, deixou de ser recarregado por 16 templates de módulos.
- O override inline da etapa de roteiro de ofício foi removido porque a regra equivalente já existia na camada global de tema.
- O perfil deixou de carregar uma folha visual própria de 357 linhas.

## Validação visual

- Desktop: 52 rotas, sem overflow horizontal.
- Notebook, tablet e celular: dashboard, perfil, listas Standard/Quick Add/Cards, formulários Standard e Wizards representativos, sem overflow de conteúdo ou ações.
- Tema claro e escuro: cabeçalhos, filtros, busca, Quick Add e perfil verificados; controles com 44 px e sem borda conflitante.
- Componentes dinâmicos: hooks e IDs de roteiro, termos, OS, PT e Google Drive foram preservados.

## Validação automatizada

- `python manage.py check`: aprovado, sem erros.
- `python -m compileall`: aprovado.
- `python scripts/audit_frontend_standards.py`: 0 erros; os avisos remanescentes pertencem à dívida técnica inventariada pelo projeto.
- `python manage.py test core.tests`: 62 testes aprovados. Esse conjunto cobre o perfil migrado, o tema e os contratos visuais globais.
- `python manage.py test`: 769 testes executados; 13 falhas e 21 erros legados. Os erros incluem nomes de rotas antigas de cadastros (`cargo_create`, `combustivel_create`, `unidade_create`, cidades, horários, programas e modelos) que não existem mais após a migração anterior para Quick Add, além de fixtures/expectativas documentais antigas. A primeira falha ocorre sem alcançar qualquer arquivo alterado nesta tarefa.
