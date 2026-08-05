# Ciclo de refactor de julho/2026 — arquivo histórico

**Não edite nada nesta pasta.** É registro datado: o que foi diagnosticado em 27–28/07/2026,
o que foi decidido e o que foi entregue entre 28/07 e 05/08/2026. Correção de rumo entra no
catálogo vigente (`docs/CATALOGO_DEFEITOS_2026-08.md`), nunca aqui.

O ciclo terminou em **05/08/2026**, quando o plano foi substituído por
[`docs/PLANO_MESTRE_REFATORACAO.md`](../../PLANO_MESTRE_REFATORACAO.md).

## O que este ciclo entregou

| Etapa | Itens fechados | Situação ao arquivar |
|---|---:|---|
| 1 — Correções críticas isoladas | 21 | fechada |
| 2 — Rede de segurança (testes) | 5 | fechada |
| 3 — Regra de negócio (diárias) | 10 | fechada (`NOVO-12` decidido como "não implementar") |
| 4 — Backend de aderência | 8 | fechada |
| 5 — Motores JS | 17 | fechada |
| 6 — Estrutura HTML | 7 | fechada |
| 7 — Reconstrução do CSS | 12 | fechada |
| 8 — Higiene e polimento | 8 de 14 | **incompleta** — o resto migrou para o catálogo novo |
| 7.1 — Escopo novo (deploy, triagem) | 4 | fechada |

Linha de base ao fechar o ciclo: **1.301 testes verdes** em PostgreSQL (eram 812 no início),
auditor de front em **392 avisos** (era 465), catraca de CI em 401.

### O que ficou pendente e foi transferido

Os itens abaixo saíram da Etapa 8 sem serem feitos e reaparecem no catálogo novo com ID novo:

- `G-01` arquivos indevidos no repositório · `G-03` repositório fora do OneDrive · `N-12` `media/` de 191 MB
- `S-02` e-mail · `S-03` rate limit no login · `S-04` CSP · `S-05` `SECRET_KEY` default
- `R-02` sistema de ícones (if/elif longo, órfãos)
- `N-11` microcopy: variantes de "Voltar à lista"
- `P-08` decidir `diario_bordo` · motor de PDF canônico

`G-02` ("docs datados → `docs/historico/`") foi cumprido pela criação desta pasta.

## Como os documentos estão organizados

| Pasta | Conteúdo |
|---|---|
| `auditorias/` | Os cinco diagnósticos de 27–28/07 (`D-xx`, `H-xx`, `J-xx`, `P-xx`, `S-xx`, `T-xx`, `N-xx`) mais as auditorias menores de CSS e arquitetura |
| `planos/` | O plano de execução das oito etapas, os prompts padronizados e os planos por app (ofícios, OS, termos, planos de trabalho, justificativas) |
| `relatorios/` | Relatórios de fase produzidos durante a execução |
| `mapas-legado/` | Mapas da migração 2.0 → 3.0 (models, views, forms, services, ofícios) |

## Por que os IDs antigos não valem mais

O catálogo de julho descrevia o código de julho. Depois de ~120 PRs, boa parte dos enunciados
está vencida — três correções de rumo ficaram registradas no próprio plano (`J-05`, `J-11`,
tokens indefinidos), e em todas o enunciado original era mais largo ou mais antigo que o código.
Citar `D-14` hoje é citar um retrato, não o sistema.

O catálogo vigente usa prefixos novos, sem colisão com estes: `BE`, `DB`, `UI`, `HT`, `JS`,
`PF`, `QA`.

## Duas propostas que continuam válidas

Estão arquivadas porque pertenciam ao plano antigo, mas o conteúdo não venceu:

- `planos/PROPOSTA_CONFIGURACOES.md` — arquitetura de configurações por seções declaradas.
  Estava "aguardando decisão de posição na fila"; a decisão está no plano mestre novo.
- `planos/PLANO_CONFIGURACOES.md` — o detalhamento da mesma proposta.
