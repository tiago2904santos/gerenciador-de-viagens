# Auditoria de componentes globais

## Resultado

A padronizacao foi executada sobre o `origin/main` atual no momento do fechamento (`829fa6e`), na branch `codex/padronizacao-componentes-globais`. O inventario final possui 79 templates em `templates/components/`, sem grupos de arquivos com conteudo identico por SHA-256.

Foram preservados nomes de campos enviados ao backend, IDs usados por formularios, URLs, regras de negocio e contratos especificos de cada modulo. Nomes estruturais de templates, classes e hooks JavaScript passaram a expressar responsabilidade visual ou funcional.

## Salvaguardas

- Branch de trabalho: `codex/padronizacao-componentes-globais`.
- Base verificada com `git fetch origin` e `git merge-base --is-ancestor origin/main HEAD`.
- Stashes de seguranca mantidos: `wip-tracked-padronizacao-sobre-main-atual` e `wip-padronizacao-componentes-antes-atualizar-main`.
- Backup local do banco de teste: `dados/local_teste_backup_componentes_20260722-021918.sqlite3` (ignorado pelo Git).
- Nenhuma migration foi criada.

## Mapeamento de consolidacao

| Antes | Componente canonico | Motivo |
| --- | --- | --- |
| `header_stack_back_action`, `header_stack_simple`, `header_stack_stepper`, `header_band_status` | `components/ui/headers/page_header.html` | Um cabecalho parametrizado, incluindo faixa sem rail com `band_only`. |
| `header_stack_filters` | `components/ui/headers/filter_page_header.html` | Nome por responsabilidade e composicao direta com o cabecalho global. |
| `status_pill` e wrappers de lista | `components/ui/badges/status_badge.html` | Um unico mapeamento de status para o chip global. |
| `buttons/action_button.html` | `components/ui/buttons/button.html` | Eliminacao de alias sem comportamento proprio. |
| `forms/form_field.html` e `forms/input_with_action.html` | `components/ui/forms/field.html` | Um contrato de campo com slots e acoes. |
| `forms/cv_date_picker.html` | `components/ui/forms/date_picker.html` | Nome sem prefixo historico; o slot `range_controls_template` atende o bate-volta. |
| `oficio_motorista_split_field.html` | `components/ui/forms/document_number_field.html` | Nome por funcao, reutilizavel fora de Oficios. |
| linhas/secoes locais de destinos em Termos, OS, PT, Eventos e Roteiros | `components/travel/destination_section.html` e `destination_row.html` | Estrutura, estados vazios, ordenacao e remocao centralizados. |
| `components/domain/trechos.html` e partial local de Roteiros | `components/travel/route_segments.html` | Cartoes de trecho consolidados no dominio de viagem. |
| calculadora local de diarias | `components/travel/travel_allowance_calculator.html` | Responsabilidade explicita e compartilhavel. |
| `destinos-section.js` / `window.CV.destinos` | `destination-section.js` / `window.CV.destinations` | API estrutural em ingles, mantendo nomes de campos do backend. |
| `oficio-motorista-suffix.js` | `document-number-field.js` | Hook orientado ao componente. |
| seletores `ui-lab-*` em CSS de producao | `static/css/dev/ui-lab-pages.css` | Isolamento dos demonstradores do UI Lab. |

## Remocoes

Foram removidos aliases, wrappers sem logica e componentes sem consumidor, incluindo as antigas arvores `components/domain/`, wrappers de cabecalho, aliases de botao/campo/paginacao, layouts nao usados, modais duplicados e linhas locais de destino.

Os componentes que permanecem apenas no UI Lab sao primitivas documentadas da biblioteca, nao aliases de producao. Eles continuam como exemplos executaveis e cobertos pelos testes de inventario.

## Modulos e paginas migrados

- Cabecalhos, filtros, badges, botoes e campos: Dashboard, Cadastros, Documentos, Diario de Bordo, Eventos, Oficios, Ordens de Servico, Planos de Trabalho, Prestacoes de Contas, Roteiros, Termos e Usuarios.
- Destinos compartilhados: cadastro e detalhe de Eventos, Termos, Ordens de Servico, Planos de Trabalho e editor de Roteiros.
- Rotas e diarias: editor de Roteiros e composicoes relacionadas de Oficios.
- Demonstracao: UI Lab e UI Lab 2 atualizados para renderizar os componentes canonicos.

## Verificacoes automatizadas

- `python manage.py check`: aprovado.
- `python manage.py makemigrations --check --dry-run`: nenhuma alteracao detectada.
- Auditoria frontend: 0 erros, 461 avisos e 11 excecoes documentadas.
- Auditoria arquitetural: 141 suspeitas informativas; nenhuma regressao bloqueante introduzida por esta entrega.
- Sintaxe JavaScript: 8 arquivos alterados analisados com Node.js, todos aprovados.
- Testes focados de componentes, temas, date picker, Termos, Oficios, Planos de Trabalho e Roteiros: 129 aprovados.
- Teste especifico do cabecalho de Oficios: aprovado apos a consolidacao.
- Inventario: 79 componentes HTML ativos e 0 grupos duplicados por hash.
- Busca por nomes removidos em templates, estaticos e Python de producao: nenhuma referencia encontrada.
- `git diff --check` com CRLF reconhecido: aprovado.

## Suite completa

A suite completa encontrou 769 testes e terminou com 21 erros e 13 falhas. A triagem isolada confirmou problemas preexistentes ou ambientais fora do escopo desta refatoracao, entre eles rotas CRUD ausentes (`cargo_create`, `programa_novo`, `horario_novo` e equivalentes), dependencia opcional `docxcompose` indisponivel e divergencias antigas de modelos/servicos de Oficios, Eventos e Usuarios.

Os testes diretamente relacionados aos componentes migrados foram executados separadamente e aprovados. Nenhuma correcao de regra de negocio fora do escopo foi incorporada para mascarar essas falhas.

## Verificacao visual e manual

No navegador integrado foram validados:

- UI Lab de cabecalhos em 1280 x 720 nos temas claro e escuro, sem overflow horizontal ou interno.
- Cadastro de Termo nos temas claro e escuro, com secao e linha canonicas de destino.
- Inclusao e remocao dinamica de destino (`1 -> 2 -> 1`) sem seletores legados e sem mensagens de erro no console.
- Preservacao do cabecalho, campos, IDs e comportamento aparente das paginas verificadas.

## Fontes de verdade

- Catalogo e regras: `docs/COMPONENTES.md`.
- Componentes do dominio de viagem: `docs/COMPONENTES_DOMINIO.md`.
- Guia resumido de uso: `docs/ui-components.md`.
- Implementacao global: `templates/components/ui/` e `templates/components/travel/`.
- Estilos exclusivos de demonstracao: `static/css/dev/`.
