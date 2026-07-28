# CLAUDE.md

**Leia `AGENTS.md` na raiz antes de qualquer coisa.** Ele é a constituição do refactor e
vale integralmente para o Claude Code: IDs de defeito, limites invioláveis, ciclo de
trabalho, corpo de PR e comandos do projeto.

Este arquivo cobre apenas o que é específico do Claude Code.

## Ordem de leitura

1. `AGENTS.md` — regras.
2. `docs/PLANO_REFATORACAO_EXECUCAO.md` — o que fazer agora e qual é o gate da etapa.
3. Apenas a seção da auditoria citada na tarefa (os documentos têm 900+ linhas; ler inteiro
   queima contexto sem ganho).
4. `docs/PROMPTS_REFATORACAO.md` — se a tarefa veio de um prompt padronizado.

## Especificidades do Claude Code

- **Uma etapa por sessão.** Etapas do plano são desenhadas para caber num PR. Terminou a
  etapa, abra o PR e encerre; não emende a próxima na mesma branch.
- **Plan mode antes de escrever** em qualquer etapa marcada como `risco: médio` ou superior
  no plano (motor de diárias, constraints, reconstrução CSS).
- **Rode a suíte de verdade**, não confie em leitura estática: a sessão remota já sobe
  PostgreSQL e roda `migrate` pelo hook `.claude/hooks/session-start.sh`.
- **Subagentes** só quando a etapa pedir varredura ampla (ex.: "encontre todas as cópias do
  sistema de destinos"). Para editar, trabalhe no fio principal.
- **Não reescreva as auditorias.** Elas são registro histórico datado. Correção de rumo entra
  como linha nova no catálogo, marcada `NOVO`, ou como nota no plano de execução.

## Uso da tela

Para etapas visuais, o servidor sobe em `http://127.0.0.1:8000`. Chromium está pré-instalado
com Playwright configurado (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`). Não rode
`playwright install`. Prints de antes/depois em tema escuro vão no corpo do PR.
