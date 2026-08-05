# CLAUDE.md

**Leia `AGENTS.md` na raiz antes de qualquer coisa.** Ele é a constituição do refactor e
vale integralmente para o Claude Code: IDs de defeito, limites invioláveis, ciclo de
trabalho, corpo de PR e comandos do projeto.

Este arquivo cobre apenas o que é específico do Claude Code.

## Ordem de leitura

1. `AGENTS.md` — regras.
2. `docs/PLANO_MESTRE_REFATORACAO.md` — o que fazer agora e qual é o gate da etapa.
3. O plano da etapa (`PLANO_BACKEND.md`, `PLANO_FRONTEND.md` ou `PLANO_DESEMPENHO.md`).
4. Apenas as linhas do `docs/CATALOGO_DEFEITOS_2026-08.md` citadas na tarefa — o catálogo é
   longo; ler inteiro queima contexto sem ganho.

O ciclo anterior está em `docs/historico/2026-07-refactor/`. Consulte só quando precisar
entender por que uma decisão antiga foi tomada; os IDs de lá não são unidade de trabalho.

## Especificidades do Claude Code

- **Uma etapa por sessão.** Etapas do plano são desenhadas para caber num PR. Terminou a
  etapa, abra o PR e encerre; não emende a próxima na mesma branch.
- **Plan mode antes de escrever** em qualquer etapa marcada como `risco: médio` ou superior
  no plano (motor de diárias, constraints, reconstrução CSS).
- **Rode a suíte de verdade**, não confie em leitura estática: a sessão remota já sobe
  PostgreSQL e roda `migrate` pelo hook `.claude/hooks/session-start.sh`.
- **Subagentes** só quando a etapa pedir varredura ampla (ex.: "encontre todas as cópias do
  sistema de destinos"). Para editar, trabalhe no fio principal.
- **Não reescreva `docs/historico/`.** É registro datado. Correção de rumo entra como linha
  nova no `CATALOGO_DEFEITOS_2026-08.md`, marcada `NOVO`, ou como nota no plano da etapa.
- **A máquina tem 4 núcleos:** workflow roda 2 agentes por vez. Fan-out largo demora; prefira
  poucos agentes com escopo grande a muitos com escopo pequeno.

## Uso da tela

Para etapas visuais, o servidor sobe em `http://127.0.0.1:8000`. Chromium está pré-instalado
com Playwright configurado (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`). Não rode
`playwright install`. Prints de antes/depois em tema escuro vão no corpo do PR.
